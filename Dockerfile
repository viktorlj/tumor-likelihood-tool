FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir . && rm -rf /root/.cache

# Copy application code and data
COPY app/ app/
COPY data/ data/
COPY static/ static/
COPY templates/ templates/

# Clean macOS metadata files if present
RUN find . -name '._*' -delete 2>/dev/null; true

# Cloud Run sets $PORT; default to 8000 for local dev
ENV PORT=8000
EXPOSE ${PORT}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
