# Prompt index

Every prompt lives in `backend/prompts/` as a readable `.md` file. Each row says what the prompt returns.

| Prompt | Owner | Used by | Returns |
|---|---|---|---|
| `extract_skills.md` | M1 | `services/extractor.py` | `ExtractedCV`: skills with quoted evidence, projects, experience. Output is checked against the CV text afterwards, so skills the CV never mentions are dropped |
| `roadmap.md` | M1 | `services/roadmap.py` | `Roadmap`: up to 4 weeks of tasks. Resource URLs are checked against `data/resources.json`; if the call fails, a deterministic plan is built from the same data |
| `chat_system.md` | M1 | `services/chat.py` | Chatbot system prompt. The user's profile summary is appended on every message; the model answers in text and may call `get_jobs_near_me`, `explain_gap` and `start_mock_interview` |
| `anomaly_fix.md` | M5 | `services/evidence/anomalies.py` | For each anomaly one sentence on why it matters to a recruiter and one concrete fix; templated fallback when the LLM fails |
