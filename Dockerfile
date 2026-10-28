FROM node:24-alpine AS frontend
WORKDIR /build
RUN npm install -g pnpm@12.6.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 libportaudio2 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r backend/requirements.txt
ARG INCLUDE_TRAINING=0
COPY ai/requirements.txt /app/ai/requirements.txt
RUN if [ "$INCLUDE_TRAINING" = "1" ]; then pip install -r ai/requirements.txt; fi
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/
COPY models/ /app/models/
RUN python scripts/download_models.py
COPY ai/ /app/ai/
COPY --from=frontend /build/dist/ /app/frontend/dist/
RUN useradd --uid 10001 --create-home appuser && mkdir -p /app/data/tmp /app/data/datasets /app/ai/runs && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn","app.main:app","--app-dir","backend","--host","0.0.0.0","--port","8000","--ws-max-size","2097152"]
