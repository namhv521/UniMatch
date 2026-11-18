import json

import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def service(tmp_path):
    import numpy as np
    from src.serving.rebuild_service import RebuildService

    class Pipeline:
        def transform_score(self, students, advisors):
            scores = np.array([[.8 if j == 0 else .4 for j in range(len(advisors))] for _ in students])
            return {'scores': {'E4': scores}, 'available': {'E4': np.ones_like(scores, dtype=bool)}}

        def explain_pair(self, student, advisor):
            return {'scope': 'Technical lexical overlap only', 'shared_terms': ['technical']}

    advisors = [{'advisor_id': aid, 'advisor_name': 'Technical ' + aid.upper(), 'research_description': 'technical'}
                for aid in ('a', 'b')]
    return RebuildService(pipeline=Pipeline(), advisors=advisors, taxonomy={'groups': {'topic_tags': {'nlp': {}}}},
                          versions={'encoder_sha256': 'c' * 64}, runtime_dir=tmp_path / 'runtime', scorable=[True, True])


@pytest.fixture
def portal(service, tmp_path, monkeypatch):
    from backend.app.rebuild_api import create_app
    monkeypatch.setenv('UNIMATCH_AUTH_DB', str(tmp_path / 'history.sqlite3'))
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'demo-history')
    monkeypatch.setenv('UNIMATCH_ROLE_ROSTER', json.dumps({
        'github:dean': {'role': 'dean'},
        'github:faculty': {'role': 'faculty', 'advisor_id': 'a'},
    }))
    app = create_app(service=service, frontend_dir=tmp_path)
    def account(subject):
        cookie = app.state.portal_store.create_session('github', subject, subject)
        return TestClient(app, cookies={'unimatch_session': cookie})
    dean, faculty, student = map(account, ['dean', 'faculty', 'student'])
    csv = 'student_id,name,email\nS1,One,one@example.test\nS2,Two,two@example.test\n'
    assert dean.post('/api/thesis/roster', json={'csv_text': csv}).status_code == 200
    assert dean.post('/api/thesis/close', json={}).status_code == 200
    return app, dean, faculty, student


def test_history_keeps_snapshots_reason_actor_and_survives_restart(portal, monkeypatch, service, tmp_path):
    app, dean, faculty, student = portal
    base = '/api/thesis'
    draft = {'id': None, 'assignments': {'S1': 'a', 'S2': 'a'}}
    assert dean.post(base + '/manual', json=draft).status_code == 200
    manual = dean.get(base).json()['manual']
    # With two advisors the equal quota is one each: a receives two.
    assert manual['exceptions']['over_quota'][0]['assigned'] == 2
    assert dean.post(base + '/publish', json={'id': manual['id'], 'algorithm': 'manual'}).status_code == 422
    assert not dean.get(base).json()['published']
    assert dean.post(base + '/manual', json={**draft, 'id': manual['id'], 'reason': ['bad']}).status_code == 422
    reason = 'Giảng viên A nhận thêm theo thống nhất của khoa.'
    published = dean.post(base + '/publish', json={'id': manual['id'], 'algorithm': 'manual', 'reason': reason})
    assert published.status_code == 200
    assert dean.post(base + '/revoke', json={}).status_code == 200
    events = dean.get(base + '/history').json()['items']
    assert [row['action'] for row in events] == ['revoke', 'publish', 'manual_save']
    assert all(row['actor_name'] == 'dean' and row['created_at'].endswith('+00:00') for row in events)
    assert len({row['revision'] for row in events}) == 3
    assert 'snapshot' not in events[0]
    published_revision = events[1]['revision']
    detail = dean.get(base + f'/history/{published_revision}').json()
    assert detail['reason'] == reason
    assert detail['snapshot']['id'] == manual['id']
    assert len(detail['snapshot']['assignments']) == 2
    for client in (faculty, student):
        assert client.get(base + '/history').status_code == 403
        assert client.get(base + f'/history/{published_revision}').status_code == 403
    assert TestClient(app).get(base + '/history').status_code == 401
    assert dean.get(base + '/history?before=0').status_code == 422
    assert dean.get(base + '/history/999999').status_code == 404
    from backend.app.rebuild_api import create_app
    restarted = TestClient(create_app(service=service, frontend_dir=tmp_path), cookies=dean.cookies)
    assert restarted.get(base + f'/history/{published_revision}').json() == detail
    monkeypatch.setenv('UNIMATCH_THESIS_SEMESTER', 'other-semester')
    other = TestClient(create_app(service=service, frontend_dir=tmp_path), cookies=dean.cookies)
    assert other.get(base + '/history').json()['items'] == []
    assert other.get(base + f'/history/{published_revision}').status_code == 404


def test_history_failure_rolls_back_publication_and_revision(portal, monkeypatch):
    from backend.app import thesis_history
    app, dean, _, _ = portal
    assert dean.post('/api/thesis/manual', json={'id': None, 'assignments': {'S1': 'a', 'S2': 'b'}}).status_code == 200
    before = dean.get('/api/thesis').json()
    events = dean.get('/api/thesis/history').json()
    def fail(*args, **kwargs):
        raise RuntimeError('history_write_failed')
    monkeypatch.setattr(thesis_history, 'append_history', fail)
    with pytest.raises(RuntimeError, match='history_write_failed'):
        dean.post('/api/thesis/publish', json={'id': before['manual']['id'], 'algorithm': 'manual'})
    assert not dean.get('/api/thesis').json()['published']
    assert dean.get('/api/thesis/history').json() == events


def test_manual_publication_rechecks_accepted_changes_and_history_paging(portal):
    app, dean, _, _ = portal
    from backend.app.portal import hashed
    uid = hashed('email:one@example.test')
    with app.state.portal_store.connect() as db:
        db.execute("INSERT INTO users VALUES (?,'email','one@example.test','One')", (uid,))
        db.execute('INSERT INTO thesis_students VALUES (?,?,?)', ('demo-history', uid, '{"skills":[]}'))
    assert dean.post('/api/thesis/manual', json={'id': None, 'assignments': {'S1': 'b', 'S2': 'a'}}).status_code == 200
    manual = dean.get('/api/thesis').json()['manual']
    with app.state.portal_store.connect() as db:
        db.execute("INSERT INTO thesis_requests VALUES (?,?,?,'accepted')", ('demo-history', uid, 'a'))
    rejected = dean.post('/api/thesis/publish', json={'id': manual['id'], 'algorithm': 'manual'})
    assert rejected.status_code == 422
    assert rejected.json()['detail']['code'] == 'manual_exception_reason_required'
    for i in range(22):
        assert dean.post('/api/thesis/manual', json={'id': manual['id'], 'assignments': {'S1': 'b', 'S2': 'a'}, 'reason': 'Đổi theo đề nghị.'}).status_code == 200
        manual = dean.get('/api/thesis').json()['manual']
    assert manual['exceptions']['changed_accepted'][0]['student_id'] == 'S1'
    first = dean.get('/api/thesis/history').json()
    second = dean.get('/api/thesis/history', params={'before': first['next_before']}).json()
    assert len(first['items']) == 20 and len(second['items']) == 3
    assert not set(x['revision'] for x in first['items']) & set(x['revision'] for x in second['items'])
