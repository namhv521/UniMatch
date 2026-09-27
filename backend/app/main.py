"""Local research API; serve only explicitly validated datasets."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.endpoints import router

app = FastAPI(title='KLTN Advisor Matching', version='1.0.0')
app.include_router(router)
static = Path(__file__).parent / 'static'
if (static / 'index.html').exists():
    app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
