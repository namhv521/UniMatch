"""Private technical fixtures: additive serving never changes the incumbent."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_phase7_service import service, csv_text
from src.data_pipeline.github_advisors import canonical, digest, write_run
from src.data_pipeline.review_decisions import record_hash


def github_sources(tmp_path, *, fork=False, metadata=False):
    text = 'PyTorch supports the technical fixture.\n'
    raw = text.encode(); sha = digest(raw); commit = 'a'*40
    source = {'source_id':'s1', 'sha256':sha, 'retrieved_at':'2026-10-23T00:00:00+00:00',
              'url':f'https://raw.githubusercontent.com/example/technical/{commit}/README.md',
              'http_status':200, 'kind':'readme', 'commit_sha':commit, 'path':'README.md'}
    evidence = {'advisor_id':'a', 'source_id':'s1', 'source_sha256':sha, 'source_url':source['url'],
                'github_username':'example', 'repository':'example/technical', 'commit_sha':commit,
                'path':'README.md', 'group':'frameworks_libraries', 'tag':'pytorch',
                'matched_text':'PyTorch', 'start':0, 'end':7, 'excerpt':text.strip(),
                'excerpt_start':0, 'excerpt_end':len(text.strip()), 'locator':'README.md:chars:0:7',
                'evidence_class':'documentation_mention', 'offset_basis':'decoded UTF-8-sig text'}
    if metadata:
        raw=canonical([{'id':1,'full_name':'example/technical','description':text.strip()}]);sha=digest(raw)
        source.update(kind='repository_listing',url='https://api.github.com/users/example/repos?per_page=100',sha256=sha,path=None)
        evidence.update(source_sha256=sha,source_url=source['url'],path='',locator='repositories[id=1].description',
                        evidence_class='repository_metadata',offset_basis='decoded JSON field value')
    evidence['evidence_id'] = digest(canonical(evidence))
    run = write_run(tmp_path/'sources', {'sources':[source], 'evidence':[evidence],
        'repositories':[{'full_name':'example/technical', 'fork':fork, 'is_template':False}],
        'supplements':{'advisors':[{'advisor_id':'a', 'github_username':'example',
            'identity_mapping':'owner_provided', 'evidence_refs':[evidence['evidence_id']]}]},
        'owner_receipt':{'identity_mapping':'owner_confirmed'},
        'quality':{'enumeration_complete':True, 'source_bytes_complete':True}},
        raw={sha:raw}, run_id='technical-run')
    return run, evidence


def profiles(service):
    from src.data_pipeline.normalization import load_taxonomy
    service.taxonomy=load_taxonomy()
    # Official identity anchors are separate from the additional GitHub source.
    for row in service.advisors:
        row['source_url'] = 'https://fit.neu.edu.vn/lecturer/'+row['advisor_id']
        row['research_description'] = 'PyTorch technical topic'
    return [{**row, 'review_status':'approved', 'retrieved_at':'2026-10-22T00:00:00+00:00',
             'research_topics':[], 'teaching_topics':[], 'profile_intro':'', 'evidence':[]}
            for row in service.advisors]


def assistant_args(run, evidence):
    sha=digest((run/'manifest.json').read_bytes())
    review=run.parent/'review.json'
    review.write_bytes(canonical({'status':'verified','source_manifest_sha256':sha,
        'approved_units':[{'advisor_id':'a','group':evidence['group'],'tag':evidence['tag'],
            'evidence_ids':[evidence['evidence_id']],
            'checks':{'source':'pass','span':'pass','semantic':'pass'}}]}))
    return {'github_run':run,'github_manifest_sha256':sha,'quality_review_path':review,
            'quality_review_sha256':digest(review.read_bytes())}


def test_github_citation_is_exact_bound_short_and_not_proficiency(service, tmp_path):
    from src.serving.github_service import GithubAssistant
    run, evidence = github_sources(tmp_path)
    assistant = GithubAssistant(profiles(service), service, **assistant_args(run,evidence))
    citation = assistant._citation('a', 'PyTorch', require_concepts=True)
    assert citation['snippet'] == evidence['excerpt'] and len(citation['snippet'].split()) <= 20
    assert citation['source_sha256'] == evidence['source_sha256']
    assert '/blob/'+'a'*40+'/README.md' in citation['source_url']
    assert citation['attribution'] == 'documentation_mention'
    assert citation['identity_mapping'] == 'owner_confirmed'
    assert citation['evidence_confidence'] is None
    assert citation['raw_source_url'].startswith('https://raw.githubusercontent.com/')
    assert assistant._citation('a', 'TensorFlow', require_concepts=True) is None


def test_approved_source_still_found_without_encoder_score(service, tmp_path, monkeypatch):
    from src.serving.github_service import GithubAssistant
    run, evidence = github_sources(tmp_path)
    assistant = GithubAssistant(profiles(service), service, **assistant_args(run, evidence))
    monkeypatch.setattr(service.pipeline, 'transform_score', lambda students, advisors: {
        'scores': {'E4': np.zeros((1, len(advisors)))},
        'available': {'E4': np.zeros((1, len(advisors)), dtype=bool)}})
    rows = assistant.match_topic_to_advisors('PyTorch', top_k=10)
    assert rows[0]['advisor_id'] == 'a' and rows[0]['score'] is None
    assert rows[0]['citation']['source_sha256'] == evidence['source_sha256']
    assert not assistant.match_topic_to_advisors('TensorFlow', top_k=10)


def test_metadata_citation_points_to_actual_json_and_confidence_is_evidence_ratio(service,tmp_path):
    from src.serving.github_service import GithubAssistant
    run,evidence=github_sources(tmp_path,metadata=True)
    service.advisors[0]['expertise_confidence']='0.6363636363636364'
    assistant=GithubAssistant(profiles(service),service,**assistant_args(run,evidence))
    citation=assistant._citation('a','PyTorch',require_concepts=True)
    assert citation['source_url']==citation['raw_source_url']==evidence['source_url']
    assert citation['repository_url'].endswith('/tree/'+'a'*40)
    assert citation['offset_basis']=='decoded JSON field value'
    assert citation['evidence_confidence']==7/11
    assert 'not proficiency' in citation['confidence_semantics']


@pytest.mark.parametrize('mutation', ['hash', 'span', 'fork'])
def test_github_citation_rejects_tamper_or_false_attribution(service, tmp_path, mutation):
    from src.serving.github_service import GithubAssistant
    run, evidence = github_sources(tmp_path, fork=mutation == 'fork')
    if mutation == 'span':
        evidence['matched_text'] = 'TensorFlow'
        (run/'evidence.jsonl').write_bytes(canonical(evidence)+b'\n')
        manifest=json.loads((run/'manifest.json').read_bytes())
        manifest['artifacts']['evidence.jsonl']=digest((run/'evidence.jsonl').read_bytes())
        (run/'manifest.json').write_bytes(canonical(manifest))
    sha = '0'*64 if mutation == 'hash' else digest((run/'manifest.json').read_bytes())
    args=assistant_args(run,evidence);args['github_manifest_sha256']=sha
    with pytest.raises(ValueError):
        GithubAssistant(profiles(service),service,**args)


def test_new_api_is_private_and_uploaded_cohorts_remain_local(service, tmp_path):
    from backend.app.github_rebuild_api import create_app
    from src.serving.github_service import GithubAssistant
    run, evidence = github_sources(tmp_path)
    assistant=GithubAssistant(profiles(service), service, **assistant_args(run,evidence))
    client=TestClient(create_app(service=service, assistant=assistant, token='technical-github-token-long'))
    assert client.get('/api/rebuild/bootstrap').status_code == 401
    h={'Authorization':'Bearer technical-github-token-long'}
    boot=client.get('/api/rebuild/bootstrap',headers=h)
    assert boot.status_code == 200 and boot.json()['assistant_ready'] is True
    value=client.post('/api/rebuild/students/validate',headers=h,
                      json={'csv_text':csv_text([{'student_id':'fixture-s','thesis_title':'technical'}])}).json()
    assert value['valid'] and service.get_students(value['cohort_id'],scope=hashlib.sha256(b'technical-github-token-long').hexdigest())[0]['review_status']=='pending'
    assert TestClient(client.app,client=('192.0.2.1',2)).get('/api/rebuild/bootstrap',headers=h).status_code==403


def test_new_api_never_falls_back_when_selection_unspecified(monkeypatch):
    from backend.app.github_rebuild_api import create_app
    monkeypatch.delenv('UNIMATCH_GITHUB_BUNDLE',raising=False)
    monkeypatch.delenv('UNIMATCH_GITHUB_SELECTION',raising=False)
    with pytest.raises(ValueError,match='explicit'):
        create_app()


@pytest.fixture
def loader_inputs(tmp_path, monkeypatch):
    from src.serving import github_service as module
    monkeypatch.setattr(module,'ROOT',tmp_path,raising=False)
    from src.data_pipeline.normalization import load_taxonomy
    from src.domain.rebuild_matching import AllocationProblem
    from src.environment.rebuild_env import MatchingEnv
    from src.evaluation.rebuild_benchmark import problem_payload
    from src.features.rebuild_features import FeaturePipeline
    from src.rl.rebuild_ppo import MaskedPPOAgent
    from src.rl.rebuild_dqn import MaskedDQN
    taxonomy=load_taxonomy(); tags=sorted((g,t) for g,items in taxonomy['groups'].items() for t in items)
    advisors=[{'advisor_id':f'a{i:02}','advisor_name':f'Technical {i}'} for i in range(35)]
    students=[{'student_id':f's{i:03}','thesis_title':'technical'} for i in range(194)]
    folder=tmp_path/'bundle';folder.mkdir(); selection_folder=tmp_path/'selection';selection_folder.mkdir()
    feature_file=folder/'feature_contract.json';feature_file.write_bytes(canonical({'technical_fixture':True}))
    feature_sha=digest(feature_file.read_bytes())
    transformer=folder/'transformer';transformer.mkdir()
    (transformer/'transformer.json').write_bytes(b'{}');(transformer/'idf.npz').write_bytes(b'technical-idf')
    available=np.ones((194,35),bool);available[:,34]=False
    scores=np.full((194,35),.5);scores[:,34]=0
    np.save(folder/'scores.npy',scores);np.save(folder/'available.npy',available)
    index={'student_ids':[s['student_id'] for s in students], 'advisor_ids':[a['advisor_id'] for a in advisors], 'shape':[194,35],'dtype':'float64'}
    paths={}
    for key,data in [('students',students),('advisors',advisors),('index',index)]:
        path=folder/(key+'.json');path.write_bytes(canonical(data));paths[key+'_path']=str(path)
    paths.update(scores_path=str(folder/'scores.npy'),available_path=str(folder/'available.npy'),
                 transformer_dir=str(folder/'transformer'),feature_contract_path=str(feature_file),taxonomy_path=str(Path('configs/data/taxonomy_v1.yaml').resolve()),github_manifest_sha256='d'*64)
    def problem(start,count,split):
        return AllocationProblem(scores=scores[start:start+count],available=available[start:start+count],
            student_ids=tuple(s['student_id'] for s in students[start:start+count]),
            advisor_ids=tuple(a['advisor_id'] for a in advisors),capacities=np.full(35,count),
            eligible=np.ones((count,35),bool),present=np.ones(35,bool),
            student_features=np.zeros((count,len(tags)),np.float32),student_feature_known=np.zeros((count,len(tags)),bool),
            metadata={'split':split,'feature_contract_sha256':feature_sha,'taxonomy_feature_order_sha256':record_hash(tags)})
    train=[problem(i*45,45,'train') for i in range(3)];env=MatchingEnv(train,shuffle_students=True)
    contract={'training_student_ids':[s['student_id'] for s in students[:135]],
              'state_contract':env.state_contract,'reward_weights':env.reward_weights,
              'quota_policy_version':'equal-division-canonical/1.0','feature_contract_sha256':feature_sha,
              'taxonomy_feature_order_sha256':record_hash(tags),'training_problem_sha256':[record_hash(problem_payload(p)) for p in train]}
    source=folder/'students.json'; artifacts=[{'path':str(source.resolve()),'sha256':digest(source.read_bytes())}]
    split_file=folder/'splits.json'
    split_file.write_bytes(canonical({'assignments':{row['student_id']:'train' if i<135 else 'validation' if i<164 else 'test' for i,row in enumerate(students)}}))
    split_sha=digest(split_file.read_bytes());artifacts.append({'path':str(split_file.resolve()),'sha256':split_sha})
    artifacts.extend({'path':str(Path(paths[key]).resolve()),'sha256':digest(Path(paths[key]).read_bytes())} for key in ('advisors_path','index_path','scores_path','available_path','taxonomy_path','feature_contract_path'))
    encoder={'artifacts':[{'path':str((transformer/name).resolve()),'sha256':digest((transformer/name).read_bytes())} for name in ('transformer.json','idf.npz')],
             'transformer_json_sha256':digest((transformer/'transformer.json').read_bytes()),'transformer_idf_sha256':digest((transformer/'idf.npz').read_bytes())}
    bundle={'schema_version':'github-advisor-training-bundle/1.0','bundle_run_id':'technical-bundle',
            'source_artifacts':artifacts,'frozen_encoder':encoder,'student_split_sha256':split_sha,'comparators':{},
            'training_problems':[problem_payload(p) for p in train],
            'evaluation_problems':{'validation':problem_payload(problem(135,29,'validation')),'test':problem_payload(problem(164,30,'test'))},
            'model_contract':contract,'serving':paths}
    selected={'run_id':'technical-selection','schema_version':'github-advisor-model-selection/1.0','test_evaluated':False,'production_promoted':False,'candidates':{key:{'algorithm':key,'path':str(selection_folder/key),
        'native_contract':copy.deepcopy(contract),'native_contract_sha256':record_hash(contract),
        'frozen_encoder':encoder,'frozen_encoder_sha256':record_hash(encoder),'checkpoint_steps':256,'seed':42,
        'checkpoint_sha256':'f'*64,'production_promoted':False} for key in ('ppo','dqn')}}
    bundle_file=folder/'training_bundle.json';bundle_file.write_bytes(canonical(bundle))
    (selection_folder/'input_manifest.json').write_bytes(canonical({'bundle_sha256':digest(bundle_file.read_bytes())}))
    monkeypatch.setattr(module,'_load_bundle',lambda path:bundle)
    monkeypatch.setattr(module,'_load_selection',lambda path:selected)
    class Frozen:
        @staticmethod
        def transform_score(rows,advisor_rows):
            return {'scores':{'E4':np.full((len(rows),len(advisor_rows)),.5)},'available':{'E4':np.ones((len(rows),len(advisor_rows)),bool)}}
    registry=[]
    monkeypatch.setattr(FeaturePipeline,'load',lambda path,known_identities:registry.extend(known_identities) or Frozen())
    monkeypatch.setattr(MaskedPPOAgent,'load',lambda *args,**kwargs:object())
    monkeypatch.setattr(MaskedDQN,'load',lambda *args,**kwargs:object())
    return module,bundle,selected,tmp_path,registry


def test_loader_preserves_exact_actions_missing_profiles_and_identity_registry(loader_inputs):
    module,bundle,selected,root,registry=loader_inputs
    value=module.load_github_service(root/'bundle/training_bundle.json',root/'selection/selection.json',root/'data_rebuild/runtime/github')
    assert value.advisor_ids==tuple(bundle['evaluation_problems']['test']['advisor_ids'])
    assert value.bootstrap()['advisors'][-1]['scorable'] is False
    assert len(value.models)==2 and value.versions['models']['ppo']['checkpoint_steps']==256
    assert all(s['student_id'] in registry for s in json.loads(Path(bundle['serving']['students_path']).read_bytes()))
    assert value.versions['scope']=='local_research_source_enriched'


def test_loader_rejects_other_bundle_bytes_even_when_native_contract_matches(loader_inputs):
    module,bundle,selected,root,_=loader_inputs
    # Both verified-loader fixtures still return the same compatible contract.
    path=root/'selection/input_manifest.json'
    path.write_bytes(canonical({'bundle_sha256':'0'*64}))
    with pytest.raises(ValueError,match='training_bundle_hash_mismatch'):
        module.load_github_service(root/'bundle/training_bundle.json',root/'selection/selection.json',root/'data_rebuild/runtime/github')


@pytest.mark.parametrize('mutation',['native','encoder','registry','mask','source','runtime'])
def test_loader_rejects_incompatible_registry_contract_or_source(loader_inputs,mutation):
    module,bundle,selected,root,_=loader_inputs
    runtime=root/'data_rebuild/runtime/github'
    if mutation=='native':selected['candidates']['ppo']['native_contract']['feature_contract_sha256']='0'*64
    if mutation=='encoder':selected['candidates']['dqn']['frozen_encoder_sha256']='0'*64
    if mutation=='registry':
        path=Path(bundle['serving']['index_path']);data=json.loads(path.read_bytes());data['advisor_ids'].reverse();path.write_bytes(canonical(data))
    if mutation=='mask':np.save(bundle['serving']['available_path'],np.ones((194,35),float))
    if mutation=='source':Path(bundle['source_artifacts'][0]['path']).write_bytes(b'[]')
    if mutation=='runtime':runtime=root/'bundle/runtime'
    with pytest.raises(ValueError):
        module.load_github_service(root/'bundle/training_bundle.json',root/'selection/selection.json',runtime)


def test_loader_rejects_frontend_runtime_before_writing_cohorts(loader_inputs):
    module,_,_,root,_=loader_inputs
    with pytest.raises(ValueError,match='private_runtime'):
        module.load_github_service(root/'bundle/training_bundle.json',root/'selection/selection.json',root/'frontend')
    assert not (root/'frontend').exists()


def test_private_runtime_cohort_is_not_accessible_through_unauthenticated_static_route(loader_inputs):
    from backend.app.rebuild_api import create_app
    module,_,_,root,_=loader_inputs
    runtime=root/'data_rebuild/v1/runtime/github'
    value=module.load_github_service(root/'bundle/training_bundle.json',root/'selection/selection.json',runtime)
    frontend=root/'frontend';frontend.mkdir();(frontend/'index.html').write_text('Technical public fixture',encoding='utf-8')
    token='technical-github-private-token';client=TestClient(create_app(service=value,token=token,frontend_dir=frontend))
    upload=client.post('/api/rebuild/students/validate',headers={'Authorization':'Bearer '+token},
        json={'csv_text':csv_text([{'student_id':'private-fixture','thesis_title':'technical'}])})
    assert upload.status_code==200 and upload.json()['valid']
    cohort_id=upload.json()['cohort_id'];assert (runtime/'cohorts'/(cohort_id+'.json')).is_file()
    assert client.get('/index.html').status_code==200
    for url in (f'/cohorts/{cohort_id}.json',f'/data_rebuild/v1/runtime/github/cohorts/{cohort_id}.json',
                f'/%2e%2e/data_rebuild/v1/runtime/github/cohorts/{cohort_id}.json'):
        response=client.get(url);assert response.status_code==404 and 'private-fixture' not in response.text
