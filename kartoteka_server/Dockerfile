# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements from nested dir (context is root)
COPY kartoteka_server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY kartoteka_server/ .

# Copy data files
COPY data/tcg_sets.json .
COPY data/tcg_sets_jp.json .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
