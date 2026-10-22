import importlib.util
from pathlib import Path

import numpy as np
import pytest


def module():
    path=Path(__file__).resolve().parents[2]/'src/environment/rebuild_env.py'
    spec=importlib.util.spec_from_file_location('phase5_env',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def problem(**changes):
    from src.domain.rebuild_matching import AllocationProblem
    values={'scores':np.array([[.9,.8],[.8,.1]]),'available':np.ones((2,2),bool),
        'student_ids':('student-a','student-b'),'advisor_ids':('advisor-a','advisor-b'),
        'capacities':np.array([1,1]),'eligible':np.array([[True,True],[True,False]]),
        'present':np.ones(2,bool),'metadata':{'split':'train','fixture':True}}
    values.update(changes)
    return AllocationProblem(**values)


def test_lookahead_mask_prevents_hall_trap_and_terminal_has_no_action():
    env=module().MatchingEnv([problem()]);obs,info=env.reset(seed=42)
    assert obs.dtype==np.float32 and obs.shape==(19,) and env.observation_space.contains(obs)
    np.testing.assert_array_equal(env.action_masks(),[False,True])
    _,_,done,truncated,step=env.step(1)
    assert not done and not truncated and step['decision']['student_id']=='student-a'
    obs,_,done,truncated,info=env.step(0)
    assert done and not truncated and info['final_validation']['valid']
    assert not obs.any() and not env.action_masks().any()
    assert env.assignments=={'student-a':'advisor-b','student-b':'advisor-a'}
    with pytest.raises(ValueError,match='episode_done'):env.step(0)


@pytest.mark.parametrize('action',[0,-1,2,True,1.0,np.nan])
def test_invalid_action_raises_without_allocation_mutation(action):
    env=module().MatchingEnv([problem()]);before,_=env.reset(seed=1)
    remaining=list(env.remaining_students);capacity=env.remaining_capacities.copy()
    with pytest.raises(ValueError,match='invalid_action'):env.step(action)
    assert env.invalid_action_count==1 and not env.assignments and not env.trace
    assert env.remaining_students==remaining
    np.testing.assert_array_equal(env.remaining_capacities,capacity)
    np.testing.assert_array_equal(env.observation(),before)


def test_unknown_signals_zero_with_mask_and_layout_is_explicit():
    p=problem(eligible=np.ones((2,2),bool),student_features=np.array([[.5,.8],[.1,.2]],np.float32),
              student_feature_known=np.array([[True,False],[False,True]]))
    env=module().MatchingEnv([p]);obs,_=env.reset(seed=5)
    layout=env.state_contract['layout']
    def part(name):a,b=layout[name];return obs[a:b]
    np.testing.assert_array_equal(part('student_features'),[.5,0])
    np.testing.assert_array_equal(part('student_feature_known'),[1,0])
    assert not part('current_preferences').any() and not part('preference_known').any()
    assert len(obs)==9*2+2*2+1


def test_seeded_training_shuffle_deterministic_without_reordering_actions():
    m=module();p=problem(eligible=np.ones((2,2),bool))
    left,right=m.MatchingEnv([p],shuffle_students=True),m.MatchingEnv([p],shuffle_students=True)
    a,info_a=left.reset(seed=17);b,info_b=right.reset(seed=17)
    np.testing.assert_array_equal(a,b)
    assert info_a['student_order']==info_b['student_order']
    assert left.advisor_ids==p.advisor_ids and right.advisor_ids==p.advisor_ids
    assert left.training_provenance[0]['metadata']['split']=='train'


def test_reward_trace_reconstructs_compatibility_preference_fairness_completion():
    p=problem(preferences=np.array([[.3,.7],[.6,.1]]),preference_known=np.ones((2,2),bool))
    env=module().MatchingEnv([p]);env.reset(seed=1)
    rewards=[]
    for action in (1,0):
        _,reward,_,_,info=env.step(action);decision=info['decision'];rewards.append(reward)
        assert reward==pytest.approx(sum(decision['reward_components'].values()))
        assert decision['total_reward']==pytest.approx(reward)
        assert decision['score_known'] and decision['preference_known']
        assert decision['advisor_registry']==list(p.advisor_ids)
        assert 'policy_probabilities' not in decision and 'q_values' not in decision
    assert sum(rewards)==pytest.approx(1.6+.1*(.7+.6)+1)
    assert env.trace[0]['loads_before']==[0,0] and env.trace[-1]['loads_after']==[1,1]


def test_fixed_assignments_survive_training_order_and_infeasibility_is_explicit():
    m=module();p=problem(eligible=np.ones((2,2),bool),fixed_assignments={'student-a':'advisor-a'})
    env=m.MatchingEnv([p],shuffle_students=True);env.reset(seed=4,options={'student_order':['student-b','student-a']})
    np.testing.assert_array_equal(env.action_masks(),[False,True]);env.step(1);env.step(0)
    assert env.assignments['student-a']=='advisor-a'
    impossible=problem(capacities=np.array([1,0]))
    with pytest.raises(ValueError,match='infeasible_problem'):m.MatchingEnv([impossible]).reset(seed=1)


def test_registry_feature_dimension_and_reward_contract_mismatches_rejected():
    m=module();p=problem()
    with pytest.raises(ValueError,match='advisor_registry'):m.MatchingEnv([p,problem(advisor_ids=('advisor-b','advisor-a'))])
    with pytest.raises(ValueError,match='feature_dimension'):m.MatchingEnv([p,problem(student_features=np.ones((2,1)),student_feature_known=np.ones((2,1),bool))])
    with pytest.raises(ValueError,match='preference_weight'):m.MatchingEnv([problem(preference_weight=.2)])
    with pytest.raises(ValueError,match='reward_weights'):m.MatchingEnv([p],reward_weights={'score':True})


def test_known_student_features_must_fit_declared_unit_interval():
    p=problem(student_features=np.array([[2.0],[-1.0]]),student_feature_known=np.ones((2,1),bool))
    with pytest.raises(ValueError,match='student_features'):module().MatchingEnv([p])


def test_failed_reset_cannot_continue_a_previously_valid_episode():
    m=module();env=m.MatchingEnv([problem(),problem(capacities=np.array([0,0]))])
    env.reset(seed=1,options={'problem_index':0})
    with pytest.raises(ValueError,match='infeasible_problem'):env.reset(seed=1,options={'problem_index':1})
    assert not env.action_masks().any()
    with pytest.raises(ValueError,match='episode_done'):env.step(1)
