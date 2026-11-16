import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_phase7_service import service


def test_dean_csv_intake_locks_preferences_and_revokes_publication(service, tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    from backend.app import thesis

    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'portal.sqlite3'))
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'fixture-intake')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', json.dumps({
        'github:dean': {'role': 'dean'}, 'github:faculty': {'role': 'faculty', 'advisor_id': 'a'},
    }))
    app = create_app(service=service, frontend_dir=tmp_path)

    def account(subject, provider='github'):
        cookie = app.state.portal_store.create_session(provider, subject, subject)
        return TestClient(app, cookies={'unimatch_session': cookie})

    dean, faculty = account('dean'), account('faculty')
    student, outsider = account('student@example.test', 'email'), account('outsider')
    base = '/api/thesis'
    csv = 'student_id,name,email,phone\nS1,Student,student@example.test,0912345678\n'
    assert outsider.post(base + '/roster', json={'csv_text': csv}).status_code == 403
    assert dean.post(base + '/roster', json={'csv_text': csv + 'S2,Other,student@example.test,\n'}).status_code == 422
    assert dean.post(base + '/roster', json={'csv_text': csv}).status_code == 200
    assert student.get(base).json()['in_roster'] is True
    assert outsider.get(base).json()['in_roster'] is False
    assert outsider.post(base + '/choice', json={'advisor_ids': ['a']}).status_code == 409
    assert dean.post(base + '/proposal', json={'advisor_ids': ['a']}).status_code == 409
    assert dean.post(base + '/close', json={}).status_code == 200
    assert student.post(base + '/choice', json={'advisor_ids': ['a']}).status_code == 409

    def frozen_results(active, students, requests, selected):
        assert active is service and not requests and selected == ['a']
        assert len(students) == 1 and not students[0]['submitted']
        row = {'user_id': students[0]['user_id'], 'student_name': students[0]['name'],
               'advisor_id': 'a', 'advisor_name': 'Technical A'}
        return {'id': 'sealed', 'status': 'feasible',
                'results': {name: {'status': 'feasible', 'assignments': [row]} for name in ('ppo', 'dqn')}}

    monkeypatch.setattr(thesis, 'compare_models', frozen_results)
    assert dean.post(base + '/proposal', json={'advisor_ids': ['a']}).status_code == 200
    assert faculty.get(base).json()['assignments'] == []
    assert dean.post(base + '/publish', json={'id': 'sealed', 'algorithm': 'dqn'}).status_code == 200
    assert faculty.get(base).json()['assignments'][0]['phone'] == '0912345678'
    assert student.get(base).json()['assignment']['advisor_id'] == 'a'
    assert faculty.post(base + '/revoke', json={}).status_code == 403
    assert dean.post(base + '/revoke', json={}).status_code == 200
    assert faculty.get(base).json()['assignments'] == []
    assert student.get(base).json()['assignment'] is None
    assert dean.get(base).json()['preferences_closed'] is True

    draft = {'id': None, 'assignments': {'S1': 'a'}}
    assert faculty.post(base + '/manual', json=draft).status_code == 403
    assert dean.post(base + '/manual', json={**draft, 'assignments': {'missing': 'a'}}).status_code == 422
    assert dean.post(base + '/manual', json={**draft, 'assignments': {'S1': 'missing'}}).status_code == 422
    assert dean.post(base + '/manual', json={**draft, 'assignments': {}}).status_code == 200
    incomplete = dean.get(base).json()['manual']['id']
    assert dean.post(base + '/publish', json={'id': incomplete, 'algorithm': 'manual'}).status_code == 409
    assert dean.post(base + '/manual', json=draft).status_code == 409
    assert dean.post(base + '/manual', json={**draft, 'id': incomplete}).status_code == 200

    workspace = dean.get(base).json()
    assert workspace['proposal']['id'] == 'sealed'
    assert faculty.get(base).json()['assignments'] == []
    manual = workspace['manual']
    assert dean.post(base + '/publish', json={'id': manual['id'], 'algorithm': 'manual'}).status_code == 200
    assert student.get(base).json()['assignment']['advisor_id'] == 'a'
    assert faculty.get(base).json()['assignments'][0]['phone'] == '0912345678'
    assert dean.post(base + '/manual', json={**draft, 'id': manual['id']}).status_code == 409
    assert dean.post(base + '/revoke', json={}).status_code == 200
    assert dean.get(base).json()['manual'] == manual


