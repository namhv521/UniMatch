from fastapi.testclient import TestClient


def test_clean_source_without_private_artifacts_fails_closed(tmp_path):
    from backend.app.rebuild_api import create_app
    app=create_app(output=tmp_path,token='public-technical-ci-token-only')
    client=TestClient(app)
    health=client.get('/health')
    assert health.status_code==200 and health.json()['status']=='degraded'
    response=client.get('/api/rebuild/bootstrap',headers={'Authorization':'Bearer public-technical-ci-token-only'})
    assert response.status_code==503 and response.json()=={'detail':'verified_artifacts_not_ready'}
    assert str(tmp_path) not in response.text
