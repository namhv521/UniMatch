import hashlib
import json
from pathlib import Path

import pytest


def api():
    from src.serving import rebuild_registry
    return rebuild_registry


def contract():
    return {'state_contract':{'version':'fixture-state','advisor_ids':['a','b'],'dimension':3},
        'taxonomy_feature_order_sha256':'a'*64,'feature_contract_sha256':'b'*64,
        'quota_policy_version':'fixture-quota','reward_weights':{'score':1}}


def candidate(tmp_path, name='one', *, config=None):
    m=api();c=config or contract();folder=tmp_path/name;folder.mkdir()
    (folder/'state.pt').write_bytes(('technical model fixture '+name).encode())
    metadata={'algorithm':'MaskablePPO','contract':c,'state_sha256':hashlib.sha256((folder/'state.pt').read_bytes()).hexdigest()}
    metadata['manifest_sha256']=m.content_sha256(metadata)
    (folder/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
    evaluation=tmp_path/(name+'-evaluation.json');evaluation.write_text(json.dumps({'fixture':True,'safety_passed':True}),encoding='utf-8')
    gate=tmp_path/(name+'-gate.json');gate.write_text(json.dumps({'status':'verified','can_promote_candidate':True,
        'scope':'technical_drill','checks':{'safety_passed':True,'frozen_evaluation_passed':True},
        'checkpoint_sha256':m.checkpoint_digest(folder),'contract_sha256':m.content_sha256(c),
        'frozen_evaluation_sha256':hashlib.sha256(evaluation.read_bytes()).hexdigest()}),encoding='utf-8')
    return folder,{'evaluation':evaluation,'gate':gate}


def registry(tmp_path,scope='technical_drill'):
    return api().CandidateRegistry(tmp_path/'registry.sqlite3',compatible_contract=contract(),scope=scope)


def receipt(reg, candidate_id, kind='sandbox_candidate_promotion'):
    item=reg.get_candidate(candidate_id)
    return {'kind':kind,'scope':'technical_drill','decision':'approve',
        'authorization_source':'automated_test_fixture','reviewer':'phase6-drill','approval_quote':'Technical fixture only.',
        'candidate_id':candidate_id,'contract_sha256':item['contract_sha256'],
        'evaluation_sha256':item['evaluation_sha256']}


def test_registration_idempotent_and_promotion_is_sandbox_only(tmp_path):
    reg=registry(tmp_path);folder,reports=candidate(tmp_path)
    key=reg.register(folder,contract(),reports)
    assert reg.register(folder,contract(),reports)==key and reg.active() is None
    selected=reg.promote(key,receipt(reg,key))
    assert selected['candidate_id']==key and selected['scope']=='technical_drill'
    assert selected['operational_authorization'] is False and selected['production'] is False
    assert len([e for e in reg.audit() if e['action']=='register'])==1


def test_missing_gate_or_failed_safety_is_rejected(tmp_path):
    reg=registry(tmp_path);folder,reports=candidate(tmp_path)
    with pytest.raises(ValueError,match='evaluation'):reg.register(folder,contract(),{'evaluation':reports['evaluation']})
    gate=json.loads(reports['gate'].read_text());gate['checks']['safety_passed']=False
    reports['gate'].write_text(json.dumps(gate))
    with pytest.raises(ValueError,match='gate'):reg.register(folder,contract(),reports)
    assert reg.active() is None


def test_incompatible_contract_and_tampered_checkpoint_fail_closed(tmp_path):
    reg=registry(tmp_path);bad={**contract(),'taxonomy_feature_order_sha256':'c'*64}
    folder,reports=candidate(tmp_path,config=bad)
    with pytest.raises(ValueError,match='compatible'):reg.register(folder,bad,reports)
    folder2,reports2=candidate(tmp_path,'two');key=reg.register(folder2,contract(),reports2)
    (folder2/'state.pt').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='checkpoint'):reg.promote(key,receipt(reg,key))
    assert reg.active() is None


