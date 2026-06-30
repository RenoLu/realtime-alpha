# Stage 1 — build the React dashboard
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2 — the Python app image (every service runs from this one image)
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RTA_FRONTEND_DIST=/app/frontend/dist
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[stream,ingest,serve,sentiment,lakehouse]"
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 8000
# compose sets the command per service (ingest / processor / predict / serve)
