"""Container entrypoint supporting both Render production and local Docker Compose."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.routing import Route


def create_app():
    if os.environ.get('UNIMATCH_DEPLOYMENT') == 'production':
        from .production import create_app as create_production_app

        return create_production_app()

    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

    from .portal_database import Database, RecordStore, database_location
    from .rebuild_assistant_api import create_app as create_api

    root = Path(__file__).resolve().parents[2]
    runtime = Path(os.environ.get('UNIMATCH_RUNTIME', '/tmp/unimatch'))
    runtime.mkdir(parents=True, exist_ok=True)

    outputs_dir = root / 'outputs'
    strict_bundle = outputs_dir / 'semester_rl_20261111_trusted_year_github'
    if strict_bundle.is_dir():
        from src.serving.semester_catalog import load_catalog

        service, assistant = load_catalog(outputs_dir, runtime / 'proposals')
    else:
        from src.serving.rebuild_service import RebuildService

        service = RebuildService.from_artifacts(root / 'data_rebuild' / 'v1', runtime_dir=runtime / 'proposals')
        assistant = None

    database = Database(database_location())
    store = RecordStore(database)
    snapshot_id = service.versions.get('github_bundle_sha256') or service.versions.get('encoder_sha256') or 'local-container'
    store.catalog(snapshot_id, service.advisors, service.versions)
    service.record_store = store

    app = create_api(service=service, assistant=assistant, token='', frontend_dir=root / 'frontend' / 'dist')
    app.state.record_store = store

    async def readiness(_request):
        try:
            await run_in_threadpool(store.health)
        except Exception:
            return JSONResponse({'status': 'degraded', 'storage': 'unavailable', 'data_loaded': False}, status_code=503)
        return JSONResponse({
            'status': 'ready',
            'storage': database.backend,
            'data_loaded': True,
            'advisors': len(service.advisors),
            'algorithms': sorted(service.models),
            'checkpoint_versions': list(service.checkpoint_versions),
        })

    app.router.routes[:] = [route for route in app.router.routes if getattr(route, 'path', None) != '/health']
    app.router.routes.insert(0, Route('/health', readiness, methods=['GET']))
    return app
