"""Single source of truth for everything CareerLens is built with (rulebook §8 and §11).

`GET /built-with` serves this list, and `ACKNOWLEDGEMENTS.md` is generated from it:

    python -m backend.built_with > ACKNOWLEDGEMENTS.md

Keep the two in sync by regenerating the markdown after editing this list (test_main.py checks that
every entry here is named in ACKNOWLEDGEMENTS.md).
"""
from __future__ import annotations

from typing import Literal, TypedDict

Kind = Literal["model", "api", "dataset", "library"]


class BuiltWith(TypedDict):
    name: str
    kind: Kind
    licence: str
    url: str
    note: str


def _item(name: str, kind: Kind, licence: str, url: str, note: str = "") -> BuiltWith:
    return {"name": name, "kind": kind, "licence": licence, "url": url, "note": note}


BUILT_WITH: list[BuiltWith] = [
    # ---- models
    _item("Claude API (Anthropic)", "model", "Commercial API, Anthropic usage policy", "https://www.anthropic.com/api",
          "Default LLM: skill extraction, roadmap, STAR rubric, anomaly fixes, chatbot (LLM_PROVIDER=anthropic)"),
    _item("DeepSeek API", "model", "Commercial API, DeepSeek terms of use", "https://api-docs.deepseek.com/",
          "Low-cost LLM via its OpenAI-compatible API (LLM_PROVIDER=deepseek)"),
    _item("GroqCloud API", "model", "Commercial API with a free tier, Groq terms of use", "https://console.groq.com/docs",
          "Free-tier LLM (gpt-oss-120b) and Whisper transcription via its OpenAI-compatible API (LLM_PROVIDER=groq)"),
    _item("xAI Grok API", "model", "Commercial API, xAI terms of service", "https://docs.x.ai/",
          "Alternative LLM via its OpenAI-compatible API (LLM_PROVIDER=grok)"),
    _item("OpenAI API", "model", "Commercial API, OpenAI usage policies", "https://platform.openai.com/",
          "Alternative LLM and text-embedding-3-small embeddings (LLM_PROVIDER=openai, EMBED_PROVIDER=openai)"),
    _item("Ollama", "model", "MIT (runtime); model licences vary (llama3.2: Llama 3.2 Community License)", "https://ollama.com/",
          "Local LLM fallback when no API key or no internet (LLM_PROVIDER=ollama)"),
    _item("sentence-transformers/all-MiniLM-L6-v2", "model", "Apache-2.0", "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2",
          "Default local embedding model (384-dim) for skill matching, reconciliation and interview relevance"),
    _item("MediaPipe Tasks Vision (Face Landmarker, Pose Landmarker)", "model", "Apache-2.0", "https://ai.google.dev/edge/mediapipe/solutions/vision",
          "Pre-trained landmarkers running in the browser; only geometric metrics leave the device"),
    _item("Whisper (OpenAI)", "model", "MIT (open-source weights); Whisper API is a commercial API", "https://github.com/openai/whisper",
          "Final accurate interview transcript (API or faster-whisper locally)"),
    # ---- APIs
    _item("GitHub REST API", "api", "GitHub Terms of Service; 60 req/h unauthenticated, 5000 with a token", "https://docs.github.com/en/rest",
          "Repos, languages, topics, READMEs and commit counts for the user's own username only"),
    _item("Nominatim / OpenStreetMap", "api", "ODbL (data); Nominatim usage policy (1 req/s, cached)", "https://nominatim.org/release-docs/latest/api/Overview/",
          "Geocoding of job addresses at dataset build time (scripts/geocode.py)"),
    _item("Web Speech API", "api", "W3C Community Group specification; browser built-in", "https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API",
          "Live interview transcript in the browser, no backend"),
    _item("OpenStreetMap tiles", "api", "ODbL data; OSMF tile usage policy", "https://operations.osmfoundation.org/policies/tiles/",
          "Map tiles for the job map"),
    # ---- datasets
    _item("ESCO (European Skills, Competences, Qualifications and Occupations)", "dataset", "Creative Commons BY 4.0", "https://esco.ec.europa.eu/",
          "Basis for the role skill profiles in data/roles.json"),
    _item("O*NET OnLine", "dataset", "Creative Commons BY 4.0 (U.S. Department of Labor)", "https://www.onetonline.org/",
          "Basis for the role skill profiles in data/roles.json"),
    _item("CareerLens roles.json", "dataset", "MIT (this repo); derived from ESCO and O*NET", "data/roles.json",
          "20-30 target roles with weighted skills, curated by M5"),
    _item("CareerLens jobs.json", "dataset", "MIT (this repo); public postings with source URLs or labelled synthetic", "data/jobs.json",
          "150-300 geocoded listings for Karachi, Lahore and Islamabad; synthetic entries carry synthetic: true"),
    _item("CareerLens resources.json", "dataset", "MIT (this repo); links to third-party free courses", "data/resources.json",
          "Whitelist of free learning links; the roadmap may only cite these URLs"),
    _item("freeCodeCamp", "dataset", "BSD-3-Clause (curriculum CC BY-SA 4.0)", "https://www.freecodecamp.org/",
          "Resource source in data/resources.json"),
    _item("Kaggle Learn", "dataset", "Apache-2.0 (course notebooks)", "https://www.kaggle.com/learn",
          "Resource source in data/resources.json"),
    _item("MIT OpenCourseWare", "dataset", "CC BY-NC-SA 4.0", "https://ocw.mit.edu/",
          "Resource source in data/resources.json"),
    _item("Google Skillshop", "dataset", "Free courses, Google terms", "https://skillshop.withgoogle.com/",
          "Resource source in data/resources.json"),
    _item("Khan Academy", "dataset", "CC BY-NC-SA 3.0 (content)", "https://www.khanacademy.org/",
          "Resource source in data/resources.json"),
    _item("Demo persona 'Sara Ahmed' (demo/)", "dataset", "MIT (this repo); fully synthetic", "demo/README.md",
          "Synthetic CV, LinkedIn export and cached GitHub data with three planted anomalies"),
    # ---- backend libraries
    _item("FastAPI", "library", "MIT", "https://fastapi.tiangolo.com/", "Backend web framework"),
    _item("Uvicorn", "library", "BSD-3-Clause", "https://www.uvicorn.org/", "ASGI server"),
    _item("Pydantic", "library", "MIT", "https://docs.pydantic.dev/", "Schemas and structured-output validation"),
    _item("pdfplumber", "library", "MIT", "https://github.com/jsvine/pdfplumber", "CV and LinkedIn-export PDF text extraction"),
    _item("python-docx", "library", "MIT", "https://github.com/python-openxml/python-docx", "DOCX CV text extraction"),
    _item("requests", "library", "Apache-2.0", "https://requests.readthedocs.io/", "GitHub API, Nominatim and Ollama HTTP calls"),
    _item("sentence-transformers", "library", "Apache-2.0", "https://www.sbert.net/", "Local embeddings"),
    _item("anthropic (Python SDK)", "library", "MIT", "https://github.com/anthropics/anthropic-sdk-python", "Claude API client"),
    _item("openai (Python SDK)", "library", "Apache-2.0", "https://github.com/openai/openai-python", "OpenAI API client"),
    _item("reportlab", "library", "BSD-3-Clause", "https://www.reportlab.com/opensource/", "Generates the demo PDFs (scripts/make_demo_files.py)"),
    _item("pytest", "library", "MIT", "https://pytest.org/", "Backend tests"),
    _item("Ruff", "library", "MIT", "https://docs.astral.sh/ruff/", "Linting in CI"),
    # ---- frontend libraries
    _item("React", "library", "MIT", "https://react.dev/", "Frontend UI"),
    _item("Vite", "library", "MIT", "https://vitejs.dev/", "Frontend build tool"),
    _item("TypeScript", "library", "Apache-2.0", "https://www.typescriptlang.org/", "Frontend language"),
    _item("Tailwind CSS", "library", "MIT", "https://tailwindcss.com/", "Styling"),
    _item("Recharts", "library", "MIT", "https://recharts.org/", "Gauges and radar charts"),
    _item("Zustand", "library", "MIT", "https://github.com/pmndrs/zustand", "Profile store persisted to local storage"),
    _item("Leaflet / react-leaflet", "library", "BSD-2-Clause (Leaflet), Hippocratic 2.1 (react-leaflet)", "https://leafletjs.com/", "Job map"),
    _item("@mediapipe/tasks-vision", "library", "Apache-2.0", "https://www.npmjs.com/package/@mediapipe/tasks-vision", "Browser-side landmark detection"),
    _item("Vitest", "library", "MIT", "https://vitest.dev/", "Frontend tests"),
]


