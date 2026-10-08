from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .schemas import FeedbackRequest


class SQLiteFeedbackStore:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "feedback.sqlite3"

    def initialize(self, _service: Any) -> None:
        pass

    def add_run(self, **_run: Any) -> None:
        pass

    def add_feedback(self, feedback: FeedbackRequest, *, snapshot_hash: str | None) -> None:
        del snapshot_hash
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL, mode TEXT NOT NULL, algorithm TEXT NOT NULL, helpful INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO feedback(created_at, mode, algorithm, helpful) VALUES (?, ?, ?, ?)",
                (int(time.time()), feedback.mode, feedback.algorithm, int(feedback.helpful)),
            )
            connection.execute(
                "DELETE FROM feedback WHERE id NOT IN (SELECT id FROM feedback ORDER BY id DESC LIMIT 10000)"
            )


class PostgresStorage:
    def __init__(
        self,
        database_url: str,
        schema_path: str | Path,
        *,
        schema_name: str = "public",
        connect: Callable[[str], Any] | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema_name):
            raise ValueError("invalid PostgreSQL schema name")
        self.database_url = database_url
        self.schema_path = Path(schema_path)
        self.schema_name = schema_name
        self._connector = connect

    def _connect(self):
        if self._connector is not None:
            return self._connector(self.database_url)
        import psycopg

        return psycopg.connect(self.database_url, connect_timeout=5)

    def _prepare(self, connection) -> None:
        connection.execute(f'SET search_path TO "{self.schema_name}"')

    def initialize(self, service: Any) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            self._prepare(connection)
            connection.execute(schema)
            if service is None:
                return
            provenance = service.provenance
            snapshot_hash = snapshot_identity(provenance)
            connection.execute(
                """
                INSERT INTO snapshots(
                    snapshot_hash, dataset_hash, feature_hash, split_hash, student_order_hash,
                    advisor_order_hash, provenance
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (snapshot_hash) DO UPDATE SET
                    dataset_hash = EXCLUDED.dataset_hash,
                    feature_hash = EXCLUDED.feature_hash,
                    split_hash = EXCLUDED.split_hash,
                    student_order_hash = EXCLUDED.student_order_hash,
                    advisor_order_hash = EXCLUDED.advisor_order_hash,
                    provenance = EXCLUDED.provenance
                """,
                (
                    snapshot_hash,
                    provenance["dataset_sha256"],
                    provenance["feature_sha256"],
                    provenance["split_sha256"],
                    provenance["student_order_sha256"],
                    provenance["advisor_order_sha256"],
                    _json(provenance),
                ),
            )
            memberships = []
            for split_name in ("train", "validation", "test", "future"):
                for position, student_index in enumerate(service.split["indices"][split_name]):
                    memberships.append(
                        (snapshot_hash, service.theses[student_index]["student_id"], split_name, position)
                    )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO students(snapshot_hash, student_id, ordinal, profile)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (snapshot_hash, student_id) DO UPDATE SET
                        ordinal = EXCLUDED.ordinal, profile = EXCLUDED.profile
                    """,
                    [
                        (snapshot_hash, row["student_id"], ordinal, _json(row))
                        for ordinal, row in enumerate(service.theses)
                    ],
                )
                cursor.executemany(
                    """
                    INSERT INTO advisors(snapshot_hash, advisor_id, ordinal, profile)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (snapshot_hash, advisor_id) DO UPDATE SET
                        ordinal = EXCLUDED.ordinal, profile = EXCLUDED.profile
                    """,
                    [
                        (snapshot_hash, row["advisor_id"], ordinal, _json(row))
                        for ordinal, row in enumerate(service.advisors)
                    ],
                )
                cursor.executemany(
                    """
                    INSERT INTO split_memberships(snapshot_hash, student_id, split_name, position)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (snapshot_hash, student_id) DO UPDATE SET
                        split_name = EXCLUDED.split_name, position = EXCLUDED.position
                    """,
                    memberships,
                )

    def add_run(
        self,
        *,
        endpoint: str,
        mode: str,
        algorithm: str,
        dataset: str,
        seed: int,
        snapshot_hash: str,
        result: dict[str, object],
    ) -> None:
        with self._connect() as connection:
            self._prepare(connection)
            connection.execute(
                """
                INSERT INTO simulation_runs(
                    id, snapshot_hash, endpoint, mode, algorithm, dataset, seed, result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(uuid.uuid4()), snapshot_hash, endpoint, mode, algorithm,
                    dataset, seed, _json(result),
                ),
            )

    def add_feedback(self, feedback: FeedbackRequest, *, snapshot_hash: str | None) -> None:
        with self._connect() as connection:
            self._prepare(connection)
            connection.execute(
                """
                INSERT INTO feedback(snapshot_hash, mode, algorithm, helpful)
                VALUES (%s, %s, %s, %s)
                """,
                (snapshot_hash, feedback.mode, feedback.algorithm, feedback.helpful),
            )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def snapshot_identity(provenance: dict[str, str]) -> str:
    canonical = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()
