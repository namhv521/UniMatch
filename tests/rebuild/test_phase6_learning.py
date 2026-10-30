import copy
import json
from datetime import datetime, timezone

import pytest

from src.data_pipeline.review_decisions import record_hash


def term(name, start, end, students, groups):
    return {'semester_id': name, 'status': 'closed', 'semester_start': start,
            'closed_at': end, 'student_ids': students, 'source_groups': groups,
            'snapshot_sha256': record_hash(name), 'approval_receipt_sha256': record_hash(name+'approved'),
            'features_available_at': start}


def temporal_terms():
    return [term('2023.1','2023-01-01T00:00:00Z','2023-05-01T00:00:00Z',['a'],['x']),
            term('2024.1','2024-01-01T00:00:00Z','2024-05-01T00:00:00Z',['b'],['y']),
            term('2025.1','2025-01-01T00:00:00Z','2025-05-01T00:00:00Z',['c'],['z'])]


def test_temporal_split_requires_actual_closure_and_disjoint_sources():
    from src.rl.semester_learning import temporal_split
    terms=temporal_terms()
    result=temporal_split(terms)
    assert result['train']==['2023.1'] and result['test']==['2025.1']
    assert result['validation']==['2024.1']
    for mutation in ('draft','overlap','future_features','missing_receipt','same_source'):
        values=copy.deepcopy(terms)
        if mutation=='draft': values[0]['status']='draft'
        if mutation=='overlap': values[2]['student_ids']=['a']
        if mutation=='future_features': values[0]['features_available_at']=values[0]['closed_at']
        if mutation=='missing_receipt': values[0]['approval_receipt_sha256']=''
        if mutation=='same_source': values[2]['source_groups']=['x']
        with pytest.raises(ValueError): temporal_split(values)
    with pytest.raises(ValueError): temporal_split(terms[:1])


def test_forgetting_pairs_identical_frozen_cohorts_and_blocks_regressions():
    from src.rl.semester_learning import forgetting_report
    old={'2023.1':{'cohort_sha256':'a'*64,'mean_compatibility':.8,'coverage':1.,'constraint_violations':0}}
    new=copy.deepcopy(old); new['2023.1']['mean_compatibility']=.7
    report=forgetting_report(old,new,max_drop=.05)
    assert not report['passed'] and report['max_forgetting']==pytest.approx(.1)
    new['2023.1']['cohort_sha256']='b'*64
    with pytest.raises(ValueError): forgetting_report(old,new,max_drop=.05)
    assert forgetting_report({}, {}, max_drop=.05)['status']=='unavailable'
    new=copy.deepcopy(old);new['2023.1']['constraint_violations']=1
    assert not forgetting_report(old,new,max_drop=.05)['passed']


def test_offline_queue_idempotent_single_claim_hash_bound_results(tmp_path):
    from src.rl.semester_learning import OfflineJobs
    jobs=OfflineJobs(tmp_path/'queue.sqlite3')
    request={'scope':'research_rehearsal','snapshot_sha256':'a'*64,'parent_contract_sha256':'b'*64}
    first=jobs.enqueue(request); assert jobs.enqueue(request)==first
    assert jobs.get(first)['status']=='queued'
    claimed=jobs.claim(first);assert claimed['request']==request
    with pytest.raises(ValueError): jobs.claim(first)
    result=tmp_path/'result.json';result.write_text('{"ok":true}')
    jobs.finish(first,'succeeded',result)
    assert jobs.get(first)['status']=='succeeded'
    result.write_text('tampered')
    with pytest.raises(ValueError,match='hash'):jobs.get(first)


def test_ppo_continuation_fresh_rollouts_preserves_parent_bytes(tmp_path):
    import numpy as np
    import torch
    from test_phase5_matching import problem
    from src.environment.rebuild_env import MatchingEnv
    from src.rl.rebuild_ppo import MaskedPPOAgent
    from src.rl.semester_learning import continue_ppo
    from src.data_pipeline.reconcile import _digest
    torch.set_num_threads(1)
    metadata={'split':'train','feature_contract_sha256':'a'*64,'taxonomy_feature_order_sha256':'b'*64,'policy_version':'test'}
    env=MatchingEnv([problem(metadata=metadata)])
    contract={'state_contract':env.state_contract,'feature_contract_sha256':'a'*64,
              'taxonomy_feature_order_sha256':'b'*64,'reward_weights':env.reward_weights,
              'quota_policy_version':'test','training_student_ids':list(env.problems[0].student_ids)}
    parent=MaskedPPOAgent(env,contract=contract,n_steps=16,batch_size=8,n_epochs=1,hidden_sizes=(8,))
    parent.learn(32);parent.save(tmp_path/'parent')
    before=_digest(tmp_path/'parent/state.pt')
    candidate=continue_ppo(tmp_path/'parent',env,MatchingEnv([problem(metadata=metadata)]),
                           old_contract=contract,new_contract=contract)
    assert candidate.model.rollout_buffer is not parent.model.rollout_buffer
    obs,_=env.reset();mask=env.action_masks()
    np.testing.assert_array_equal(parent.probabilities(obs,mask),candidate.probabilities(obs,mask))
    assert candidate.learn(32)['actual_timesteps']==32
    assert _digest(tmp_path/'parent/state.pt')==before
    bad=problem(metadata={**metadata,'split':'test'})
    with pytest.raises(ValueError,match='train'):
        continue_ppo(tmp_path/'parent',env,MatchingEnv([bad]),old_contract=contract,new_contract=contract)
    bad=problem(metadata=metadata,student_ids=('heldout-1','heldout-2'))
    with pytest.raises(ValueError,match='registry'):
        continue_ppo(tmp_path/'parent',env,MatchingEnv([bad]),old_contract=contract,new_contract=contract)
    bad=problem(metadata={**metadata,'policy_version':'different'})
    with pytest.raises(ValueError,match='policy'):
        continue_ppo(tmp_path/'parent',env,MatchingEnv([bad]),old_contract=contract,new_contract=contract)
