"""Small shared SQL store: SQLite locally, PostgreSQL for production."""
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src.data_pipeline.review_decisions import record_hash

ROOT = Path(__file__).resolve().parents[2]
_SQL_STRING_OR_PARAM = re.compile(r"'(?:''|[^'])*'|\?")


def _to_postgres_sql(query: str) -> str:
    """Safely translate SQLite `?` placeholders into psycopg `%s` without corrupting literals."""
    escaped = query.replace('%', '%%')
    return _SQL_STRING_OR_PARAM.sub(lambda m: '%s' if m.group(0) == '?' else m.group(0), escaped)


def database_location(default=None):
    return os.environ.get('UNIMATCH_DATABASE_URL') or os.environ.get('DATABASE_URL') or str(
        default or os.environ.get('UNIMATCH_AUTH_DB', ROOT/'data_rebuild/runtime/portal.sqlite3'))


class Connection:
    def __init__(self, connection, postgres):
        self.connection, self.postgres = connection, postgres

    def execute(self, query, params=()):
        sql = _to_postgres_sql(query) if self.postgres else query
        return self.connection.execute(sql, params)

    def executescript(self, script):
        for statement in script.split(';'):
            cleaned = '\n'.join(
                line for line in statement.splitlines()
                if not line.lstrip().startswith('--')
            ).strip()
            if cleaned:
                self.execute(cleaned)


class Database:
    def __init__(self, location):
        self.location = str(location)
        self.postgres = self.location.startswith(('postgres://', 'postgresql://'))
        self._pool = None
        if self.postgres:
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
                self._pool = ConnectionPool(
                    self.location,
                    min_size=1,
                    max_size=6,
                    kwargs={'connect_timeout': 15, 'row_factory': dict_row},
                    configure=lambda conn: conn.execute('SET search_path TO unimatch_portal'),
                )
            except ImportError:
                self._pool = None
        else:
            Path(self.location).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if self.postgres:
                db.execute('CREATE SCHEMA IF NOT EXISTS unimatch_portal')
                db.execute('SET search_path TO unimatch_portal')
            db.executescript((ROOT/'database/portal.sql').read_text(encoding='utf-8'))

    @contextmanager
    def connect(self):
        if self.postgres and self._pool is not None:
            with self._pool.connection() as connection:
                connection.execute('SET search_path TO unimatch_portal')
                with connection:
                    yield Connection(connection, True)
            return
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            connection = psycopg.connect(self.location, connect_timeout=15, row_factory=dict_row)
            connection.execute('SET search_path TO unimatch_portal')
        else:
            connection = sqlite3.connect(self.location, timeout=15)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
        try:
            with connection:
                yield Connection(connection, self.postgres)
        finally:
            connection.close()


class RecordStore:
    def __init__(self, database):
        self.database = database

    def put(self, kind, key, body):
        with self.database.connect() as db:
            db.execute('INSERT INTO records(kind,record_key,scope_hash,body) VALUES (?,?,?,?) '
                       'ON CONFLICT(kind,record_key) DO NOTHING',
                       (kind, key, body['identity']['scope_hash'], json.dumps(body, ensure_ascii=False, allow_nan=False)))

    def get(self, kind, key, scope_hash):
        with self.database.connect() as db:
            row = db.execute('SELECT body FROM records WHERE kind=? AND record_key=? AND scope_hash=?',
                             (kind, key, scope_hash)).fetchone()
        if not row:
            raise ValueError('cohort_not_found' if kind == 'cohorts' else 'run_not_found')
        return json.loads(row['body'])

    def catalog(self, snapshot, advisors, versions):
        digest = record_hash({'advisors': advisors, 'versions': versions})
        with self.database.connect() as db:
            db.execute('INSERT INTO catalogs(snapshot,payload_hash,metadata) VALUES (?,?,?) ON CONFLICT(snapshot) DO NOTHING',
                       (snapshot, digest, json.dumps(versions, ensure_ascii=False)))
            row = db.execute('SELECT payload_hash FROM catalogs WHERE snapshot=?', (snapshot,)).fetchone()
            if row['payload_hash'] != digest:
                raise ValueError('catalog_snapshot_conflict')
            for ordinal, advisor in enumerate(advisors):
                db.execute('INSERT INTO advisors(snapshot,advisor_id,ordinal,profile) VALUES (?,?,?,?) '
                           'ON CONFLICT(snapshot,advisor_id) DO NOTHING',
                           (snapshot, advisor['advisor_id'], ordinal, json.dumps(advisor, ensure_ascii=False)))

    def health(self):
        with self.database.connect() as db:
            db.execute('SELECT 1').fetchone()
        return True
