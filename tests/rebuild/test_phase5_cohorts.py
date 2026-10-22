import numpy as np
import pytest


def fixture():
    scores=np.arange(12,dtype=float).reshape(6,2)/12
    return {'scores':scores,'available':np.ones((6,2),dtype=bool),
        'index':{'student_ids':[f's{i}' for i in range(6)],'advisor_ids':['a','b']},
        'gate':{'feature_contract_sha256':'a'*64,'run_id':'technical-fixture'}}, [
        {'student_id':f's{i}','topic_tags':'nlp' if i==0 else ''} for i in range(6)], {
        'assignments':{f's{i}':('train' if i<4 else 'validation' if i==4 else 'test') for i in range(6)}}


def test_research_cohorts_preserve_splits_registry_and_missing_mention_masks():
    from src.data_pipeline.rebuild_cohorts import assemble_research_suite
    data,students,split=fixture()
    suite=assemble_research_suite(data,students,split,{'groups':{'topic_tags':{'nlp':{},'cv':{}}}},cohort_size=2)
    train=suite['train']
    assert [p.student_ids for p in train]==[('s0','s1'),('s2','s3')]
    assert suite['validation'].student_ids==('s4',) and suite['test'].student_ids==('s5',)
    assert all(p.advisor_ids==('a','b') for p in train+[suite['test']])
    assert train[0].student_features.shape==(2,2)
    assert train[0].student_feature_known[0].sum()==1 and not train[0].student_feature_known[1].any()
    assert all(p.metadata['scope']=='research_only' for p in train)
    assert not suite['metadata']['operational_allocation_authorized']
    assert not train[0].preference_known.any()


def test_research_catalog_selection_uses_train_only_without_imputing_eval_missingness():
    from src.data_pipeline.rebuild_cohorts import assemble_research_suite
    data,students,split=fixture(); data['available'][5,1]=False; data['scores'][5,1]=0
    suite=assemble_research_suite(data,students,split,{'groups':{}},cohort_size=2)
    assert suite['metadata']['selected_advisor_ids']==['a','b']
    assert not suite['test'].available[0,1]


def test_operational_policy_rejects_unknown_eligibility_and_existing_load():
    from src.data_pipeline.rebuild_cohorts import validate_operational_policy
    with pytest.raises(ValueError,match='confirmed_semester_policy_required'):
        validate_operational_policy({},['s'],['a'])
    policy={'semester_id':'explicit-fixture','selected_advisor_ids':['a'],
            'student_ids':['s'],'advisor_ids':['a'],
            'eligibility_confirmed':True,'eligibility':[[True]],'reviewer':'owner:fixture',
            'policy_evidence_ref':'technical-policy','existing_loads':{'a':0},'fixed_assignments':{}}
    validated=validate_operational_policy(policy,['s'],['a'])
    assert validated['eligible'].tolist()==[[True]]
    policy['existing_loads']={'a':1}
    with pytest.raises(ValueError,match='existing_load_requires_matching_fixed_assignments'):
        validate_operational_policy(policy,['s'],['a'])


def test_operational_eligibility_is_bound_to_ordered_ids_not_matrix_shape():
    from src.data_pipeline.rebuild_cohorts import validate_operational_policy
    policy={'semester_id':'explicit-fixture','selected_advisor_ids':['a','b'],
            'student_ids':['s0','s1'],'advisor_ids':['a','b'],
            'eligibility_confirmed':True,'eligibility':[[True,False],[False,True]],
            'reviewer':'owner:fixture','policy_evidence_ref':'fixture','existing_loads':{'a':0,'b':0}}
    with pytest.raises(ValueError,match='policy_identity_order_mismatch'):
        validate_operational_policy(policy,['s1','s0'],['a','b'])


def test_source_adapter_rejects_snapshot_changed_between_bound_reads(monkeypatch,tmp_path):
    import src.data_pipeline.rebuild_cohorts as module
    monkeypatch.setattr(module,'load_approved_features',lambda _: {'contract':{'snapshot':{'run_id':'before'}}})
    monkeypatch.setattr(module,'_load_snapshot',lambda _: ([],[],{'run_id':'after'}))
    with pytest.raises(ValueError,match='cohort_source_snapshot_changed'):
        module.build_research_suite(tmp_path)
