"""Public synthetic contract: no private data or checkpoint is required."""
from fastapi.testclient import TestClient

from backend.app.main import create_app
from src.serving.model_registry import ModelRegistry


def test_clean_checkout_auth_and_degraded_serving(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('KLTN_LOGIN_EMAIL', 'ci@example.test')
    monkeypatch.setenv('KLTN_LOGIN_PASSWORD', 'public-fixture-not-production')
    monkeypatch.setenv('KLTN_COOKIE_SECURE', 'false')
    client = TestClient(create_app(root=tmp_path, runtime_dir=tmp_path/'runtime'))
    assert ModelRegistry(tmp_path).catalog() == []
    assert client.get('/api/v1/health').json()['data_loaded'] is False
    assert 'serving_initialization_failed' in caplog.text
    assert client.get('/api/v1/catalog').status_code == 401
    payload = {'email':'ci@example.test', 'password':'public-fixture-not-production'}
    assert client.post('/api/v1/auth/login', json=payload).status_code == 403
    origin = {'Origin':'http://testserver'}
    assert client.post('/api/v1/auth/login', headers=origin, json=payload).status_code == 200
    assert client.get('/api/v1/auth/session').json()['authenticated'] is True
    assert client.get('/api/v1/catalog').status_code == 503
    assert client.post('/api/v1/auth/logout', headers=origin).status_code == 200
    assert client.get('/api/v1/auth/session').json()['authenticated'] is False
