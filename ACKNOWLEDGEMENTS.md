# Acknowledgements

Every model, API, dataset source and library CareerLens is built with, with its licence and link (rulebook §8 and §11).
This file is generated from `backend/built_with.py` (`python -m backend.built_with > ACKNOWLEDGEMENTS.md`), which also
serves `GET /built-with` for the in-app "Built with" page. Edit the Python list, then regenerate.

Licence texts of third-party components remain with their authors; CareerLens itself is MIT (see `LICENSE`).

## Models

| Name | Licence | Link | Used for |
|---|---|---|---|
| Claude API (Anthropic) | Commercial API, Anthropic usage policy | [https://www.anthropic.com/api](https://www.anthropic.com/api) | Default LLM: skill extraction, roadmap, STAR rubric, anomaly fixes, chatbot (LLM_PROVIDER=anthropic) |
| DeepSeek API | Commercial API, DeepSeek terms of use | [https://api-docs.deepseek.com/](https://api-docs.deepseek.com/) | Low-cost LLM via its OpenAI-compatible API (LLM_PROVIDER=deepseek) |
| GroqCloud API | Commercial API with a free tier, Groq terms of use | [https://console.groq.com/docs](https://console.groq.com/docs) | Free-tier LLM (gpt-oss-120b) and Whisper transcription via its OpenAI-compatible API (LLM_PROVIDER=groq) |
| xAI Grok API | Commercial API, xAI terms of service | [https://docs.x.ai/](https://docs.x.ai/) | Alternative LLM via its OpenAI-compatible API (LLM_PROVIDER=grok) |
| OpenAI API | Commercial API, OpenAI usage policies | [https://platform.openai.com/](https://platform.openai.com/) | Alternative LLM and text-embedding-3-small embeddings (LLM_PROVIDER=openai, EMBED_PROVIDER=openai) |
| Ollama | MIT (runtime); model licences vary (llama3.2: Llama 3.2 Community License) | [https://ollama.com/](https://ollama.com/) | Local LLM fallback when no API key or no internet (LLM_PROVIDER=ollama) |
| sentence-transformers/all-MiniLM-L6-v2 | Apache-2.0 | [https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Default local embedding model (384-dim) for skill matching, reconciliation and interview relevance |
| MediaPipe Tasks Vision (Face Landmarker, Pose Landmarker) | Apache-2.0 | [https://ai.google.dev/edge/mediapipe/solutions/vision](https://ai.google.dev/edge/mediapipe/solutions/vision) | Pre-trained landmarkers running in the browser; only geometric metrics leave the device |
| Whisper (OpenAI) | MIT (open-source weights); Whisper API is a commercial API | [https://github.com/openai/whisper](https://github.com/openai/whisper) | Final accurate interview transcript (API or faster-whisper locally) |

## APIs and web services

| Name | Licence | Link | Used for |
|---|---|---|---|
| GitHub REST API | GitHub Terms of Service; 60 req/h unauthenticated, 5000 with a token | [https://docs.github.com/en/rest](https://docs.github.com/en/rest) | Repos, languages, topics, READMEs and commit counts for the user's own username only |
| Nominatim / OpenStreetMap | ODbL (data); Nominatim usage policy (1 req/s, cached) | [https://nominatim.org/release-docs/latest/api/Overview/](https://nominatim.org/release-docs/latest/api/Overview/) | Geocoding of job addresses at dataset build time (scripts/geocode.py) |
| Web Speech API | W3C Community Group specification; browser built-in | [https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API) | Live interview transcript in the browser, no backend |
| OpenStreetMap tiles | ODbL data; OSMF tile usage policy | [https://operations.osmfoundation.org/policies/tiles/](https://operations.osmfoundation.org/policies/tiles/) | Map tiles for the job map |

## Datasets and data sources

| Name | Licence | Link | Used for |
|---|---|---|---|
| ESCO (European Skills, Competences, Qualifications and Occupations) | Creative Commons BY 4.0 | [https://esco.ec.europa.eu/](https://esco.ec.europa.eu/) | Basis for the role skill profiles in data/roles.json |
| O*NET OnLine | Creative Commons BY 4.0 (U.S. Department of Labor) | [https://www.onetonline.org/](https://www.onetonline.org/) | Basis for the role skill profiles in data/roles.json |
| CareerLens roles.json | MIT (this repo); derived from ESCO and O*NET | `data/roles.json` | 20-30 target roles with weighted skills, curated by M5 |
| CareerLens jobs.json | MIT (this repo); public postings with source URLs or labelled synthetic | `data/jobs.json` | 150-300 geocoded listings for Karachi, Lahore and Islamabad; synthetic entries carry synthetic: true |
| CareerLens resources.json | MIT (this repo); links to third-party free courses | `data/resources.json` | Whitelist of free learning links; the roadmap may only cite these URLs |
| freeCodeCamp | BSD-3-Clause (curriculum CC BY-SA 4.0) | [https://www.freecodecamp.org/](https://www.freecodecamp.org/) | Resource source in data/resources.json |
| Kaggle Learn | Apache-2.0 (course notebooks) | [https://www.kaggle.com/learn](https://www.kaggle.com/learn) | Resource source in data/resources.json |
| MIT OpenCourseWare | CC BY-NC-SA 4.0 | [https://ocw.mit.edu/](https://ocw.mit.edu/) | Resource source in data/resources.json |
| Google Skillshop | Free courses, Google terms | [https://skillshop.withgoogle.com/](https://skillshop.withgoogle.com/) | Resource source in data/resources.json |
| Khan Academy | CC BY-NC-SA 3.0 (content) | [https://www.khanacademy.org/](https://www.khanacademy.org/) | Resource source in data/resources.json |
| Demo persona 'Sara Ahmed' (demo/) | MIT (this repo); fully synthetic | `demo/README.md` | Synthetic CV, LinkedIn export and cached GitHub data with three planted anomalies |

## Libraries

| Name | Licence | Link | Used for |
|---|---|---|---|
| FastAPI | MIT | [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/) | Backend web framework |
| Uvicorn | BSD-3-Clause | [https://www.uvicorn.org/](https://www.uvicorn.org/) | ASGI server |
| Pydantic | MIT | [https://docs.pydantic.dev/](https://docs.pydantic.dev/) | Schemas and structured-output validation |
| pdfplumber | MIT | [https://github.com/jsvine/pdfplumber](https://github.com/jsvine/pdfplumber) | CV and LinkedIn-export PDF text extraction |
| python-docx | MIT | [https://github.com/python-openxml/python-docx](https://github.com/python-openxml/python-docx) | DOCX CV text extraction |
| requests | Apache-2.0 | [https://requests.readthedocs.io/](https://requests.readthedocs.io/) | GitHub API, Nominatim and Ollama HTTP calls |
| sentence-transformers | Apache-2.0 | [https://www.sbert.net/](https://www.sbert.net/) | Local embeddings |
| anthropic (Python SDK) | MIT | [https://github.com/anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) | Claude API client |
| openai (Python SDK) | Apache-2.0 | [https://github.com/openai/openai-python](https://github.com/openai/openai-python) | OpenAI API client |
| reportlab | BSD-3-Clause | [https://www.reportlab.com/opensource/](https://www.reportlab.com/opensource/) | Generates the demo PDFs (scripts/make_demo_files.py) |
| pytest | MIT | [https://pytest.org/](https://pytest.org/) | Backend tests |
| Ruff | MIT | [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/) | Linting in CI |
| React | MIT | [https://react.dev/](https://react.dev/) | Frontend UI |
| Vite | MIT | [https://vitejs.dev/](https://vitejs.dev/) | Frontend build tool |
| TypeScript | Apache-2.0 | [https://www.typescriptlang.org/](https://www.typescriptlang.org/) | Frontend language |
| Tailwind CSS | MIT | [https://tailwindcss.com/](https://tailwindcss.com/) | Styling |
| Recharts | MIT | [https://recharts.org/](https://recharts.org/) | Gauges and radar charts |
| Zustand | MIT | [https://github.com/pmndrs/zustand](https://github.com/pmndrs/zustand) | Profile store persisted to local storage |
| Leaflet / react-leaflet | BSD-2-Clause (Leaflet), Hippocratic 2.1 (react-leaflet) | [https://leafletjs.com/](https://leafletjs.com/) | Job map |
| @mediapipe/tasks-vision | Apache-2.0 | [https://www.npmjs.com/package/@mediapipe/tasks-vision](https://www.npmjs.com/package/@mediapipe/tasks-vision) | Browser-side landmark detection |
| Vitest | MIT | [https://vitest.dev/](https://vitest.dev/) | Frontend tests |

## Pre-existing work

Everything prepared before the AICON'26 build period is listed with dates in `DISCLOSURES.md`.
