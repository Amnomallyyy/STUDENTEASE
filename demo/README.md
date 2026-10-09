# Demo folder: judge test instructions

Everything here is synthetic. "Sara Ahmed" is a fictional final-year student (email `sara.ahmed@example.com`,
phone `+92 300 0000000`, "Example University", Karachi). No real person's data is used anywhere in CareerLens.

| File | What it is |
|---|---|
| `demo_cv.pdf` / `demo_cv.txt` | The demo CV (target role: Data Analyst) with three planted anomalies |
| `linkedin_export.pdf` / `linkedin_export.txt` | A LinkedIn "Download your data" style export for the same persona |
| `github_username.txt` | The GitHub username the analyzer is run with (`careerlens-demo`) |
| `cached_responses.json` | Cached GitHub data for that username plus recorded LLM answers for the demo CV (offline replay) |

The `.txt` files are the source; `python scripts/make_demo_files.py` regenerates both PDFs and verifies them.

## 1. Run it (about 2 minutes)

```bash
# backend, from the repo root
python -m venv .venv && .venv/Scripts/activate      # or: source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env                                   # add ANTHROPIC_API_KEY (or OPENAI_API_KEY), or use offline mode below
uvicorn backend.main:app --reload                      # http://localhost:8000, docs at /docs

# frontend, second terminal
cd frontend && npm i && npm run dev                    # http://localhost:5173
```

Then, in the browser:

1. **Upload** `demo/demo_cv.pdf`, pick target role **Data Analyst**, allow location or type **Karachi**.
2. **Career Map** opens. Expect: a match percentage against Data Analyst with the matched / partial / missing
   skills listed, **20 or more pins** within 25 km of Karachi, each pin showing its own ticks and crosses, a
   "N of 20 nearby jobs ask for SQL"-style market gap, and a **4-week roadmap**. Pin a job: the roadmap
   re-orders to that job's missing skills first.
3. **CV Analyzer**: enter the GitHub username from `github_username.txt` and upload `linkedin_export.pdf`.
   Expect **exactly three anomalies**:

   | Planted anomaly | Rule | What the card says |
   |---|---|---|
   | **Kubernetes** on the CV, nowhere on GitHub or LinkedIn | `invented_skill` (unsupported claim) | Remove it or add evidence |
   | **JavaScript** is 35 % of the GitHub code (`weather-dashboard`) but absent from the CV | `missing_repo` (missed strength) | Add the weather-dashboard repo under Projects |
   | **"Expert in Docker"** with a single mention anywhere | `overclaim` | Change "Expert in" to "Familiar with" |

   Everything else on the CV (Python, Pandas, NumPy, Matplotlib, Jupyter, Excel, Statistics, Git, Communication,
   Teamwork, both projects, the internship) is backed by LinkedIn and/or GitHub, so no other card appears. The
   integrity score is the share of CV claims with at least one external source.
4. **Chat**: ask "What should I do first?" - the answer cites the roadmap and the top market gap.
5. **Mock interview**: answer one question (typed or spoken); the readiness score splits verbal 70 / non-verbal 30.
6. **Delete my data** clears the server session and the browser store.

Without the frontend, the same flow runs against the API alone:

```bash
python scripts/build_demo_cache.py        # DELETE /profile, POST /profile/cv, GET /career/roadmap, POST /analyzer/run; prints a summary
```

or interactively at `http://localhost:8000/docs`.

## 2. Offline mode (no API key, no internet)

Start the backend with the cache file and the local embedding model:

```bash
LLM_CACHE_PATH=demo/cached_responses.json EMBED_PROVIDER=local uvicorn backend.main:app
```

PowerShell: `$env:LLM_CACHE_PATH="demo/cached_responses.json"; uvicorn backend.main:app`

- Every LLM prompt produced by the demo CV is answered from the `llm` section of the file, keyed by a SHA-256 of
  the output schema plus the prompt text (recorded with `LLM_CACHE_RECORD=1`, see `scripts/build_demo_cache.py`).
  A prompt that is not in the cache falls through to the configured provider, so a different CV still works when
  online. Note that the prompt includes the CV text, so re-generating `demo_cv.pdf` changes the keys: run the
  recording step again after editing the demo files.
- GitHub data for `careerlens-demo` comes from the `github` section (`GITHUB_CACHE_PATH` already defaults to this
  file); no request leaves the machine.
- Embeddings come from `sentence-transformers/all-MiniLM-L6-v2`, which runs on CPU; the first call downloads the
  model once (about 90 MB), after which `backend/cache/embeddings.json` caches every vector.

Rehearsal: switch the laptop's Wi-Fi off and run step 1 again; every screen must still fill.

## 3. Swapping in a real GitHub account

The team can show a member's real account instead of the cached one:

1. Put the username in `demo/github_username.txt` and type it in the Analyzer screen.
2. Make sure that account has a repo whose main language is **not** on the CV and holds more than 20 % of the
   account's code (the "missed strength" rule), and that the CV's project names match repo names.
3. Optionally set `GITHUB_TOKEN` in `.env` (5000 req/h instead of 60).
4. To make it work offline, run the analyzer once online while `GITHUB_CACHE_PATH` points at a writable copy of
   `cached_responses.json` and `LLM_CACHE_RECORD=1`, then commit the file.

## 4. What to say about the data sources

- GitHub: official REST API, the user's own username only, within rate limits.
- LinkedIn: the user's own "Download your data" export (or pasted profile text). Never scraped.
- Jobs: `data/jobs.json` is seeded (public postings with source URLs, or labelled `synthetic: true`); the map does
  not depend on a live job site.
- The CV parser drops email, phone, address and date-of-birth lines before any text reaches an LLM.
