import csv
import io
import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_thesis_history import portal, service


def test_official_export_uses_published_manual_pairs_and_faculty_scope(portal):
    app, dean, faculty, student = portal
    base = '/api/thesis'
    assert student.get(base + '/export').status_code == 403
    assert dean.get(base + '/export').status_code == 409
    old_proposal = {'id': 'automatic-before-edit', 'status': 'feasible',
                    'quotas': [{'advisor_id': 'a', 'total': 1}, {'advisor_id': 'b', 'total': 1}],
                    'assignments': [{'student_id': 'S1', 'advisor_id': 'a'}, {'student_id': 'S2', 'advisor_id': 'b'}]}
    with app.state.portal_store.connect() as db:
        db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?', (json.dumps(old_proposal), 'demo-history'))
    draft = {'id': None, 'assignments': {'S1': 'b', 'S2': 'a'}}
    assert dean.post(base + '/manual', json=draft).status_code == 200
    manual = dean.get(base).json()['manual']
    assert dean.post(base + '/publish', json={'id': manual['id'], 'algorithm': 'manual'}).status_code == 200
    exported = dean.get(base + '/export')
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.content.decode('utf-8-sig'))))
    assert [(r['student_id'], r['advisor_id']) for r in rows] == [('S1', 'b'), ('S2', 'a')]
    assert {r['algorithm'] for r in rows} == {'manual'}
    published_revision = dean.get(base + '/history').json()['items'][0]['revision']
    assert {r['revision'] for r in rows} == {str(published_revision)}
    assert 'email' not in rows[0] and 'one@example.test' not in exported.text
    scoped = list(csv.DictReader(io.StringIO(faculty.get(base + '/export').content.decode('utf-8-sig'))))
    assert [r['student_id'] for r in scoped] == ['S2']
    assert 'two@example.test' in faculty.get(base + '/export').text
    assert 'one@example.test' not in faculty.get(base + '/export').text
    assert faculty.get(base).json()['teaching_load'] == {'accepted': 0, 'assigned': 1, 'quota': 1}
    assert dean.post(base + '/revoke', json={}).status_code == 200
    assert faculty.get(base + '/export').status_code == 409


def test_recommendations_explain_actual_scoring_input(service, tmp_path, monkeypatch):
    import numpy as np
    from backend.app import thesis
    from backend.app.rebuild_api import create_app
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'recommendations.sqlite3'))
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'demo-recommendations')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', '{}')
    app = create_app(service=service, frontend_dir=tmp_path)
    student = TestClient(app, cookies={'unimatch_session': app.state.portal_store.create_session('github', 'student', 'Student')})
    monkeypatch.setattr(thesis, 'compatibility', lambda active, profiles:
                        (np.ones((len(profiles), len(active.advisors))), np.ones((len(profiles), len(active.advisors)), dtype=bool)))
    from backend.app.thesis_assessment import ASSESSMENT_VERSION
    from backend.app.thesis_tracks import TRACKS
    key = 'backend_developer'
    if key not in TRACKS:
        key = next(iter(TRACKS))
    keyword = next(term for term in TRACKS[key]['keywords'] if len(term) >= 3)
    service.advisors[0]['research_description'] = keyword
    payload = {'version': ASSESSMENT_VERSION, 'roles': [key], 'orientation': 'idea',
               'survey': {key: 4}, 'tools': {key: []},
               'answers': {key: [q[2] for q in TRACKS[key]['questions']]}}
    assert student.post('/api/thesis/assessment', json=payload).status_code == 200
    recommendations = student.get('/api/thesis/recommendations').json()
    assert recommendations
    for row in recommendations:
        assert row['basis']['topic_tags']
        assert 'explanation' in row
        assert row['scope'] == 'topic_compatibility_not_proficiency_or_acceptance'
    assert keyword in recommendations[0]['basis']['matched_keywords']


