# Disclosures: work prepared before the AICON'26 build period

Last updated: **2026-10-09**

The AICON'26 rulebook allows pre-existing resources if they are disclosed. This file lists everything that existed
in the repository before the build period, by member and file, so judges can tell pre-built from in-competition
work.

## How to verify

- The commit on the day the build period starts is tagged **`pre-event`** (`git tag pre-event <sha>`; pushed
  with `git push origin pre-event`). Every commit reachable from that tag is pre-event work and is listed below.
- Everything after it is in-competition work: `git log pre-event..main --name-status` shows exactly which files were
  created or changed during the event, with author and date on each commit.
- Commit messages use conventional prefixes (`feat:`, `fix:`, `data:`, `docs:`), so the log doubles as the record
  of what was built where.

## Pre-event work (all dated 2026-10-09 unless stated)

### M1 - AI core (branches `AI-core`, `feat/m1-extractor`, `feat/m1-matcher`; commits `616d95c`, `06ed4e8`, `49cf942`, `4ad1b12`)

| Date | Files | What |
|---|---|---|
| 2026-10-09 | `backend/llm_adapter.py` | `complete_json()`, `chat()`, `embed()` behind an Anthropic / OpenAI / Ollama switch with the sentence-transformers fallback |
| 2026-10-09 | `backend/schemas/{profile,skill,job,interview,role,api}.py`, `backend/schemas/generate_ts.py`, `frontend/src/types/profile.ts` | Pydantic integration contracts and the generated TypeScript types |
| 2026-10-09 | `backend/prompts/extract_skills.md`, `backend/services/extractor.py`, `backend/services/normalize.py` | CV text -> skills / projects / experience with PII redaction, alias normalisation |
| 2026-10-09 | `backend/services/matcher.py` | Embedding skill matcher (cosine 0.80 / 0.65) with the on-disk embedding cache |
| 2026-10-09 | `backend/services/{differential,roadmap,career,chat,geo,data,session,cv_text}.py`, `backend/prompts/{roadmap,chat_system}.md` | Market-weighted differential, roadmap generator, career orchestration, grounded chatbot with tool calls, distance helpers, dataset loaders, in-memory session, file-to-text |
| 2026-10-09 | `backend/api/{profile,career,chat,errors}.py` | `/profile`, `/career/*`, `/chat` routes and the shared error mapping |
| 2026-10-09 | `backend/tests/{conftest,test_api,test_chat,test_data,test_differential,test_extractor,test_geo,test_matcher,test_roadmap,test_ts_types}.py` | Unit and API tests with fake embeddings (no network) |
| 2026-10-09 | `docs/api.md`, `docs/data_formats.md`, `docs/prompts.md` | API table, dataset formats, prompt index |

### M5 - Data, evidence and DevOps (branch `feat/m5-data-devops`)

| Date | Files | What |
|---|---|---|
| 2026-10-09 | `data/roles.json`, `data/skill_aliases.json`, `data/resources.json`, `scripts/build_roles.py` | 20-30 role skill profiles derived from ESCO / O*NET and public postings; alias table; whitelist of free learning links |
| 2026-10-09 | `data/jobs.json`, `scripts/build_jobs.py`, `scripts/geocode.py` | 150-300 geocoded listings for Karachi / Lahore / Islamabad (public postings with source URLs or labelled `synthetic: true`), required skills pre-extracted; Nominatim geocoding with a cache |
| 2026-10-09 | `backend/services/evidence/{github,linkedin,reconcile,anomalies}.py`, `backend/prompts/anomaly_fix.md` | GitHub REST ingestion, LinkedIn export parsing, cross-source clustering, the five anomaly rules and the LLM fix prompt |
| 2026-10-09 | `backend/api/{jobs,analyzer}.py`, `backend/schemas/analyzer.py`, `backend/tests/test_anomalies.py` and related tests | `/jobs/nearby`, `/jobs/{id}`, `/analyzer/run`, `/analyzer/report` |
| 2026-10-09 | `demo/demo_cv.{txt,pdf}`, `demo/linkedin_export.{txt,pdf}`, `demo/github_username.txt`, `demo/cached_responses.json`, `demo/README.md`, `scripts/make_demo_files.py`, `scripts/build_demo_cache.py` | Synthetic demo persona "Sara Ahmed" with three planted anomalies, cached GitHub data and recorded LLM answers for offline replay, judge instructions |
| 2026-10-09 | `backend/main.py`, `backend/built_with.py`, `backend/requirements*.txt`, `backend/Dockerfile`, `render.yaml`, `.github/workflows/ci.yml`, `ruff.toml`, `.gitignore`, `.env.example`, `backend/tests/test_main.py` | FastAPI app with CORS, `/health`, `/built-with`; Docker image with the MiniLM model baked in; Render blueprint; CI (ruff + pytest + vitest) |
| 2026-10-09 | `README.md`, `DISCLOSURES.md`, `ACKNOWLEDGEMENTS.md`, `LICENSE`, `docs/architecture.md`, `docs/demo_script.md` | Documentation, licence (MIT), acknowledgements, demo script |

### Project planning (before any code)

| Date | Item | What |
|---|---|---|
| 2026-10-09 | Project outline (Mehran Wahid) | Problem statement, module design, architecture, team plan, judging and demo script; the basis of this README and `docs/` |
| 2026-10-09 | `31c52c2` first commit | Repository created with a stub README |

### Third-party resources used as-is

All listed with licences in `ACKNOWLEDGEMENTS.md`: Claude / OpenAI / Ollama models, `all-MiniLM-L6-v2`,
MediaPipe landmarkers, Whisper, GitHub REST API, Nominatim / OpenStreetMap, Web Speech API, the ESCO and O*NET
taxonomies, the free course catalogues the resource list points to, and the open-source libraries in
`backend/requirements.txt` and `frontend/package.json`. None of these were modified.

## What is expected to be built during the event

Per the outline's build timeline (so judges know what to look for after the `pre-event` tag): frontend screens
(Upload, Dashboard, Career Map, Analyzer board, chat panel), the interview NLP pipeline and screen (M3), the
browser vision pipeline and `docs/vision_metrics.md` (M4), integration of every module into the shared dashboard,
threshold tuning on the demo CV, deployment of both ends, and the screen recording.

## Members

| Tag | Role |
|---|---|
| M1 | AI core / backend lead |
| M2 | Frontend lead |
| M3 | Interview NLP |
| M4 | Computer vision |
| M5 | Data, evidence & DevOps (main contact) |
