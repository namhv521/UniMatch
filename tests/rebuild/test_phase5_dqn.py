import json
import numpy as np
import pytest
import torch

from src.rl.rebuild_dqn import MaskedDQN, ReplayBuffer, masked_double_dqn_targets


def test_double_dqn_masks_online_argmax_then_reads_target_not_target_max():
    result = masked_double_dqn_targets([1, 2], [False, True],
        [[10, 999, 20], [5, 6, 7]], [[100, 9999, 30], [1, 2, 3]],
        [[True, False, True], [False, False, False]], .5)
    np.testing.assert_allclose(result, [16, 2])


def test_target_rejects_nonterminal_empty_mask_and_invalid_arrays():
    with pytest.raises(ValueError):
        masked_double_dqn_targets([1], [False], [[1, 2]], [[1, 2]], [[False, False]], .9)
    with pytest.raises(ValueError):
        masked_double_dqn_targets([1], [True], [[float('nan'), 2]], [[1, 2]], [[False, False]], .9)


def test_replay_copies_and_stores_truncated_as_bootstrappable():
    replay = ReplayBuffer(3, 2, 3, seed=7)
    obs = np.array([1., 2.]); nxt = np.array([3., 4.]); mask = np.array([False, True, False])
    replay.add(obs, 1, 2., nxt, False, mask, truncated=True, current_mask=mask)
    obs[:] = 99; nxt[:] = 88; mask[:] = False
    batch = replay.sample(1)
    np.testing.assert_equal(batch['observations'], [[1, 2]])
    np.testing.assert_equal(batch['next_masks'], [[False, True, False]])
    assert batch['truncated'][0] and not batch['terminated'][0]
    with pytest.raises(ValueError):
        replay.add([1, 2], 0, 0, [2, 3], False, [False]*3)
    with pytest.raises(ValueError):
        replay.add([1, 2], 0, 0, [2, 3], True, [False]*3, current_mask=[False, True, False])


def test_replay_ring_and_seeded_sampling():
    a = ReplayBuffer(2, 1, 2, seed=42); b = ReplayBuffer(2, 1, 2, seed=42)
    for replay in (a, b):
        for n in range(4):
            replay.add([n], 0, n, [n+1], True, [False, False])
    assert len(a) == 2
    ba, bb = a.sample(2), b.sample(2)
    for key in ba:
        np.testing.assert_equal(ba[key], bb[key])
    assert set(ba['rewards']) == {2, 3}


def model(**kwargs):
    return MaskedDQN(2, 3, hidden_sizes=(8,), batch_size=2, learning_starts=2,
                     train_frequency=1, target_update_interval=2, **kwargs)


def test_epsilon_and_greedy_cannot_select_forbidden_action():
    m = model()
    with torch.no_grad():
        for p in m.online.parameters(): p.zero_()
        m.online[-1].bias.copy_(torch.tensor([100., 1., 2.]))
    assert m.predict([0, 0], [False, True, True]) == 2
    assert {m.predict([0, 0], [False, True, True], deterministic=False, epsilon=1.) for _ in range(100)} == {1, 2}
    with pytest.raises(ValueError): m.predict([0, 0], [False]*3)
    with pytest.raises(ValueError): m.predict([0, 0], [1, 0, 1])


class ToyEnv:
    training_provenance = [{'problem_index': 0, 'student_ids': ['s1', 's2'],
                            'metadata': {'split': 'train', 'snapshot_sha256': 'a'*64}}]
    state_contract = {'version': 1, 'advisors': ['a', 'b', 'c']}
    def reset(self, seed=None):
        self.pos = 0
        return np.array([0., 1.]), {}
    def action_masks(self):
        return np.array([False, True, True]) if self.pos == 0 else np.array([False, True, False])
    def step(self, action):
        assert self.action_masks()[action]
        self.pos += 1
        return np.array([self.pos, 1.]), 1., self.pos == 2, False, {}


def test_learn_updates_weights_records_real_losses_and_train_provenance():
    m = model(contract={'state_contract': ToyEnv.state_contract})
    before = [p.detach().clone() for p in m.online.parameters()]
    report = m.learn(ToyEnv(), 12)
    assert report['actual_timesteps'] == 12 and report['episodes'] == 6
    assert report['gradient_updates'] >= 1 and all(np.isfinite(report['losses']))
    assert report['training_unique_student_count'] == 2
    assert any(not torch.equal(a, b) for a, b in zip(before, m.online.parameters()))
    assert len(m.replay) == 12


def test_learn_rejects_heldout_and_missing_provenance():
    env = ToyEnv(); env.training_provenance = [{'student_ids': ['test'], 'metadata': {'split': 'test'}}]
    with pytest.raises(ValueError): model().learn(env, 2)
    env.training_provenance = []
    with pytest.raises(ValueError): model().learn(env, 2)


