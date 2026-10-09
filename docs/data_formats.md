# Dataset formats

M5 builds these files (see `scripts/`); M1's code reads them through `backend/services/data.py`. They are validated on
load, and a missing or malformed file produces an error that names the file. Paths can be overridden with the
environment variables `ROLES_PATH`, `JOBS_PATH` and `RESOURCES_PATH`.

## `data/roles.json`

A list of 20-30 roles. Each skill needs a `category`; `weight` is its importance (core skills higher, for example 3 vs 1).

```json
[
  {
    "id": "data-analyst",
    "name": "Data Analyst",
    "skills": [
      {"name": "SQL", "category": "language", "weight": 3, "requirement": "core"},
      {"name": "Tableau", "category": "tool", "weight": 1, "requirement": "preferred"}
    ]
  }
]
```

`category` is one of `language`, `tool`, `framework`, `soft_skill`, `domain`. `requirement` is `core` or `preferred`.

## `data/jobs.json`

A list of 150-300 geocoded listings. `required_skills` is pre-extracted with M1's extractor, using the same skill shape as
above. Set `synthetic: true` for generated listings.

```json
[
  {
    "id": "j17",
    "company": "Example Analytics",
    "title": "Junior Data Analyst",
    "city": "Karachi",
    "lat": 24.8607,
    "lng": 67.0011,
    "requirements_text": "Looking for SQL and Excel...",
    "required_skills": [{"name": "SQL", "category": "language", "weight": 1}],
    "source_url": "https://example.org/jobs/17",
    "synthetic": false
  }
]
```

## `data/resources.json`

The whitelist of free learning links. The roadmap may only cite URLs from this file. Keys are skill names (case is ignored).

```json
{
  "SQL": [
    {"title": "SQL basics (free course)", "url": "https://example.org/sql", "hours": 6}
  ]
}
```

## `data/skill_aliases.json`

Either `{"JS": "JavaScript"}` (alias to name) or `{"JavaScript": ["JS", "Java Script"]}` (name to aliases). Used by
`backend/services/normalize.py`; a small built-in set applies when the file is absent.
