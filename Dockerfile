# Logistics Exception Investigator — single container (UI + API + pipeline).
#
#   docker compose up --build
#   → http://localhost:8000  (web UI, API, and demo seed all in one place)
#
# One-command pitch demo: `docker compose up -d --build && curl -X POST localhost:8000/demo/seed?case_id=C02`

# ---- stage 1: build the React UI -------------------------------------------
FROM node:20-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ .
RUN npm run build

# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LEI_DATA_DIR=/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# production UI served by the API itself (single port, single container)
COPY --from=web /web/dist ./apps/web/dist

RUN useradd -m appuser && mkdir -p /data && chown -R appuser /data /app
USER appuser

EXPOSE 8000
VOLUME ["/data"]
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
