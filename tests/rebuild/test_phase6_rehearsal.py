import json
from pathlib import Path

import pytest


def test_rehearsal_refuses_unverified_predecessor(tmp_path):
    from src.evaluation.semester_rehearsal import load_phase5_parent
    (tmp_path/'reports').mkdir()
    (tmp_path/'reports/phase5_gate.json').write_text(json.dumps({'status':'partial','can_start_phase6':False}))
    with pytest.raises(ValueError,match='phase5'): load_phase5_parent(tmp_path)


def test_rehearsal_gate_distinguishes_technical_work_from_temporal_proof():
    from src.evaluation.semester_rehearsal import phase6_gate
    gate=phase6_gate('run-1',{'idempotent_upload':True,'offline_learning':True,
                     'reload_reproducible':True,'rollback_preserves_assignments':True,'no_holdout_training':True})
    assert gate['status']=='partial' and not gate['can_start_phase7']
    assert not gate['models_promoted'] and gate['temporal_forgetting'] is None
    assert gate['technical_implementation_verified']
    assert gate['blocking_reasons']


def test_actual_registry_drill_preserves_assignment_history(tmp_path):
    from src.evaluation.semester_rehearsal import _registry_drill
    from test_phase6_registry import candidate, contract
    c=contract()
    old,_=candidate(tmp_path,'old');new,_=candidate(tmp_path,'new')
    evaluation=tmp_path/'evaluation.json';evaluation.write_text('{"scope":"technical_drill"}')
    result=_registry_drill(tmp_path/'drill',c,new,old,evaluation)
    assert result['assignments_unchanged'] and result['operational_authorization'] is False
