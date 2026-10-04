# Lightweight Python 3.11 image optimized for Render 512MB RAM free tier
FROM python:3.11-slim

# Avoid writing .pyc files & buffer output for fast logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend code
COPY backend/app /app/backend/app
COPY frontend /app/frontend

ENV PYTHONPATH=/app/backend

# Render exposes PORT env var
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