def test_role_assessment_and_ranked_preferences(service, tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    from backend.app.thesis_assessment import ASSESSMENT_VERSION
    from backend.app.thesis_tracks import TRACKS
    service.advisors.append({'advisor_id': 'c', 'advisor_name': 'Technical C'})
    service.advisor_ids += ('c',)
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'portal.sqlite3'))
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'fixture-ranked')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', json.dumps({
        'github:a': {'role': 'faculty', 'advisor_id': 'a'},
        'github:b': {'role': 'faculty', 'advisor_id': 'b'},
        'github:c': {'role': 'faculty', 'advisor_id': 'c'},
    }))
    app = create_app(service=service, frontend_dir=tmp_path)

    def account(subject):
        cookie = app.state.portal_store.create_session('github', subject, subject)
        return TestClient(app, cookies={'unimatch_session': cookie})

    student, a, b, c = map(account, ['student', 'a', 'b', 'c'])
    base = '/api/thesis'
    tracks = student.get(base).json()['assessment']
    assert len(tracks) == 22
    assert all(len(track['questions']) == 5 and set(track['questions'][0]) == {'prompt', 'options'} for track in tracks)
    key = 'product_owner'
    assessment = {'version': ASSESSMENT_VERSION, 'roles': [key], 'orientation': 'idea',
                  'tools': {key: ['Jira']}, 'survey': {key: 4},
                  'answers': {key: [row[2] for row in TRACKS[key]['questions']]}}
    assert student.post(base + '/assessment', json={**assessment, 'roles': [key, key]}).status_code == 422
    assert student.post(base + '/assessment', json=assessment).status_code == 200
    assert student.get(base).json()['profile']['skills'][0]['status'] == 'strong'
    assert student.get(base + '/recommendations').status_code == 200
    assert student.post(base + '/choice', json={'advisor_ids': ['a', 'a']}).status_code == 422
    assert student.post(base + '/choice', json={'advisor_ids': ['c', 'a', 'b']}).status_code == 200
    assert student.get(base).json()['topic_description'] == ''
    assert student.post(base + '/topic', json={'topic_description': 'Topic draft'}).status_code == 200
    applicant = c.get(base).json()['requests'][0]
    assert applicant['rank'] == 1 and applicant['topic_description'] == 'Topic draft'
    assert a.get(base).json()['requests'][0]['rank'] == 2
    assert b.get(base).json()['requests'][0]['rank'] == 3
    decision = {'user_id': applicant['user_id'], 'decision': 'accepted'}
    assert a.post(base + '/decision', json=decision).status_code == 200
    assert b.post(base + '/decision', json=decision).status_code == 409
    assert b.get(base).json()['requests'] == []
    assert c.get(base).json()['requests'] == []
    assert student.post(base + '/topic', json={'topic_description': 'Topic refined'}).status_code == 200
    assert a.get(base).json()['requests'][0]['topic_description'] == 'Topic refined'


def test_email_activation_and_public_registration(tmp_path, monkeypatch):
    from backend.app.email_auth import password_hash
    from backend.app.portal import hashed, install_portal

    code = 'temporary-fixture-activation'
    temporary_password = 'fixture'
    new_password = 'new-fixture-password'
    seed = [{'email': 'dean@example.test', 'name': 'Dean', 'role': 'dean',
             'password_hash': password_hash(temporary_password), 'activation_hash': hashed(code)}]
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'portal.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'http://testserver')
    monkeypatch.setenv('UNIMATCH_EMAIL_ACCOUNT_SEED', json.dumps(seed))
    app = FastAPI()
    install_portal(app)
    client = TestClient(app)
    base = '/api/auth/email/'
    credentials = {'email': 'DEAN@example.test', 'password': temporary_password}
    assert client.post(base + 'login', json=credentials).json()['detail'] == 'activation_required'
    assert client.get('/api/auth/me').status_code == 401
    payload = {**credentials, 'activation_code': code, 'new_password': new_password}
    assert client.post(base + 'activate', json={**payload, 'activation_code': 'wrong'}).status_code == 401
    assert client.post(base + 'activate', json=payload).status_code == 200
    assert client.get('/api/auth/me').json()['role'] == 'dean'
    assert client.post('/api/auth/logout').status_code == 200
    assert client.post(base + 'login', json=credentials).status_code == 401
    install_portal(FastAPI())
    assert client.post(base + 'login', json={**credentials, 'password': new_password}).status_code == 200
    public = TestClient(app)
    student = {'email': 'student@example.test', 'password': new_password, 'name': 'Student', 'role': 'dean'}
    assert public.post(base + 'register', json=student, headers={'Origin': 'https://another.test'}).status_code == 403
    assert public.post(base + 'register', json=student).status_code == 200
    assert public.get('/api/auth/me').json()['role'] == 'student'
    assert public.post(base + 'register', json={**student, 'email': credentials['email']}).status_code == 409


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
    assert dean.post('/api/rebuild/assistant', json={'question': 'Xin chào'}).status_code == 403
    assert a.post('/api/rebuild/assistant', json={'question': 'Xin chào'}).status_code == 403
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
    contact = {'email': 'student@example.test', 'phone': '+84 912 345 678'}
    assert student.post('/api/thesis/choice', json={'advisor_ids': ['b'], 'contact': contact}).status_code == 200
    before_publication = b.get('/api/thesis')
    assert before_publication.json()['registered_students'] == []
    assert contact['email'] not in before_publication.text
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
    faculty = b.get('/api/thesis').json()
    assert [r['student_name'] for r in faculty['assignments']] == ['student']
    assert faculty['registered_students'] == [{'name': 'student', 'email': contact['email'], 'phone': '+84912345678'}]
    assert contact['email'] not in a.get('/api/thesis').text
    assert contact['email'] not in dean.get('/api/thesis').text
    assert second.post('/api/thesis/assessment', json=answers).status_code == 409