def test_seed_reproducibility():
    a = model(seed=17); b = model(seed=17)
    ra, rb = a.learn(ToyEnv(), 8), b.learn(ToyEnv(), 8)
    assert ra['losses'] == rb['losses']
    np.testing.assert_equal(a.q_values([.5, 1]), b.q_values([.5, 1]))


def test_checkpoint_parity_contract_replay_rng_and_tamper(tmp_path):
    contract = {'registry': ['a', 'b', 'c'], 'features': {'sha256': 'x'}, 'state_contract': ToyEnv.state_contract}
    m = model(contract=contract); m.learn(ToyEnv(), 8); m.save(tmp_path)
    restored = MaskedDQN.load(tmp_path, expected_contract=contract)
    np.testing.assert_equal(m.q_values([.3, .7]), restored.q_values([.3, .7]))
    for v in m.replay.sample(2).values(): assert v.dtype != object
    assert len(restored.replay) == 8
    with pytest.raises(ValueError): MaskedDQN.load(tmp_path, expected_contract={'registry': ['c', 'b', 'a']})
    weight_path = tmp_path / 'weights.pt'
    weight_path.write_bytes(weight_path.read_bytes()+b'tamper')
    with pytest.raises(ValueError): MaskedDQN.load(tmp_path, expected_contract=contract)


def test_checkpoint_restores_rng_and_resumes_identically(tmp_path):
    m = model(seed=19); m.learn(ToyEnv(), 6); m.save(tmp_path)
    restored = MaskedDQN.load(tmp_path)
    ba,bb=m.replay.sample(2),restored.replay.sample(2)
    for key in ba: np.testing.assert_equal(ba[key],bb[key])
    assert [m.predict([0,1],[False,True,True],False,1.) for _ in range(10)] == [restored.predict([0,1],[False,True,True],False,1.) for _ in range(10)]
    ra,rb=m.learn(ToyEnv(),4),restored.learn(ToyEnv(),4)
    assert ra['losses']==rb['losses']


def test_input_and_hyperparameter_validation():
    with pytest.raises(ValueError): MaskedDQN(0,3)
    with pytest.raises(ValueError): model(gamma=2)
    with pytest.raises(ValueError): model(learning_rate=float('nan'))
    with pytest.raises(ValueError): model().q_values([float('nan'),0])
    with pytest.raises(ValueError): model().predict([0,0],[False,True,True],False,2)


def test_training_tracks_actual_shuffled_row_and_preserves_provenance_in_checkpoint(tmp_path):
    class Shuffled(ToyEnv):
        def reset(self, seed=None):
            obs, _ = super().reset(seed)
            return obs, {'student_ids': ['s1', 's2'], 'student_order': ['s2', 's1'],
                         'metadata': dict(self.training_provenance[0]['metadata']), 'problem_index': 0}
    m = model()
    report = m.learn(Shuffled(), 1)
    assert report['training_encountered_student_ids'] == ['s2']
    m.save(tmp_path)
    loaded = MaskedDQN.load(tmp_path)
    assert loaded.training_provenance == m.training_provenance


def test_reset_cannot_smuggle_rows_from_another_declared_cohort():
    class WrongCohort(ToyEnv):
        training_provenance = [*ToyEnv.training_provenance,
            {'problem_index': 1, 'student_ids': ['s3'], 'metadata': {'split': 'train'}}]
        def reset(self, seed=None):
            obs, _ = super().reset(seed)
            return obs, {'student_ids': ['s3'], 'problem_index': 0, 'metadata': {'split': 'train'}}
    m = model()
    with pytest.raises(ValueError): m.learn(WrongCohort(), 2)
    assert len(m.replay) == 0


def test_truncation_bootstraps_and_terminal_does_not():
    replay = ReplayBuffer(2, 1, 2)
    replay.add([0], 0, 1, [1], False, [True, False], truncated=True)
    replay.add([0], 0, 1, [1], True, [False, False])
    b = replay.sample(2)
    targets = masked_double_dqn_targets(b['rewards'], b['terminated'],
        [[2, 99], [2, 99]], [[10, 99], [10, 99]], b['next_masks'], .5)
    for done, value in zip(b['terminated'], targets):
        assert value == (1 if done else 6)


def test_contract_and_environment_dimensions_are_checked_before_training():
    from types import SimpleNamespace
    env=ToyEnv();env.observation_space=SimpleNamespace(shape=(99,));env.action_space=SimpleNamespace(n=3)
    with pytest.raises(ValueError): model().learn(env,2)
    env=ToyEnv()
    with pytest.raises(ValueError): model(contract={'state_contract': {'version': 'wrong'}}).learn(env,2)


