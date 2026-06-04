FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads /app/data/repos /app/data/vector_store /app/logs

RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

ENV UPLOAD_DIR=/app/data/uploads
ENV REPO_DIR=/app/data/repos
ENV VECTOR_STORE_DIR=/app/data/vector_store

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