def test_fixture_authority_never_passes_research_sandbox(tmp_path):
    reg=registry(tmp_path,scope='research_sandbox');folder,reports=candidate(tmp_path)
    gate=json.loads(reports['gate'].read_text());gate['scope']='research_sandbox';reports['gate'].write_text(json.dumps(gate))
    key=reg.register(folder,contract(),reports);fake=receipt(reg,key);fake['scope']='research_sandbox'
    with pytest.raises(ValueError,match='authority'):reg.promote(key,fake)
    assert reg.active() is None


def test_rollback_preserves_immutable_assignment_batches(tmp_path):
    m=api();reg=registry(tmp_path);one,reports1=candidate(tmp_path);two,reports2=candidate(tmp_path,'two')
    a=reg.register(one,contract(),reports1);b=reg.register(two,contract(),reports2)
    reg.promote(a,receipt(reg,a));reg.promote(b,receipt(reg,b))
    assignments=[{'student_id':'s1','advisor_id':'a'}];source={'semester_id':'technical-fixture','snapshot_sha256':'c'*64}
    binding=m.content_sha256({'batch_id':'fixture-batch','assignments':assignments,'source':source})
    authorization={'kind':'sandbox_assignment_approval','scope':'technical_drill','decision':'approve',
        'authorization_source':'automated_test_fixture','reviewer':'phase6-drill','approval_quote':'Technical fixture.',
        'batch_sha256':binding,'source_sha256':m.content_sha256(source)}
    before=reg.record_assignments('fixture-batch',assignments,source=source,owner_receipt=authorization)
    assert reg.record_assignments('fixture-batch',assignments,source=source,owner_receipt=authorization)==before
    reg.rollback(a,receipt(reg,a,'sandbox_candidate_rollback'))
    assert reg.active()['candidate_id']==a and reg.get_assignments('fixture-batch')==before
    with pytest.raises(ValueError,match='immutable'):
        reg.record_assignments('fixture-batch',[{'student_id':'s1','advisor_id':'b'}],source=source,owner_receipt=authorization)


def test_rollback_cannot_select_unapproved_or_modified_prior_model(tmp_path):
    reg=registry(tmp_path);one,r1=candidate(tmp_path);two,r2=candidate(tmp_path,'two')
    a=reg.register(one,contract(),r1);b=reg.register(two,contract(),r2);reg.promote(a,receipt(reg,a))
    with pytest.raises(ValueError,match='prior_approval'):reg.rollback(b,receipt(reg,b,'sandbox_candidate_rollback'))
    assert reg.active()['candidate_id']==a
    reg.promote(b,receipt(reg,b));(one/'state.pt').write_bytes(b'modified')
    with pytest.raises(ValueError,match='checkpoint'):reg.rollback(a,receipt(reg,a,'sandbox_candidate_rollback'))
    assert reg.active()['candidate_id']==b


def test_receipt_must_bind_exact_candidate_and_evaluation(tmp_path):
    reg=registry(tmp_path);folder,reports=candidate(tmp_path);key=reg.register(folder,contract(),reports)
    forged=receipt(reg,key);forged['evaluation_sha256']={'gate':'f'*64}
    with pytest.raises(ValueError,match='receipt'):reg.promote(key,forged)
    assert reg.active() is None


def test_active_selection_rechecks_stored_approval_checksum(tmp_path):
    import sqlite3
    reg=registry(tmp_path);folder,reports=candidate(tmp_path);key=reg.register(folder,contract(),reports)
    reg.promote(key,receipt(reg,key))
    with sqlite3.connect(reg.path) as db:
        db.execute('UPDATE approvals SET receipt=?',('{}',))
    with pytest.raises(ValueError,match='approval'):reg.active()


def test_assignment_batch_database_rows_are_immutable(tmp_path):
    import sqlite3
    reg=registry(tmp_path)
    # Database guard is independent of the application API.
    with sqlite3.connect(reg.path) as db:
        db.execute('INSERT INTO assignment_batches VALUES(?,?)',('fixture','{}'))
    with sqlite3.connect(reg.path) as db:
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            db.execute('UPDATE assignment_batches SET payload=?',('{"changed":true}',))
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            db.execute('DELETE FROM assignment_batches')
