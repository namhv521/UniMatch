"""SQL persistence and public authentication gates."""
import pytest
from fastapi.testclient import TestClient

from test_phase7_service import service, csv_text


def test_sql_record_survives_store_recreation_and_rejects_other_user(service, tmp_path):
    from backend.app.portal_database import Database, RecordStore
    location = str(tmp_path / 'portal.sqlite3')
    service.record_store = RecordStore(Database(location))
    uploaded = service.validate_students(csv_text([{'student_id': 's1', 'thesis_title': 'Technical thesis'}]), scope='owner')
    service.record_store = RecordStore(Database(location))
    assert service.get_students(uploaded['cohort_id'], scope='owner')[0]['student_id'] == 's1'
    assert not list((service.runtime_dir / 'cohorts').glob('*.json'))
    with pytest.raises(ValueError, match='not_found'):
        service.get_students(uploaded['cohort_id'], scope='other')


def test_public_mode_requires_postgresql_and_https(tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    monkeypatch.setenv('UNIMATCH_DEPLOYMENT', 'production')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('UNIMATCH_DATABASE_URL', raising=False)
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path/'auth.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'https://unimatch.example')
    with pytest.raises(ValueError, match='production_postgresql_required'):
        create_app(frontend_dir=tmp_path)


def test_catalog_is_bound_to_snapshot_and_cannot_silently_change(service, tmp_path):
    from backend.app.portal_database import Database, RecordStore
    store = RecordStore(Database(str(tmp_path/'portal.sqlite3')))
    store.catalog('snapshot', service.advisors, service.versions)
    changed = [dict(row) for row in service.advisors]
    changed[0]['advisor_name'] = 'changed'
    with pytest.raises(ValueError, match='catalog_snapshot_conflict'):
        store.catalog('snapshot', changed, service.versions)
