import copy
import numpy as np
import pytest

from src.evaluation.rl_convergence import (
    PARENT_STEPS, CHECKPOINT_STEPS, SEEDS, paired_statistics,
    select_candidate, validate_training_suite, checkpoint_weights_sha256,
)


def row(seed,steps,objective,*,algorithm='dqn',safe=True):
    return {'seed':seed,'total_steps':steps,'algorithm':algorithm,
        'checkpoint_path':f'/private/{algorithm}/{steps}/{seed}',
        'metrics':{'objective':objective,'mean_compatibility':objective/10,
          'coverage':1. if safe else .5,'constraint_violations':0},
        'invalid_action_count':0,'reload_trace_equal':True,
        'elapsed_seconds':.01,'weights_changed':steps!=PARENT_STEPS}


def rows():
    return [row(s,PARENT_STEPS,5) for s in SEEDS]+[row(s,CHECKPOINT_STEPS[0],6) for s in SEEDS]+[row(s,CHECKPOINT_STEPS[1],5.5) for s in SEEDS]


def test_predeclared_budget_is_fixed_and_test_is_not_an_eval_stage():
    assert SEEDS==(42,43,44,45,46)
    assert PARENT_STEPS==16384 and CHECKPOINT_STEPS==(24576,32768)


def test_paired_stats_preserves_seed_pairing_and_reports_uncertainty():
    before=[row(s,PARENT_STEPS,5+i) for i,s in enumerate(SEEDS)]
    after=[row(s,24576,6+i) for i,s in reversed(list(enumerate(SEEDS)))]
    result=paired_statistics(before,after)
    assert result['objective']['delta_mean']==pytest.approx(1)
    assert result['objective']['delta_std']==pytest.approx(0)
    assert result['objective']['delta_ci95']==pytest.approx([1,1])
    assert result['objective']['n']==5
    after[-1]['seed']=999
    with pytest.raises(ValueError): paired_statistics(before,after)


def test_selection_uses_validation_across_all_seeds_and_fixed_representative_seed():
    selected=select_candidate(rows(),'dqn')
    assert selected['total_steps']==24576 and selected['seed']==42
    assert selected['improved_on_validation']
    assert selected['fallback']=='hungarian' and selected['production_promoted'] is False


def test_more_steps_can_be_worse_and_fallback_retains_parent():
    data=rows()
    for r in data:
        if r['total_steps']!=PARENT_STEPS: r['metrics']['objective']=4
    selected=select_candidate(data,'dqn')
    assert selected['total_steps']==PARENT_STEPS and not selected['improved_on_validation']


def test_incomplete_unsafe_or_unreproducible_stage_never_selected():
    for mutation in ('unsafe','reload','missing'):
        data=rows()
        stage=[r for r in data if r['total_steps']==24576]
        if mutation=='unsafe':stage[0]['metrics']['coverage']=.5
        if mutation=='reload':stage[0]['reload_trace_equal']=False
        if mutation=='missing':data.remove(stage[0])
        selected=select_candidate(data,'dqn')
        assert selected['total_steps']==32768


def test_fixed_seed_regression_prevents_representative_checkpoint_cherry_picking():
    data=rows()
    for r in data:
        if r['total_steps']==24576 and r['seed']==42:r['metrics']['objective']=4.99
    assert select_candidate(data,'dqn')['total_steps']==32768


def test_splits_source_membership_and_frozen_payload_are_bound():
    from src.domain.rebuild_matching import AllocationProblem
    from src.evaluation.rebuild_benchmark import problem_payload
    def problem(ids,split):
        return AllocationProblem(scores=np.array([[.9,.8]]),available=np.ones((1,2),bool),
            student_ids=(ids,),advisor_ids=('a','b'),capacities=np.array([1,0]),eligible=np.ones((1,2),bool),
            present=np.ones(2,bool),metadata={'split':split})
    suite={'train':[problem('s','train')],'validation':problem('v','validation'),'test':problem('t','test')}
    inputs={'training_problems':[problem_payload(p) for p in suite['train']],
        'evaluation_problems':{'validation':problem_payload(suite['validation'])},
        'model_contract':{'training_student_ids':['s']}}
    assert validate_training_suite(suite,inputs)['holdout_isolated']
    bad=copy.deepcopy(inputs);bad['training_problems'][0]['scores'][0][0]=.1
    with pytest.raises(ValueError):validate_training_suite(suite,bad)
    suite['train']=[problem('t','train')]
    with pytest.raises(ValueError):validate_training_suite(suite,inputs)
