FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
# Real production server (was the Flask dev server via haku_extractor.py, which
# is single-process and has no protection against a slow request freezing the
# whole app). --workers 1 is required: each worker process would launch its own
# Playwright browsers, multiplying memory. --threads handles concurrency instead.
CMD gunicorn -k gthread --workers 1 --threads 8 --timeout 180 --bind 0.0.0.0:${PORT:-8080} wsgi:app
