# REST API

One row per endpoint. Everyone adds their own rows; M1 owns the format and the `/profile`, `/career` and `/chat` rows.
Request and response bodies are the Pydantic models in `backend/schemas/`; the TypeScript versions are generated into
`frontend/src/types/profile.ts` with `python -m backend.schemas.generate_ts`.

There are no accounts: the server keeps one in-memory `Profile` for the session (`backend/services/session.py`).

| Route | Owner | Request | Response |
|---|---|---|---|
| `GET /profile` | M1 | none | `Profile` |
| `POST /profile/cv` | M1 | multipart: `file` (PDF/DOCX/TXT, max 5 MB); optional form fields `target_role`, `mode` (`student` or `job_seeker`), `lat`, `lng`, `city` | `Profile` (skills, projects, experience; plus gap and nearby jobs if `target_role` is given and the data files exist) |
| `PATCH /profile` | M1 | `ProfilePatch`: any of `mode`, `target_role`, `location` | `Profile` |
| `DELETE /profile` | M1 | none ("Delete my data") | 204 |
| `GET /career/roles` | M2 | none | `list[Role]`: every target role (`id`, `name`, weighted `skills[]`) from `data/roles.json`, for the role picker and the keyword-vs-embedding toggle; 503 if the file is missing |
| `GET /career/gap` | M1 | query `role` (default: profile's target role), `radius_km` (default 25), optional `lat`, `lng` | `GapResponse`: `match` (`MatchResult`: `match_pct`, `evidenced_pct` (null until the Analyzer has run; then the same weighted % counting only skills backed by GitHub or LinkedIn), `matched[]` (`{name, matched_to, similarity, sources[]}`), `partial[]`, `missing[]`), `market_gaps`, `jobs_nearby`. Also saved on the profile |
| `GET /career/roadmap` | M1 | query `role`, optional `pinned_job_id`, `radius_km` | `Roadmap` (4 weeks; pinning a job moves its missing skills first). Saved on the profile |
| `GET /career/adjacent` | M1 | query `role`, `limit` (default 5) | `list[AdjacentRole]` |
| `POST /chat` | M1 | `ChatRequest`: `{message, history[]}` | `text/event-stream`; see below |
| `GET /jobs/nearby` | M5 | query `lat`, `lng` (default: the profile's location), `radius` (km, default 25), `limit` (default 50), `min_match` (default 0) | `list[JobNearby]` = `JobMatch` + `company`, `title`, `city`, `lat`, `lng`, `synthetic`, `source_url`; scored with `services/differential.score_job`. 409 no CV, 422 no location |
| `GET /jobs/{job_id}` | M5 | path `job_id` | `Job` (full listing for the detail card); 404 unknown id |
| `POST /analyzer/run` | M5 | multipart form: `github_username?`, `linkedin_text?`, `linkedin_export?` (PDF/TXT, max 5 MB), `portfolio_url?` (the user's own public site, read with up to 3 same-site project/about pages); at least one source | `AnalyzerReport`: `report_id`, `anomalies[]` (`Anomaly`), `integrity_score` (0-100 or null), `clusters[]` (`{name, sources[], members[], mention_count}`), `sources` (skill count per source, e.g. `{cv: 12, github: 7, linkedin: 8}`; a key is absent when that source was not given), `github_username`, `target_role` + `match` (the target-role gap recomputed with the merged skills, with `evidenced_pct`; null when no target role is set). Also saved on the profile: `anomalies`, `integrity_score`, `evidence_sources` (the sources checked), `skills` (each CV skill tagged with the sources that back it, plus the skills the CV omits: LinkedIn skills and GitHub languages that are at least 20 % of the code, the missed-strength bar; repo topics are never added) and, when a target role is set, the refreshed `gap`. A later `POST /profile/cv` or `DELETE /profile` forgets the reports. 409 no CV, 422 no source, 404 unknown GitHub user, 502 GitHub or LLM failure |
| `GET /analyzer/report` | M5 | query `report_id` (default: latest) | `AnalyzerReport`; 404 if none |
| `GET /health` | M5 | none | `{status: "ok", llm_provider, embed_provider, data: {roles, jobs, resources}}` (counts, or null when a file is missing) |
| `GET /built-with` | M5 | none | `list[{name, kind (model / api / dataset / library), licence, url}]` from `backend/built_with.py` |
| `POST /interview/start` | M3 | `{role?, count?}` (role defaults to the profile's target role) | `list[InterviewQuestion]` |
| `POST /interview/answer` | M3 | multipart: `question_id`, `transcript`, `duration_s` (0 = typed), `samples` (JSON `list[NonVerbalSample]`, `[]` = camera off), optional `audio` file | `AnswerResult` |
| `GET /interview/report` | M3 | none (also written to `Profile.interview`) | `InterviewReport` |

## Errors

| Status | Meaning |
|---|---|
| 404 | Unknown role or job id |
| 409 | `/career/*` called before a CV was uploaded |
| 413 | CV file larger than 5 MB |
| 422 | Unsupported or unreadable CV file, missing `role`, or invalid parameters |
| 502 | The LLM provider failed or returned something invalid |
| 503 | A dataset file (`data/roles.json` etc.) is missing or malformed; the message names it |

## `POST /chat` events

Each event is one line `data: <json>` followed by a blank line. The front end switches on `type`:

| `type` | Fields | Meaning |
|---|---|---|
| `open_map` | `radius_km`, `keyword` (or null) | Show the job map with this filter |
| `open_career_map` | `role` | Show the career map for the role |
| `open_interview` | `role` | Start the mock interview |
| `text` | `delta` | Next piece of the answer; append to the message |
| `done` | none | End of the answer |
| `error` | `message` | The answer failed; show the message |

Action events (`open_*`) arrive before the text of the answer.

## Wiring (M5, `backend/main.py`)

```python
from backend.api import analyzer, career, chat, jobs, profile
app.include_router(profile.router)
app.include_router(career.router)
app.include_router(chat.router)
app.include_router(jobs.router)
app.include_router(analyzer.router)
# backend.api.interview (M3) is registered when the module exists.
```

Run with `uvicorn backend.main:app --reload`. CORS origins come from `CORS_ORIGINS` (default: the Vite dev server).

Python dependencies used by M1's code: `pydantic`, `fastapi`, `uvicorn`, `python-multipart`, `anthropic`, `openai`,
`sentence-transformers`, `requests`, `pdfplumber`, `python-docx`. For tests also `pytest` and `httpx`.
