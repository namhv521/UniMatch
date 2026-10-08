from __future__ import annotations

import hmac
import logging
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.serving import MatchingService, ServiceError

from .schemas import FeedbackRequest, LoginRequest, RecommendRequest, SimulateRequest
from .storage import PostgresStorage, SQLiteFeedbackStore, snapshot_identity

COOKIE_NAME = "kltn_session"
LOGGER = logging.getLogger(__name__)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"status": "error", "error": {"code": code, "message": message}}, status_code=status)


def _benchmark_path(product_root: Path) -> Path:
    return product_root / "outputs/benchmarks/current-validation.json"


class Sessions:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._values[token] = time.time() + self.ttl_seconds
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            expiry = self._values.get(token)
            if expiry is None or expiry <= now:
                self._values.pop(token, None)
                return False
            return True

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._values.pop(token, None)


def create_app(
    *,
    root: str | Path | None = None,
    runtime_dir: str | Path | None = None,
    frontend_dir: str | Path | None = None,
    storage: Any | None = None,
) -> FastAPI:
    product_root = Path(root) if root is not None else Path(__file__).parents[2]
    try:
        service: MatchingService | None = MatchingService(product_root)
    except ServiceError as exc:
        LOGGER.warning("serving_initialization_failed correlation_id=%s exception=%s cause=%s", secrets.token_hex(8), type(exc).__name__, type(exc.__cause__).__name__)
        service = None
    active_snapshot_hash = snapshot_identity(service.provenance) if service is not None else None
    sessions = Sessions(max(60, int(os.getenv("KLTN_SESSION_TTL_SECONDS", "28800"))))
    if storage is None:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            storage = PostgresStorage(
                database_url,
                product_root / "database/schema.sql",
                schema_name=os.getenv("KLTN_DATABASE_SCHEMA", "public"),
            )
        else:
            storage = SQLiteFeedbackStore(
                Path(runtime_dir) if runtime_dir is not None else product_root / "outputs/runtime"
            )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        storage.initialize(service)
        yield

    app = FastAPI(
        title="KLTN Matching API", version="1.0.0", docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )
    app.state.service = service
    app.state.sessions = sessions
    app.state.storage = storage

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            expected = urlsplit(str(request.base_url))
            allowed = {f"{expected.scheme}://{expected.netloc}"}
            configured = os.getenv("KLTN_ALLOWED_ORIGIN")
            if configured:
                allowed.update(value.strip().rstrip("/") for value in configured.split(",") if value.strip())
            if origin is None or origin.rstrip("/") not in allowed:
                return _error(403, "origin_rejected", "Request origin is not allowed")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return _error(422, "validation_error", "Invalid request")

    @app.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        return _error(400, "service_error", str(exc))

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        correlation_id = secrets.token_hex(8)
        LOGGER.error("request_failed correlation_id=%s exception=%s", correlation_id, type(_exc).__name__)
        return JSONResponse(
            {
                "status": "error",
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed",
                    "correlation_id": correlation_id,
                },
            },
            status_code=500,
        )

    def require_session(request: Request) -> None:
        if not sessions.valid(request.cookies.get(COOKIE_NAME)):
            raise HTTPException(status_code=401, detail="authentication_required")

    def require_service() -> MatchingService:
        if service is None:
            raise HTTPException(status_code=503, detail="service_unavailable")
        return service

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        if exc.status_code == 401:
            return _error(401, "authentication_required", "Authentication required")
        if exc.status_code == 503:
            return _error(503, "service_unavailable", "Serving artifacts are unavailable")
        if exc.status_code == 409:
            return _error(409, "benchmark_unverified", "Benchmark provenance is not verified")
        return _error(exc.status_code, "request_rejected", "Request rejected")

    def health_data() -> dict[str, object]:
        if service is None:
            return {
                "status": "degraded",
                "version": "1.0.0",
                "data_loaded": False,
                "quality_ready": False,
                "total_advisors": 0,
                "available_models": [],
            }
        catalog = service.catalog()
        quality_ready = bool(catalog["quality"]["ready"])
        return {
            "status": "healthy" if quality_ready else "degraded",
            "version": "1.0.0",
            "data_loaded": True,
            "quality_ready": quality_ready,
            "total_advisors": len(service.advisors),
            "available_models": [
                item["algorithm"] for item in catalog["models"] if item["status"] != "invalid"
            ],
        }

    @app.get("/health")
    @app.get("/api/v1/health")
    def health():
        return health_data()

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest, response: Response):
        email = os.getenv("KLTN_LOGIN_EMAIL")
        password = os.getenv("KLTN_LOGIN_PASSWORD")
        if not email or not password:
            return _error(503, "auth_not_configured", "Authentication is not configured")
        valid = hmac.compare_digest(payload.email.encode(), email.encode()) & hmac.compare_digest(
            payload.password.encode(), password.encode()
        )
        if not valid:
            return _error(401, "invalid_credentials", "Invalid credentials")
        token = sessions.create()
        response.set_cookie(
            COOKIE_NAME,
            token,
            max_age=sessions.ttl_seconds,
            httponly=True,
            secure=_bool_env("KLTN_COOKIE_SECURE", True),
            samesite="strict",
            path="/",
        )
        return {"status": "success", "data": {"authenticated": True, "user": {"display_name": os.getenv("KLTN_DISPLAY_NAME", "Người dùng cục bộ")}}}

    @app.get("/api/v1/auth/session")
    def session(request: Request):
        authenticated = sessions.valid(request.cookies.get(COOKIE_NAME))
        return {
            "authenticated": authenticated,
            "user": {"display_name": os.getenv("KLTN_DISPLAY_NAME", "Người dùng cục bộ")} if authenticated else None,
        }

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response):
        sessions.revoke(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=_bool_env("KLTN_COOKIE_SECURE", True))
        return {"status": "success", "data": {"authenticated": False}}

    @app.get("/api/v1/catalog", dependencies=[Depends(require_session)])
    def catalog():
        available = require_service()
        return {"status": "success", "data": available.catalog()}

    @app.get("/api/v1/datasets/{name}", dependencies=[Depends(require_session)])
    def dataset(name: str):
        available = require_service()
        return {"status": "success", "data": available.dataset(name)}

    @app.post("/api/v1/simulate", dependencies=[Depends(require_session)])
    def simulate(payload: SimulateRequest):
        available = require_service()
        result = available.simulate(payload.mode, payload.algorithm, payload.dataset, payload.seed)
        storage.add_run(
            endpoint="simulate", mode=payload.mode, algorithm=payload.algorithm,
            dataset=payload.dataset, seed=payload.seed,
            snapshot_hash=active_snapshot_hash, result=result,
        )
        return {"status": "success", "data": result}

    @app.post("/api/v1/allocate", dependencies=[Depends(require_session)])
    def allocate(payload: SimulateRequest):
        available = require_service()
        result = available.simulate(payload.mode, payload.algorithm, payload.dataset, payload.seed)
        storage.add_run(
            endpoint="allocate", mode=payload.mode, algorithm=payload.algorithm,
            dataset=payload.dataset, seed=payload.seed,
            snapshot_hash=active_snapshot_hash, result=result,
        )
        return {"status": "success", "data": result}

    @app.post("/api/v1/recommend", dependencies=[Depends(require_session)])
    def recommend(payload: RecommendRequest):
        available = require_service()
        return {"status": "success", "data": available.recommend(payload.title, payload.top_k)}

    @app.get("/api/v1/results/summary", dependencies=[Depends(require_session)])
    @app.get("/api/v1/benchmark/summary", dependencies=[Depends(require_session)])
    def results_summary():
        available = require_service()
        benchmark = _benchmark_path(product_root)
        if benchmark.is_file():
            artifact = json_load(benchmark)
            provenance = artifact.get("provenance", {})
            expected = {
                "dataset_hash": available.provenance["dataset_sha256"],
                "feature_hash": available.provenance["feature_sha256"],
                "split_hash": available.provenance["split_sha256"],
                "advisor_mapping_hash": available.provenance["advisor_order_sha256"],
                "capacity_policy": "uniform-ceiling-experimental-v1",
                "split": "validation",
            }
            if (
                artifact.get("schema_version") != "1.0"
                or artifact.get("split") != "validation"
                or artifact.get("students") != len(available.split["indices"]["validation"])
                or artifact.get("advisors") != len(available.advisors)
                or any(provenance.get(key) != value for key, value in expected.items())
            ):
                raise HTTPException(status_code=409, detail="benchmark_unverified")
            data = {
                key: artifact[key]
                for key in (
                    "schema_version", "created_at", "scope", "split", "students", "advisors", "seeds",
                    "provenance", "summary", "promotion", "selected_engine", "selection_reason", "limitations",
                    "evaluated_checkpoints",
                )
                if key in artifact
            }
        else:
            data = {
                "status": "not_evaluated",
                "message": "Comparable five-seed RL benchmark is not available",
                "models": available.registry.catalog(),
            }
        return {"status": "success", "data": data}

    @app.post("/api/v1/feedback", dependencies=[Depends(require_session)])
    def store_feedback(payload: FeedbackRequest):
        storage.add_feedback(
            payload,
            snapshot_hash=active_snapshot_hash,
        )
        return {"status": "success", "data": {"stored": True}}

    static = Path(frontend_dir) if frontend_dir is not None else product_root / "frontend/dist"
    if not static.is_dir() and (product_root / "frontend/index.html").is_file():
        static = product_root / "frontend"
    if static.is_dir() and (static / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


def json_load(path: Path) -> object:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


app = create_app()