def test_password_recovery_is_one_time_expiring_scoped_and_revokes_sessions(tmp_path, monkeypatch):
    from backend.app.portal import install_portal
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'reset.sqlite3'))
    monkeypatch.setenv('UNIMATCH_PUBLIC_ORIGIN', 'http://testserver')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', '{"github:dean":{"role":"dean"}}')
    monkeypatch.delenv('UNIMATCH_EMAIL_ACCOUNT_SEED', raising=False)
    app = FastAPI()
    install_portal(app)
    owner, other, dean = TestClient(app), TestClient(app), TestClient(app, cookies={
        'unimatch_session': app.state.portal_store.create_session('github', 'dean', 'Dean')})
    credentials = {'email': 'student@example.test', 'password': 'original-password', 'name': 'Student'}
    assert owner.post('/api/auth/email/register', json=credentials).status_code == 200
    assert other.post('/api/auth/email/register', json={**credentials, 'email': 'other@example.test'}).status_code == 200
    assert owner.post('/api/auth/recovery-code', json={'email': credentials['email']}).status_code == 403
    issued = dean.post('/api/auth/recovery-code', json={'email': credentials['email']})
    assert issued.status_code == 200
    token = issued.json()['code']
    reset = {'email': credentials['email'], 'reset_code': token, 'new_password': 'replacement-password'}
    client = TestClient(app)
    assert client.post('/api/auth/email/reset', json=reset, headers={'Origin': 'https://evil.test'}).status_code == 403
    assert client.post('/api/auth/email/reset', json={**reset, 'reset_code': 'wrong'}).status_code == 401
    assert client.post('/api/auth/email/reset', json={**reset, 'email': 'other@example.test'}).status_code == 401
    assert client.post('/api/auth/email/reset', json={**reset, 'new_password': 'short'}).status_code == 422
    assert client.post('/api/auth/email/reset', json=reset).status_code == 200
    assert owner.get('/api/auth/me').status_code == 401
    assert other.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/email/reset', json=reset).status_code == 401
    assert client.post('/api/auth/email/login', json=credentials).status_code == 401
    assert client.post('/api/auth/email/login', json={**credentials, 'password': reset['new_password']}).status_code == 200
    token = dean.post('/api/auth/recovery-code', json={'email': credentials['email']}).json()['code']
    with app.state.portal_store.connect() as db:
        db.execute('UPDATE email_password_resets SET expires=? WHERE email=?', (time.time() - 1, credentials['email']))
    assert client.post('/api/auth/email/reset', json={**reset, 'reset_code': token}).status_code == 401


def test_manual_working_copy_survives_threshold_save(portal):
    _, dean, _, _ = portal
    draft = {'id': None, 'assignments': {'S1': 'a'}}
    assert dean.post('/api/thesis/manual', json=draft).status_code == 200
    before = dean.get('/api/thesis').json()['manual']
    assert dean.post('/api/thesis/threshold', json={'threshold': 61}).status_code == 200
    after = dean.get('/api/thesis').json()['manual']
    assert after['id'] == before['id']
    assert after['assignments'] == before['assignments']


def test_dean_incomplete_filter_distinguishes_missing_profile_preference_and_contact(portal):
    app, dean, _, _ = portal
    from backend.app.portal import hashed
    uid = hashed('email:one@example.test')
    with app.state.portal_store.connect() as db:
        db.execute("INSERT INTO users VALUES (?,'email','one@example.test','One')", (uid,))
        db.execute('INSERT INTO thesis_students VALUES (?,?,?)', ('demo-history', uid, '{"skills":[]}'))
    rows = dean.get('/api/thesis').json()['roster_preview']
    assert rows[0]['incomplete_reasons'] == ['Chưa gửi nguyện vọng', 'Thiếu thông tin liên hệ']
    assert rows[1]['incomplete_reasons'] == ['Chưa nộp khảo sát', 'Chưa gửi nguyện vọng', 'Thiếu thông tin liên hệ']


def test_quiz_answer_changes_do_not_change_same_direction_scoring_input():
    from backend.app.thesis_assessment import ASSESSMENT_VERSION, assess, scoring_row
    from backend.app.thesis_tracks import TRACKS
    role = next(iter(TRACKS))
    questions = TRACKS[role]['questions']
    shared = {'version': ASSESSMENT_VERSION, 'roles': [role], 'orientation': 'idea', 'major': '',
              'survey': {role: 2}, 'tools': {role: []}}
    correct = assess({**shared, 'answers': {role: [question[2] for question in questions]}})
    incorrect = assess({**shared, 'answers': {role: [(question[2] + 1) % len(question[1]) for question in questions]}})
    correct_row = scoring_row('student', correct)
    incorrect_row = scoring_row('student', incorrect)
    assert correct_row['topic_tags'] == incorrect_row['topic_tags']
    assert correct_row['thesis_keywords'] == incorrect_row['thesis_keywords']
