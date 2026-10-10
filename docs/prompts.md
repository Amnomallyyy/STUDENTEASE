# Prompt index

Every prompt lives in `backend/prompts/` as a readable `.md` file. Each row says what the prompt returns.

| Prompt | Owner | Used by | Returns |
|---|---|---|---|
| `extract_skills.md` | M1 | `services/extractor.py` | `ExtractedCV`: skills with quoted evidence, projects, experience. Output is checked against the CV text afterwards, so skills the CV never mentions are dropped |
| `roadmap.md` | M1 | `services/roadmap.py` | `Roadmap`: up to 4 weeks of tasks. Resource URLs are checked against `data/resources.json`; if the call fails, a deterministic plan is built from the same data |
| `chat_system.md` | M1 | `services/chat.py` | Chatbot system prompt. The user's profile summary is appended on every message; the model answers in text and may call `get_jobs_near_me`, `explain_gap` and `start_mock_interview` |
| `question_gen.md` | M3 | `services/interview/questions.py` | 3 behavioural questions seeded with the user's role, top skills and projects; template questions (still using the user's skills) when the LLM fails |
| `star_rubric.md` | M3 | `services/interview/star.py` | `StarScore`: present / evidence_span / strength 0-3 for Situation, Task, Action, Result. Every quote is checked against the transcript and dropped if it is not there, so a Result cannot be invented; cue-phrase fallback offline |
| `rewrite_star.md` | M3 | `services/interview/rewrite.py` | The user's own answer rewritten into STAR form (their facts, under 200 words); missing parts become bracketed prompts, never invented content |
| `coaching_notes.md` | M4 | `services/interview/nonverbal.py` | 2-3 kind, concrete body-language notes from the per-answer metrics and the transcript; rule-based notes when the LLM fails |
| `anomaly_fix.md` | M5 | `services/evidence/anomalies.py` | For each anomaly one sentence on why it matters to a recruiter and one concrete fix; templated fallback when the LLM fails |
