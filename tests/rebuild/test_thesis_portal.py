import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_phase7_service import service


def test_unconfigured_production_keeps_existing_coordinator_access(tmp_path, monkeypatch):
    from backend.app.portal import install_portal

    monkeypatch.setenv('UNIMATCH_DEPLOYMENT', 'production')
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'portal.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'http://testserver')
    monkeypatch.delenv('UNIMATCH_ROLE_ROSTER', raising=False)
    monkeypatch.delenv('UNIMATCH_THESIS_SEMESTER', raising=False)
    app = FastAPI()
    install_portal(app)
    cookie = app.state.portal_store.create_session('github', 'existing', 'Existing user')
    client = TestClient(app, cookies={'unimatch_session': cookie})
    assert client.get('/api/auth/me').json()['role'] == 'dean'
    assert client.get('/api/thesis').json() == {'detail': 'semester_not_configured'}


def test_semester_flow_is_scoped_and_preserves_accepted_places(service, tmp_path, monkeypatch):
    from backend.app.rebuild_assistant_api import create_app
    from backend.app.thesis_assessment import ASSESSMENT

    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'portal.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'http://testserver')
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'fixture.1')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', json.dumps({
        'github:dean': {'role': 'dean'},
        'github:faculty-a': {'role': 'faculty', 'advisor_id': 'a'},
        'github:faculty-b': {'role': 'faculty', 'advisor_id': 'b'},
    }))
    app = create_app(service=service, frontend_dir=tmp_path)

    def account(subject):
        cookie = app.state.portal_store.create_session('github', subject, subject)
        return TestClient(app, cookies={'unimatch_session': cookie})

    dean, a, b, student, second = map(account, ['dean', 'faculty-a', 'faculty-b', 'student', 'second'])
    assert student.get('/api/auth/me').json()['role'] == 'student'
    assert a.get('/api/auth/me').json()['advisor_id'] == 'a'
    assert student.get('/api/rebuild/bootstrap').status_code == 403
    assert b.get('/api/rebuild/training').status_code == 403
    assert student.post('/api/rebuild/assistant', json={'question': 'Xin chào'}).status_code == 200
    assert student.post('/api/thesis/threshold', json={'threshold': 90}).status_code == 403
    assert student.post('/api/thesis/choice', json={'advisor_id': 'b'}).status_code == 409
    answers = {'survey': {tag: 3 for tag in ASSESSMENT},
               'answers': {tag: [q[2] for q in questions] for tag, (_, questions) in ASSESSMENT.items()}}
    assert student.post('/api/thesis/assessment', json=answers, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert student.post('/api/thesis/assessment', json={}).status_code == 422
    for client in (student, second):
        assert client.post('/api/thesis/assessment', json=answers).status_code == 200
    assert all(skill['status'] == 'strong' for skill in student.get('/api/thesis').json()['profile']['skills'])
    assert [r['advisor_id'] for r in student.get('/api/thesis/recommendations').json()] == ['a', 'b']
    assert student.post('/api/thesis/choice', json={'advisor_id': 'a'}).status_code == 200
    a_state = a.get('/api/thesis').json()
    assert a_state['student_count'] == 2
    request = a_state['requests'][0]
    assert b.get('/api/thesis').json()['requests'] == []
    assert 'answers' not in request
    decision = {'user_id': request['user_id'], 'decision': 'accepted'}
    assert b.post('/api/thesis/decision', json=decision).status_code == 409
    assert a.post('/api/thesis/decision', json={**decision, 'decision': 'rejected'}).status_code == 200
    assert student.post('/api/thesis/choice', json={'advisor_id': 'a'}).status_code == 409
    assert student.post('/api/thesis/choice', json={'advisor_id': 'b'}).status_code == 200
    assert b.post('/api/thesis/decision', json=decision).status_code == 200
    assert b.post('/api/thesis/decision', json=decision).status_code == 409
    assert student.post('/api/thesis/choice', json={'advisor_id': None}).status_code == 409
    assert dean.post('/api/thesis/proposal', json={'advisor_ids': ['a']}).status_code == 409
    assert dean.post('/api/thesis/threshold', json={'threshold': 80}).json() == {'threshold': 80}
    pool = {'advisor_ids': ['a', 'b']}
    proposal = dean.post('/api/thesis/proposal', json=pool).json()
    assert proposal['status'] == 'feasible'
    assert [(q['accepted'], q['remaining'], q['total']) for q in proposal['quotas']] == [(0, 1, 1), (1, 0, 1)]
    assert next(row for row in proposal['assignments'] if row['accepted'])['advisor_id'] == 'b'
    assert student.get('/api/thesis').json()['assignment'] is None
    assert second.post('/api/thesis/choice', json={'advisor_id': 'a'}).status_code == 200
    assert dean.post('/api/thesis/publish', json={'id': proposal['id']}).status_code == 409
    refreshed = dean.post('/api/thesis/proposal', json=pool).json()
    assert dean.post('/api/thesis/publish', json={'id': refreshed['id']}).status_code == 200
    assert student.get('/api/thesis').json()['assignment']['advisor_id'] == 'b'
    assert [r['student_name'] for r in b.get('/api/thesis').json()['assignments']] == ['student']
    assert second.post('/api/thesis/assessment', json=answers).status_code == 409
