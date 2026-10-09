# CareerLens backend. Build from the REPO ROOT so the data/ and demo/ folders are included:
#
#     docker build -f backend/Dockerfile -t careerlens-api .
#     docker run -p 8000:8000 --env-file .env careerlens-api
#
# render.yaml points Render at this file with dockerContext "." for the same reason.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EMBED_PROVIDER=local \
    EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    HF_HOME=/app/.cache/huggingface \
    PORT=8000

WORKDIR /app

# CPU-only torch first so sentence-transformers does not pull the multi-GB CUDA wheels.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r /app/backend/requirements.txt

# Pre-download the embedding model so the first request after a cold start does not wait on Hugging Face.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY backend /app/backend
COPY data /app/data
COPY demo /app/demo

# Non-root user; the app writes backend/cache/embeddings.json and reads the model cache.
RUN useradd --create-home --uid 1000 careerlens \
    && mkdir -p /app/backend/cache \
    && chown -R careerlens:careerlens /app
USER careerlens

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health')"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
