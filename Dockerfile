# ---------- Stage 1: build frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: backend runtime ----------
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && pip install --no-cache-dir gunicorn

COPY backend/ /app/backend/
COPY frontend/public/ /app/frontend/public/
COPY --from=frontend-build /app/frontend/build /app/frontend/build

EXPOSE 8080
CMD ["sh", "-c", "gunicorn --chdir backend -w ${GUNICORN_WORKERS:-2} -k gthread --threads ${GUNICORN_THREADS:-4} -b 0.0.0.0:${PORT:-8080} app:app"]
