# REST API

One row per endpoint. Everyone adds their own rows; M1 owns the format and the `/profile` and `/career` rows.
Request and response bodies are the Pydantic models in `backend/schemas/`.

| Route | Owner | Request | Response |
|---|---|---|---|
| `POST /profile/cv` | M1 | multipart CV file (PDF/DOCX), optional `target_role`, `mode` | `Profile` |
| `GET /profile` | M1 | none | `Profile` |
| `GET /career/gap` | M1 | query `role` | `MatchResult` + `list[MarketGap]` |
| `GET /career/roadmap` | M1 | query `role`, optional `pinned_job_id` | `Roadmap` |
| `GET /career/adjacent` | M1 | query `role` | `list[{role, match_pct}]` |
| `POST /chat` | M1 | `{message, history[]}`, streamed response | server-sent events |
| `GET /jobs/nearby` | M5 | query `lat`, `lng`, `radius` | `list[JobMatch]` |
| `POST /analyzer/run` | M5 | `{github_username, linkedin_export?}` | `{report_id}` |
| `GET /analyzer/report` | M5 | query `report_id` | `list[Anomaly]` + integrity score |
| `POST /interview/start` | M3 | `{role}` | `list[InterviewQuestion]` |
| `POST /interview/answer` | M3 | audio + transcript + `list[NonVerbalSample]` | `AnswerResult` |
| `GET /interview/report` | M3 | none | `InterviewReport` |
