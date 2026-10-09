# 5-minute demo script

One **presenter** (talks), one **driver** (keyboard, mouse, camera), two on standby for questions; M5 keeps the
backup laptop and the screen recording ready. Demo persona: the synthetic "Sara Ahmed" CV in `demo/`
(see `demo/README.md` for the expected numbers).

## Before walking on stage (checklist)

- [ ] Backend and frontend running on the demo laptop (`uvicorn backend.main:app`, `npm run dev`) **and** the deployed
      link open on a phone with mobile data.
- [ ] `GET /health` shows `status: ok`, the intended `llm_provider`, and non-null `roles` / `jobs` / `resources`.
- [ ] Session is clean: press **Delete my data** (or `DELETE /profile`).
- [ ] `demo/demo_cv.pdf`, `demo/linkedin_export.pdf` and `demo/github_username.txt` open in a file window.
- [ ] Camera and microphone permissions already granted in the browser; lighting checked; presenter sits where the
      landmark overlay ran at >= 10 fps during rehearsal.
- [ ] Offline fallback env ready to paste (`LLM_CACHE_PATH`, `GITHUB_CACHE_PATH`, `EMBED_PROVIDER=local`).
- [ ] Screen recording (2-3 min) on the desktop as the last resort.

## Script

| Time | Beat | Presenter says (gist) | Driver does | On screen |
|---|---|---|---|---|
| 0:00-0:30 | Problem | Graduates apply blind and fail interviews on structure and presence, not knowledge. One statistic from the briefing or a public source. "Upload your CV, and in two minutes know what to fix, where to apply, and how to answer." | Title slide up | Title slide with the one-sentence promise |
| 0:30-1:40 | Career Map | "One CV becomes the shared input for everything." Match %, "N of 20 nearby jobs ask for SQL - learn that first", the pins are coloured by match, each pin shows its own gap. "The LLM structured every listing, the embedding matcher ranks jobs and names each gap, the roadmap is generated from the local market, not a generic template." Toggle keyword-vs-embedding once: "Postgres still matches SQL." | Upload `demo_cv.pdf`, pick **Data Analyst**, allow location (Karachi). Click the top pin -> ticks / crosses. Pin the job -> roadmap re-orders. Flip the keyword toggle and back | Career Map: match meter, missing chips, map with 20+ pins, job detail, 4-week roadmap |
| 1:40-2:25 | CV Analyzer | "Now we check the CV against evidence. GitHub via the official API, LinkedIn via the user's own export - no scraping." Three amber chips: Kubernetes has no evidence anywhere; JavaScript is a third of her GitHub code but missing from the CV; 'Expert in Docker' is mentioned once. Click one: why it matters to a recruiter and the fix. "Integrity score = share of claims with external evidence." | Enter the username from `github_username.txt`, upload `linkedin_export.pdf`, run. Click the Docker chip | Analyzer board, three anomaly cards, integrity score |
| 2:25-4:00 | Mock interview | "Last gap: the interview." Answer one question live, ~50 s, rehearsed, with two deliberate "um"s and one look away. While the report renders: "Fillers and pace are counted by code, not a model. STAR uses a constrained prompt that must quote the transcript - an empty quote means not present, so it cannot invent a Result. Every body-language number is geometry from landmarks; the weights are in the tooltip; video never leaves this laptop." | Start interview, allow camera, record the answer. Point at the eye-contact ring dropping during the look-away, the STAR checklist ticking, the readiness dial (70 / 30), the coaching note naming the look-away, the rewritten answer | Interview screen: landmark overlay, live gauges, then the report |
| 4:00-4:30 | Chatbot | "The assistant answers only from her profile." | Type **"What should I do first?"** -> it cites the top market gap and opens the roadmap | Chat panel over the Career Map |
| 4:30-5:00 | Impact and what we built | SDG 4.4 (relevant skills), 8.6 (youth NEET), 10.2 (free, no login, skills-only matching). Adoption path: a university placement office licensing it for its final-year cohort. One line on pre-built vs built here: "Role and job datasets, demo files and CI were prepared before the event and are dated in DISCLOSURES.md; the screens, the interview pipeline, the vision pipeline and all the integration were built on site - `git log pre-event..main`." | Closing slide | Closing slide |

