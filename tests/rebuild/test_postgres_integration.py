"""Run against a disposable PostgreSQL DB via UNIMATCH_TEST_DATABASE_URL."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from test_phase7_service import service, csv_text

pytestmark = pytest.mark.skipif(not os.environ.get('UNIMATCH_TEST_DATABASE_URL'), reason='disposable PostgreSQL not configured')


def test_postgresql_users_sessions_catalog_and_records(service):
    from backend.app.portal_database import Database, RecordStore
    from backend.app.portal import PortalStore
    database = Database(os.environ['UNIMATCH_TEST_DATABASE_URL'])
    accounts = PortalStore(database)
    subject = uuid.uuid4().hex
    token = accounts.create_session('github', subject, 'Integration user')
    user = accounts.session(token)
    assert user['name'] == 'Integration user'
    assert accounts.session('not-a-token') is None
    first = accounts.create_pending('github', 'verifier')
    assert accounts.consume_pending(first)['provider'] == 'github'
    assert accounts.consume_pending(first) is None
    store = RecordStore(database)
    store.catalog(subject, service.advisors, service.versions)
    service.record_store = store
    upload = service.validate_students(csv_text([{'student_id': subject, 'thesis_title': 'Technical thesis'}]), scope=user['id'])
    service.record_store = RecordStore(Database(os.environ['UNIMATCH_TEST_DATABASE_URL']))
    assert service.get_students(upload['cohort_id'], scope=user['id'])[0]['student_id'] == subject
    with pytest.raises(ValueError, match='not_found'):
        service.get_students(upload['cohort_id'], scope='other-user')


def test_public_https_api_uses_postgres_and_disables_operator_token(service, tmp_path, monkeypatch):
    import hashlib
    from backend.app.portal_database import Database
    database = Database(os.environ['UNIMATCH_TEST_DATABASE_URL'])
    key = uuid.uuid4().hex
    payload = b'technical-fixture'
    sha = hashlib.sha256(payload).hexdigest()
    with database.connect() as db:
        db.execute('INSERT INTO model_bundles(bundle_key,sha256,payload) VALUES (?,?,?)', (key, sha, payload))
    monkeypatch.setenv('UNIMATCH_DEPLOYMENT', 'production')
    monkeypatch.setenv('DATABASE_URL', os.environ['UNIMATCH_TEST_DATABASE_URL'])
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'https://unimatch.example')
    monkeypatch.setenv('UNIMATCH_MODEL_BUNDLE', key)
    monkeypatch.setenv('UNIMATCH_MODEL_BUNDLE_SHA256', sha)
    monkeypatch.setenv('UNIMATCH_RUNTIME', str(tmp_path))
    service.versions['github_bundle_sha256'] = key
    from backend.app import production_release
    monkeypatch.setattr(production_release, 'unpack_release', lambda *a: tmp_path)
    monkeypatch.setattr(production_release, 'load_release', lambda *a: (service, None))
    from backend.app.production import create_app
    app = create_app()
    client = TestClient(app, base_url='https://unimatch.example', client=('203.0.113.1', 443))
    assert client.get('/health').json()['storage'] == 'postgresql'
    assert client.get('/api/rebuild/bootstrap', headers={'Authorization': 'Bearer old-operator-token'}).status_code == 401
    session = app.state.portal_store.create_session('github', uuid.uuid4().hex, 'Browser user')
    client.cookies.set('unimatch_session', session)
    assert client.get('/api/auth/me').status_code == 200
    assert client.get('/api/rebuild/bootstrap').status_code == 200
    assert client.post('/api/rebuild/quotas', json={'student_count': 2, 'advisor_ids': ['a']},
                       headers={'Origin': 'https://evil.example'}).status_code == 403
