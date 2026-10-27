import json
from pathlib import Path

import pytest


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')


def fixture(tmp_path):
    from src.data_pipeline.reconcile import _digest
    p6=tmp_path/'phase6_runs/prior'
    old={'phase':6,'status':'partial','technical_implementation_verified':True,
         'checks':{'idempotent_upload':True,'offline_learning':True,'reload_reproducible':True,
                   'rollback_preserves_assignments':True,'no_holdout_training':True}}
    write(p6/'evidence.json',{'technical':True})
    write(p6/'manifest.json',{'gate':old,'artifacts':[{'path':'evidence.json','sha256':_digest(p6/'evidence.json')}]})
    experiment=tmp_path/'convergence_runs/experiment'
    gate={'status':'verified','completed_seeds':[42,43,44,45,46],
          'parent_steps':16384,'stages':[24576,32768],
          'checks':{'no_train_holdout_overlap':True,'zero_invalid_actions':True,
                    'zero_constraint_violations':True,'reload_exact':True,'code_unchanged':True,
                    'final_test_not_reused':True},'models_promoted':False}
    write(experiment/'gate.json',gate)
    write(experiment/'manifest.json',{'gate':gate,'artifacts':[{'path':'gate.json','sha256':_digest(experiment/'gate.json')}]})
    authority={'kind':'local_release_scope_amendment','authorization_source':'explicit_user_message',
               'reviewer':'owner:current_session','requirements':{'semester_verification_required':False,
                   'local_csv_inference':True,'more_steps_experiment':True,'continue_following_phases':True},
               'user_message':'không cần xác thực học kì; sử dụng dữ liệu local; kiểm tra tăng step và tiếp tục phase sau'}
    path=tmp_path/'authority.json';write(path,authority)
    return p6,experiment,path


def test_amended_gate_retains_history_and_requires_real_experiment(tmp_path):
    from src.evaluation.local_release_gates import verify_local_phase6
    p6,experiment,authority=fixture(tmp_path)
    old=(p6/'manifest.json').read_bytes()
    result=verify_local_phase6(p6,experiment,authority)
    assert result['status']=='verified' and result['can_start_phase7']
    assert result['temporal_forgetting'] is None and not result['models_promoted']
    assert (p6/'manifest.json').read_bytes()==old
    (experiment/'gate.json').write_text('tamper')
    with pytest.raises(ValueError,match='hash'):verify_local_phase6(p6,experiment,authority)


def test_scope_and_completed_seed_checks_fail_closed(tmp_path):
    from src.evaluation.local_release_gates import verify_local_phase6
    from src.data_pipeline.reconcile import _digest
    p6,experiment,authority=fixture(tmp_path)
    values=json.loads(authority.read_text());values['authorization_source']='agent_inference';write(authority,values)
    with pytest.raises(ValueError,match='owner'):verify_local_phase6(p6,experiment,authority)
    values['authorization_source']='explicit_user_message';write(authority,values)
    gate=json.loads((experiment/'gate.json').read_text());gate['completed_seeds']=[42];write(experiment/'gate.json',gate)
    write(experiment/'manifest.json',{'gate':gate,'artifacts':[{'path':'gate.json','sha256':_digest(experiment/'gate.json')}]})
    with pytest.raises(ValueError,match='experiment'):verify_local_phase6(p6,experiment,authority)


def test_native_convergence_gate_schema_is_bound_and_fail_closed(tmp_path):
    from src.evaluation.local_release_gates import verify_local_phase6
    from src.data_pipeline.reconcile import _digest
    p6,experiment,authority=fixture(tmp_path)
    gate=json.loads((experiment/'gate.json').read_text())
    gate['checkpoint_steps']=gate.pop('stages')
    gate.update(no_train_holdout_overlap=True,zero_invalid_actions=True,zero_constraint_violations=True,
                reload_exact=True,code_unchanged=True,test_evaluated=False)
    gate['checks']={'budget_completed':True,'all_weights_changed':True,'all_reloads_match':True,
                    'all_allocations_valid':True,'train_holdout_isolated':True,
                    'test_not_evaluated':True,'code_unchanged':True}
    def publish():
        write(experiment/'gate.json',gate)
        write(experiment/'manifest.json',{'gate':gate,'artifacts':[{'path':'gate.json','sha256':_digest(experiment/'gate.json')}]})
    publish()
    assert verify_local_phase6(p6,experiment,authority)['status']=='verified'
    gate['checks']['all_reloads_match']=False;publish()
    with pytest.raises(ValueError):verify_local_phase6(p6,experiment,authority)
