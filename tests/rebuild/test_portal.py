"""Portal trust boundaries, with no external authentication requests."""
import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_phase7_service import service, csv_text


def portal(tmp_path, monkeypatch):
    from backend.app.portal import install_portal
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'auth.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'http://testserver')
    app = FastAPI()
    install_portal(app)
    return app, TestClient(app)


def test_missing_provider_configuration_fails_closed(tmp_path, monkeypatch):
    app, client = portal(tmp_path, monkeypatch)
    config = client.get('/api/auth/config').json()
    assert not config['providers']['google']
    assert client.post('/api/auth/start/google', json={'turnstile_token': 'fake'}).status_code == 503
    assert client.get('/api/auth/me').status_code == 401


def test_shared_matching_entrypoint_has_portal_endpoints(tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'auth.sqlite3'))
    app = create_app(token='technical-fixture-long-token', frontend_dir=tmp_path)
    client = TestClient(app)
    assert client.get('/api/auth/config').status_code == 200
    token = app.state.portal_store.create_session('github', '1', 'A')
    client.cookies.set('unimatch_session', token)
    assert client.get('/api/auth/me').status_code == 200


def test_browser_users_cannot_read_each_others_cohorts(service, tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'auth.sqlite3'))
    app = create_app(service=service, token='technical-fixture-long-token', frontend_dir=tmp_path)
    client = TestClient(app)
    client.cookies.set('unimatch_session', app.state.portal_store.create_session('github', 'one', 'A'))
    uploaded = client.post('/api/rebuild/students/validate', json={'csv_text': csv_text([
        {'student_id': 's1', 'thesis_title': 'Technical thesis'}])}).json()
    payload = {'cohort_id': uploaded['cohort_id'], 'advisor_ids': ['a'], 'top_k': 1}
    assert client.post('/api/rebuild/recommend', json=payload).status_code == 200
    client.cookies.set('unimatch_session', app.state.portal_store.create_session('github', 'two', 'B'))
    denied = client.post('/api/rebuild/recommend', json=payload)
    assert denied.status_code == 400 and 'Technical thesis' not in denied.text


def test_session_cookie_is_scoped_and_logout_rejects_cross_origin(tmp_path, monkeypatch):
    app, client = portal(tmp_path, monkeypatch)
    token = app.state.portal_store.create_session('github', '123', 'Student')
    client.cookies.set('unimatch_session', token)
    assert client.get('/api/auth/me').json()['name'] == 'Student'
    assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/logout', headers={'Origin': 'http://testserver'}).status_code == 200
    assert client.get('/api/auth/me').status_code == 401


def test_callback_requires_bound_one_time_state(tmp_path, monkeypatch):
    app, client = portal(tmp_path, monkeypatch)
    assert client.get('/api/auth/callback/github?state=bad&code=x', follow_redirects=False).status_code == 400
    state = app.state.portal_store.create_pending('github', 'verifier')
    client.cookies.set('unimatch_oauth', 'different')
    assert client.get(f'/api/auth/callback/github?state={state}&code=x', follow_redirects=False).status_code == 400


def test_training_requires_authentication_and_binds_active_run(tmp_path, monkeypatch):
    app, client = portal(tmp_path, monkeypatch)
    assert client.get('/api/rebuild/training').status_code == 401
    token = app.state.portal_store.create_session('github', '1', 'A')
    client.cookies.set('unimatch_session', token)
    from types import SimpleNamespace
    app.state.rebuild_service = SimpleNamespace(versions={'selection_run_id': 'wrong'})
    assert client.get('/api/rebuild/training').status_code == 409


def test_training_reports_real_snapshot_without_claiming_convergence(tmp_path, monkeypatch):
    app, client = portal(tmp_path, monkeypatch)
    client.cookies.set('unimatch_session', app.state.portal_store.create_session('github', '1', 'A'))
    from types import SimpleNamespace
    app.state.rebuild_service = SimpleNamespace(versions={'selection_run_id': '20261022T205827Z-16010d68'})
    value = client.get('/api/rebuild/training').json()
    assert value['mode'] == 'saved_experiment'
    assert value['models']['ppo']['trained_steps'] == 131072
    assert value['models']['ppo']['plateau'] is False
    assert value['models']['dqn']['selected_steps'] == 98304
    assert 'C:\\' not in json.dumps(value)


def test_turnstile_and_oauth_exchange_with_bound_state(tmp_path, monkeypatch):
    import httpx
    app, client = portal(tmp_path, monkeypatch)
    for key in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'TURNSTILE_SITE_KEY', 'TURNSTILE_SECRET_KEY'):
        monkeypatch.setenv('UNIMATCH_' + key, 'technical-fixture')
    calls = []
    async def post(self, url, **kwargs):
        calls.append((url, kwargs))
        if 'siteverify' in url:
            return httpx.Response(200, json={'success': True, 'hostname': 'testserver', 'action': 'login'}, request=httpx.Request('POST', url))
        return httpx.Response(200, json={'access_token': 'provider-secret'}, request=httpx.Request('POST', url))
    async def get(self, url, **kwargs):
        return httpx.Response(200, json={'sub': 'verified-subject', 'name': 'Student'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    monkeypatch.setattr(httpx.AsyncClient, 'get', get)
    started = client.post('/api/auth/start/google', json={'turnstile_token': 'challenge'})
    assert started.status_code == 200
    from urllib.parse import parse_qs, urlparse
    params = parse_qs(urlparse(started.json()['url']).query)
    assert params['code_challenge_method'] == ['S256']
    callback = '/api/auth/callback/google?state=' + params['state'][0] + '&code=code'
    response = client.get(callback, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'] == '/landing.html'
    assert 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/auth/me').json()['name'] == 'Student'
    assert client.get(callback, follow_redirects=False).status_code == 400
    assert 'provider-secret' not in response.text


def test_expired_session_and_wrong_turnstile_hostname_fail_closed(tmp_path, monkeypatch):
    import httpx
    app, client = portal(tmp_path, monkeypatch)
    token = app.state.portal_store.create_session('github', 'x', 'A')
    with app.state.portal_store.connect() as db:
        db.execute('UPDATE sessions SET expires=?', (time.time()-1,))
    client.cookies.set('unimatch_session', token)
    assert client.get('/api/auth/me').status_code == 401
    for key in ('GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET', 'TURNSTILE_SITE_KEY', 'TURNSTILE_SECRET_KEY'):
        monkeypatch.setenv('UNIMATCH_' + key, 'technical-fixture')
    async def post(self, url, **kwargs):
        return httpx.Response(200, json={'success': True, 'hostname': 'evil.example', 'action': 'login'}, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    assert client.post('/api/auth/start/github', json={'turnstile_token': 'challenge'}).status_code == 400
