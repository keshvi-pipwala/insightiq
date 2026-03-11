FROM python:3.11-slim

WORKDIR /app

# System deps needed for chromadb + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-bake the sentence-transformer model into the image so first
# startup is fast (no download on cold start)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Railway provides a writable /tmp; use it for SQLite + ChromaDB
# (Railway's filesystem is ephemeral — for persistence attach a Volume
#  and set DATA_DIR env var to the mount path)
RUN mkdir -p /app/data

EXPOSE 8000

# Railway injects $PORT; fall back to 8000 for local Docker
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