Hard rules for the driver: never type into the chat while the presenter is talking about something else; never
refresh the page after the upload (the session is in memory); if a request hangs more than 5 s, switch to the
offline path below without commentary.

## Offline fallback rehearsal

Do this once the evening before and once at the venue:

1. Stop the backend. Start it with the cache: `LLM_CACHE_PATH=demo/cached_responses.json EMBED_PROVIDER=local
   uvicorn backend.main:app` (PowerShell: set the two `$env:` variables first). GitHub data for the demo username
   is read from the same file by default.
2. Turn Wi-Fi off on the demo laptop.
3. Run the whole script above with the demo files. Every screen must fill: the LLM answers come from the `llm`
   section of the cache, GitHub from the `github` section, embeddings from the local model, jobs from `data/`.
4. For the interview, type the rehearsed answer (text mode) if the microphone or the Whisper call is the problem;
   the camera overlay still works because MediaPipe is local.
5. If the frontend itself cannot load (tiles, fonts), open the API docs at `http://localhost:8000/docs` and run the
   same calls there; `scripts/build_demo_cache.py` prints the whole flow in the terminal.
6. If the laptop dies: the deployed link on the phone, then the screen recording.

## Q&A: rehearsed answers

1. **Which model and why? What runs locally?** Claude (Sonnet) by default through `llm_adapter.py` for extraction,
   roadmap, STAR, fixes and chat, because structured tool-call output keeps the pipeline deterministic; OpenAI or
   Ollama are one env var away if the organisers restrict APIs. Embeddings are `all-MiniLM-L6-v2` running locally
   (384-dim is plenty for skill names). MediaPipe vision runs in the browser; filler, pace, anomaly rules and the
   cosine thresholds are plain code.
2. **Show me the STAR prompt. How do you stop it hallucinating a Result that is not there?** `backend/prompts/
   star_rubric.md`. The schema requires an `evidence_span` quoted from the transcript for each element; the span is
   checked against the transcript and an empty span means `present: false`. The UI highlights the spans so you can
   see the grounding.
3. **How was the role skill dataset built and what are its sources?** `scripts/build_roles.py` -> `data/roles.json`:
   20-30 roles with 10-20 weighted skills each, derived from the ESCO and O*NET taxonomies (both CC BY 4.0) and
   cross-checked against public postings; core vs preferred weights. Jobs are public postings with source URLs or
   labelled synthetic, geocoded with Nominatim. Everything is committed and disclosed.
4. **What happens with a CV in Urdu, or a scanned image?** Out of scope for the MVP: the parser returns a clear
   "no text found, OCR not supported yet" error. OCR and multilingual embeddings (e.g. a multilingual MiniLM) are
   the next step; the pipeline is text-in, so nothing else changes.
5. **How is this different from LinkedIn's skill suggestions or a generic ChatGPT prompt?** Two things exist nowhere
   else in one place: cross-source verification of the CV against the user's own GitHub and LinkedIn with
   deterministic rules, and geo-matched gaps per job (what *this* employer 4 km away is missing from you). The
   chatbot and roadmap are grounded in those numbers, not general knowledge.
6. **What did you build during the event versus before?** `DISCLOSURES.md` lists every pre-built file with dates;
   the `pre-event` git tag marks the boundary, and `git log pre-event..main` is the in-competition work.
7. **How does the body-language score work, and is it fair?** Geometric metrics from MediaPipe landmarks: eye
   contact = head yaw / pitch within 15 degrees, posture = shoulder tilt and forward lean, fidgeting = wrist velocity,
   head stability = nose variance, expression = smile / brow blendshape averages reported as neutral / engaged /
   tense. Thresholds are in `docs/vision_metrics.md`, weights are visible (35 / 25 / 20 / 10 / 10), it is only 30 %
   of readiness, there is no emotion or identity inference, video never leaves the browser, and it coaches habits;
   it does not judge people.
8. **Privacy of the CV?** Email, phone, ID numbers, DOB and address lines are redacted before any LLM call; only
   skills, projects and experience are kept; no database, in-memory session, "Delete my data" clears everything.
9. **What if the API goes down on stage?** Exactly what we rehearsed: local embeddings, cached LLM answers for the
   demo CV, cached GitHub data, committed job data. We can show it with Wi-Fi off.
