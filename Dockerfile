# No browser anymore — Card Finder uses haku.cards' JSON API and all fetching is
# plain HTTP, so a slim Python image is enough (small memory = free hosts work).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD gunicorn -k gthread --workers 2 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT:-8080} wsgi:app
