import copy

import numpy as np
import pytest

from test_phase5_matching import problem


def test_common_evaluator_replays_exact_trace_and_reports_safe_assignments():
    from src.evaluation.rebuild_benchmark import evaluate_problem, verify_trace
    p=problem(eligible=np.array([[True,True],[True,False]]))
    result=evaluate_problem(p,'hungarian',seed=42)
    assert result['status']=='feasible' and result['metrics']['coverage']==1
    assert result['metrics']['constraint_violations']==0 and result['invalid_action_count']==0
    assert result['trace'][0]['action_index']==1
    assert verify_trace(p,result['trace'])
    changed=copy.deepcopy(result['trace']); changed[0]['total_reward']+=1
    with pytest.raises(ValueError,match='trace_replay_mismatch'):
        verify_trace(p,changed)


def test_seed_summary_reports_variation_and_explicit_undefined_exact_ratio():
    from src.evaluation.rebuild_benchmark import summarize_seeds
    rows=[{'case':'test','algorithm':'dqn','seed':s,'status':'feasible','elapsed_seconds':.1,
           'metrics':{'objective':float(s),'coverage':1.,'constraint_violations':0,'optimality_ratio':None}}
          for s in range(1,6)]
    stats=summarize_seeds(rows)['test']['dqn']
    assert stats['objective']['mean']==3 and stats['objective']['std']>0
    assert stats['objective']['ci95'][0]<3<stats['objective']['ci95'][1]
    assert stats['optimality_ratio']['mean'] is None and stats['optimality_ratio']['n']==0


def test_stress_suite_copies_readonly_constraints_and_declares_expected_conflicts():
    from src.evaluation.rebuild_benchmark import _stress_problems
    from src.domain.rebuild_matching import feasible
    p=problem()
    suite={'train':[p],'metadata':{'advisor_registry':list(p.advisor_ids),'selected_advisor_ids':list(p.advisor_ids)}}
    cases=_stress_problems(suite)
    assert feasible(cases['synthetic_fixed_future'])
    for key in ('synthetic_missing_profile','synthetic_quota_shortage','synthetic_hall_conflict'):
        assert not feasible(cases[key])


def test_cpu_smoke_never_evaluates_real_test_partition():
    from src.evaluation.rebuild_benchmark import _evaluation_problems
    p=problem()
    suite={'train':[p],'validation':p,'test':p,
           'metadata':{'advisor_registry':list(p.advisor_ids),'selected_advisor_ids':list(p.advisor_ids)}}
    assert 'test' not in _evaluation_problems(suite,smoke=True)
    assert _evaluation_problems(suite,smoke=False)['test'] is p
