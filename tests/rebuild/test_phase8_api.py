from fastapi.testclient import TestClient

from test_phase7_service import service


class TechnicalAssistant:
    def answer(self,question,**kwargs):
        return {'answer':'Technical fixture answer','mode':'deterministic_read_only',
                'citations':[],'intent':'fixture','question_length':len(question)}


def test_assistant_routes_precede_static_and_keep_matching_protected(service):
    from backend.app.rebuild_assistant_api import create_app
    client=TestClient(create_app(service=service,assistant=TechnicalAssistant(),token='technical-fixture-token-long'))
    assert client.get('/api/rebuild/bootstrap').status_code==401
    assert client.post('/api/rebuild/assistant',json={'question':'data science'}).status_code==401
    headers={'Authorization':'Bearer technical-fixture-token-long'}
    boot=client.get('/api/rebuild/bootstrap',headers=headers)
    assert boot.status_code==200 and boot.json()['assistant_ready'] is True
    reply=client.post('/api/rebuild/assistant',headers=headers,json={'question':'data science'})
    assert reply.status_code==200 and reply.json()['mode']=='deterministic_read_only'
    assert reply.json()['advisor_selection_scope']=='all_approved_public_profiles'
    assert client.get('/api/rebuild/templates/students.csv',headers=headers).status_code==200


def test_assistant_body_and_types_are_bounded_before_routing(service):
    from backend.app.rebuild_assistant_api import create_app
    client=TestClient(create_app(service=service,assistant=TechnicalAssistant(),token='technical-fixture-token-long'))
    headers={'Authorization':'Bearer technical-fixture-token-long'}
    for payload in ({'question':'a'*4001},{'question':123},{'question':'x','top_k':True},
                    {'question':'x','advisor_ids':'anything'},{'question':'x','path':'private.json'}):
        assert client.post('/api/rebuild/assistant',headers=headers,json=payload).status_code==400
    response=client.post('/api/rebuild/assistant',headers=headers,content=b'x'*32769)
    assert response.status_code==413


def test_knowledge_failure_does_not_disable_base_matching_bootstrap(service,tmp_path):
    from backend.app.rebuild_assistant_api import create_app
    client=TestClient(create_app(service=service,token='technical-fixture-token-long',output=tmp_path))
    headers={'Authorization':'Bearer technical-fixture-token-long'}
    result=client.get('/api/rebuild/bootstrap',headers=headers)
    assert result.status_code==200 and result.json()['assistant_ready'] is False
    assert client.post('/api/rebuild/assistant',headers=headers,json={'question':'topic'}).status_code==503
