import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    from backend.app.api import endpoints
    from backend.app.main import app
    dataset = {'students': [{'student_id': 's1', 'student_name': 'Demo A', 'thesis_title': 'AI', 'advisor_id': 'a'},
                            {'student_id': 's2', 'student_name': 'Demo B', 'thesis_title': 'Web', 'advisor_id': 'b'}],
               'advisors': [{'advisor_id': 'a', 'advisor_name': 'Advisor A', 'quota': 1, 'skill_text': 'AI', 'academic_title': '', 'primary_field': 'AI', 'publication_evidence_count': 1},
                            {'advisor_id': 'b', 'advisor_name': 'Advisor B', 'quota': 1, 'skill_text': 'Web', 'academic_title': '', 'primary_field': 'Web', 'publication_evidence_count': 1}],
               'split': {'train': np.array([0, 1]), 'val': np.array([0, 1]), 'test': np.array([0, 1])},
               'scores': np.array([[.9, .2], [.4, .8]]), 'partial': False, 'sha256': 'test'}
    monkeypatch.setattr(endpoints, 'get_dataset', lambda: dataset)
    return TestClient(app)


def test_allocate_quota_and_schema(client):
    response = client.post('/api/v1/allocate', json={'cohort_type': 'val', 'algorithm': 'exact_hungarian', 'fairness_weight': .15})
    assert response.status_code == 200
    result = response.json()
    assert result['metrics']['quota_violations'] == 0
    assert len(result['assignments']) == 2
    assert result['metrics']['mean_compatibility'] == pytest.approx(.85)


def test_holdout_unavailable_model_and_unknown_fields(client):
    assert client.post('/api/v1/allocate', json={'cohort_type': 'test'}).status_code == 409
    assert client.post('/api/v1/allocate', json={'algorithm': 'maskable_ppo'}).status_code == 409
    assert client.post('/api/v1/allocate', json={'injected': True}).status_code == 422
    assert client.post('/api/v1/allocate', json={'quota_override': 0}).status_code == 422


def test_missing_data_has_actionable_service_error(monkeypatch):
    from backend.app.api import endpoints
    from backend.app.main import app
    def missing():
        raise ValueError('incomplete curation')
    monkeypatch.setattr(endpoints, 'get_dataset', missing)
    response = TestClient(app).post('/api/v1/allocate', json={})
    assert response.status_code == 503
    assert 'detail' in response.json()
