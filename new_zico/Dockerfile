# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app 

# Runtime libs for scientific stack (e.g., scikit-learn)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.txt

# Copy application source
COPY src /app/src

# Use a non-root user
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# GEMINI_API_KEY must be provided at runtime
CMD ["sh", "-c", "uvicorn src.app:app --host 0.0.0.0 --port ${PORT:-7860}"] 