def as_markdown() -> str:
    """Render ACKNOWLEDGEMENTS.md from BUILT_WITH."""
    kinds: list[tuple[Kind, str]] = [
        ("model", "Models"),
        ("api", "APIs and web services"),
        ("dataset", "Datasets and data sources"),
        ("library", "Libraries"),
    ]
    lines = [
        "# Acknowledgements",
        "",
        "Every model, API, dataset source and library CareerLens is built with, with its licence and link (rulebook §8 and §11).",
        "This file is generated from `backend/built_with.py` (`python -m backend.built_with > ACKNOWLEDGEMENTS.md`), which also",
        "serves `GET /built-with` for the in-app \"Built with\" page. Edit the Python list, then regenerate.",
        "",
        "Licence texts of third-party components remain with their authors; CareerLens itself is MIT (see `LICENSE`).",
        "",
    ]
    for kind, title in kinds:
        lines += [f"## {title}", "", "| Name | Licence | Link | Used for |", "|---|---|---|---|"]
        for item in BUILT_WITH:
            if item["kind"] != kind:
                continue
            url = item["url"]
            link = f"[{url}]({url})" if url.startswith("http") else f"`{url}`"
            lines.append(f"| {item['name']} | {item['licence']} | {link} | {item['note']} |")
        lines.append("")
    lines += [
        "## Pre-existing work",
        "",
        "Everything prepared before the AICON'26 build period is listed with dates in `DISCLOSURES.md`.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    print(as_markdown(), end="")
