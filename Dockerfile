FROM python:3.13-slim

WORKDIR /app

# Install dependencies only (no need to build the package itself)
RUN pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "polars>=1.0.0" "jinja2>=3.1.0"

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
