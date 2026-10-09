# Prompt index

Every prompt lives in `backend/prompts/` as a readable `.md` file. Each row says what the prompt returns.

| Prompt | Owner | Used by | Returns |
|---|---|---|---|
| `extract_skills.md` | M1 | `services/extractor.py` | `ExtractedCV`: skills with quoted evidence, projects, experience |
