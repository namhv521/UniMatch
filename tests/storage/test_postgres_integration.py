from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from backend.app.storage import PostgresStorage
from src.serving import MatchingService

DSN = os.getenv("KLTN_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="set KLTN_TEST_DATABASE_URL for PostgreSQL integration")
ROOT = Path(__file__).parents[2]


def test_real_postgres_import_is_idempotent_and_isolated() -> None:
    """Catches PostgreSQL dialect/FK errors and duplicate rows on restart."""
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql

    schema_name = f"kltn_test_{uuid.uuid4().hex}"
    with psycopg.connect(DSN) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
    try:
        storage = PostgresStorage(DSN, ROOT / "database/schema.sql", schema_name=schema_name)
        service = MatchingService(ROOT)
        storage.initialize(service)
        storage.initialize(service)
        with psycopg.connect(DSN) as connection:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
            assert connection.execute("SELECT count(*) FROM students").fetchone()[0] == len(service.theses)
            assert connection.execute("SELECT count(*) FROM advisors").fetchone()[0] == len(service.advisors)
            assert connection.execute("SELECT count(*) FROM split_memberships").fetchone()[0] == len(service.theses)
    finally:
        with psycopg.connect(DSN) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))
