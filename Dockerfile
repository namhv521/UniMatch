FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json frontend/build.mjs ./
RUN npm ci --omit=dev
COPY frontend/*.html frontend/*.css frontend/*.js ./
COPY frontend/assets ./assets
RUN npm run check && npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib UNIMATCH_RUNTIME=/tmp/unimatch UNIMATCH_DEPLOYMENT=production
WORKDIR /app
COPY requirements-production.txt ./
RUN pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements-production.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/data_rebuild/runtime /tmp/unimatch \
    && chown -R app:app /app/data_rebuild /tmp/unimatch
COPY src ./src
COPY backend ./backend
COPY database/portal.sql ./database/portal.sql
COPY configs ./configs
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import json,os,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health',timeout=8)); assert data.get('data_loaded') is True"
CMD ["sh", "-c", "exec uvicorn backend.app.production:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