def test_shared_environment_hall_trap_trains_and_rolls_out_valid_assignments(tmp_path):
    from src.domain.rebuild_matching import AllocationProblem
    from src.environment.rebuild_env import MatchingEnv
    problem = AllocationProblem(scores=np.array([[.9,.8],[.8,.1]]),
        available=np.ones((2,2),bool),student_ids=('s1','s2'),advisor_ids=('a1','a2'),
        capacities=np.array([1,1]),eligible=np.array([[True,True],[True,False]]),
        present=np.ones(2,bool),metadata={'split':'train','snapshot_sha256':'a'*64})
    env = MatchingEnv([problem],shuffle_students=True)
    m = MaskedDQN(env.observation_space.shape[0],env.action_space.n,
        hidden_sizes=(8,),batch_size=2,learning_starts=2,train_frequency=1,
        contract={'state_contract':env.state_contract})
    report=m.learn(env,8)
    assert report['episodes']==4 and report['training_unique_student_count']==2
    m.save(tmp_path);restored=MaskedDQN.load(tmp_path,expected_contract=m.contract)
    obs,_=env.reset(seed=17)
    terminated=False
    while not terminated:
        action=restored.predict(obs,env.action_masks())
        obs,_,terminated,_,info=env.step(action)
    assert info['final_validation']['valid'] and env.invalid_action_count==0


def test_checkpoint_metadata_tamper_and_replay_unknown_mask_rejected(tmp_path):
    m=model();m.learn(ToyEnv(),4);m.save(tmp_path)
    metadata_path=tmp_path/'metadata.json'
    metadata=json.loads(metadata_path.read_text())
    metadata['action_count']=99
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match='checksum'): MaskedDQN.load(tmp_path)
    replay=ReplayBuffer(2,2,3)
    with pytest.raises(ValueError): replay.add([1,2],0,1,[2,3],False,None)
    assert len(replay)==0


def test_nonfinite_or_unrepresentable_replay_reward_cannot_be_stored():
    replay=ReplayBuffer(2,2,3)
    for reward in (float('inf'),float('nan'),1e100):
        with pytest.raises(ValueError): replay.add([1,2],0,reward,[2,3],True,[False]*3)
    assert len(replay)==0


@pytest.mark.parametrize('feature_hash', [None, 'b'*64])
def test_declared_feature_contract_requires_exact_hash_in_every_training_cohort(feature_hash):
    env=ToyEnv()
    metadata={'split':'train','snapshot_sha256':'a'*64}
    if feature_hash is not None:
        metadata['feature_contract_sha256']=feature_hash
    env.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],'metadata':metadata}]
    m=model(contract={'state_contract':env.state_contract,'feature_contract_sha256':'a'*64})
    with pytest.raises(ValueError,match='feature contract'):
        m.learn(env,2)
    assert len(m.replay)==0 and m.total_timesteps==0


def test_matching_feature_contract_is_accepted():
    env=ToyEnv()
    env.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],
        'metadata':{'split':'train','feature_contract_sha256':'a'*64}}]
    m=model(contract={'state_contract':env.state_contract,'feature_contract_sha256':'a'*64})
    assert m.learn(env,2)['actual_timesteps']==2


def test_checkpoint_replay_with_stale_feature_provenance_is_rejected(tmp_path):
    env=ToyEnv()
    env.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],
        'metadata':{'split':'train','feature_contract_sha256':'a'*64}}]
    m=model(contract={'feature_contract_sha256':'a'*64})
    m.learn(env,2)
    # Emulate a legacy checkpoint produced before replay provenance was validated.
    m.training_provenance[0]['metadata'].pop('feature_contract_sha256')
    m.save(tmp_path)
    with pytest.raises(ValueError,match='feature contract'):
        MaskedDQN.load(tmp_path,expected_contract=m.contract)


@pytest.mark.parametrize('order_hash', [None, 'b'*64])
def test_taxonomy_order_contract_rejects_missing_or_different_train_semantics(order_hash):
    env=ToyEnv()
    metadata={'split':'train'}
    if order_hash is not None: metadata['taxonomy_feature_order_sha256']=order_hash
    env.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],'metadata':metadata}]
    m=model(contract={'taxonomy_feature_order_sha256':'a'*64})
    with pytest.raises(ValueError,match='contract'):
        m.learn(env,2)
    assert len(m.replay)==0


def test_taxonomy_order_checked_for_valid_train_and_persisted_replay(tmp_path):
    env=ToyEnv()
    env.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],
        'metadata':{'split':'train','taxonomy_feature_order_sha256':'a'*64}}]
    m=model(contract={'taxonomy_feature_order_sha256':'a'*64})
    assert m.learn(env,2)['actual_timesteps']==2
    m.save(tmp_path)
    MaskedDQN.load(tmp_path,expected_contract=m.contract)
    m.training_provenance[0]['metadata']['taxonomy_feature_order_sha256']='b'*64
    m.save(tmp_path)
    with pytest.raises(ValueError,match='contract'):
        MaskedDQN.load(tmp_path,expected_contract=m.contract)
