FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json frontend/build.mjs ./
RUN npm ci --omit=dev
COPY frontend/index.html frontend/style.css frontend/*.js ./
COPY frontend/assets ./assets
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/data /app/outputs \
    && chown app:app /app/outputs

COPY src ./src
COPY backend ./backend
COPY scripts ./scripts
COPY database ./database
COPY configs ./configs
COPY assets/student-skills-template.xlsx ./assets/student-skills-template.xlsx
COPY run_dashboard.py ./
COPY --from=frontend /build/frontend/dist ./frontend/dist

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5)); assert data.get('data_loaded') is True"
CMD ["python", "run_dashboard.py", "--host", "0.0.0.0", "--port", "8000"]
