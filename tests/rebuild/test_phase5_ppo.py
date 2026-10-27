import numpy as np
import pytest
import torch

from test_phase5_matching import problem
from src.environment.rebuild_env import MatchingEnv


def test_masked_ppo_trains_and_safe_checkpoint_reproduces_policy(tmp_path):
    from src.rl.rebuild_ppo import MaskedPPOAgent
    torch.set_num_threads(1)
    env=MatchingEnv([problem(metadata={'split':'train','scope':'technical_fixture','feature_contract_sha256':'a'*64})],shuffle_students=True)
    contract={'state_contract':env.state_contract,'feature_contract_sha256':'a'*64}
    model=MaskedPPOAgent(env,seed=42,contract=contract,n_steps=16,batch_size=8,n_epochs=2,hidden_sizes=(16,16))
    report=model.learn(32)
    assert report['actual_timesteps']==32 and report['training_unique_student_count']==2
    assert report['losses'] and all(np.isfinite(row['loss']) for row in report['losses'])
    obs,_=env.reset(seed=42); mask=env.action_masks()
    mask[0]=False
    assert model.predict(obs,mask)==1
    probabilities=model.probabilities(obs,mask)
    assert probabilities[0]==0 and probabilities[1]==pytest.approx(1)
    path=tmp_path/'ppo'; model.save(path)
    loaded=MaskedPPOAgent.load(path,env,expected_contract=contract)
    np.testing.assert_array_equal(loaded.probabilities(obs,mask),probabilities)
    with pytest.raises(ValueError,match='contract'):
        MaskedPPOAgent.load(path,env,expected_contract={'state_contract':{}})
    (path/'state.pt').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='hash'):
        MaskedPPOAgent.load(path,env,expected_contract=contract)


def test_ppo_rejects_nontraining_cohorts_and_empty_action_mask():
    from src.rl.rebuild_ppo import MaskedPPOAgent
    torch.set_num_threads(1)
    env=MatchingEnv([problem(metadata={'split':'test'})])
    model=MaskedPPOAgent(env,seed=42,contract={'state_contract':env.state_contract},n_steps=8,batch_size=4,hidden_sizes=(8,))
    with pytest.raises(ValueError,match='train'):
        model.learn(8)
    obs,_=env.reset(seed=42)
    with pytest.raises(ValueError,match='valid_action'):
        model.predict(obs,np.zeros(2,dtype=bool))


def test_ppo_rejects_same_shape_but_different_feature_semantics():
    from src.rl.rebuild_ppo import MaskedPPOAgent
    env=MatchingEnv([problem(metadata={'split':'train','feature_contract_sha256':'b'*64})])
    with pytest.raises(ValueError,match='feature_contract'):
        MaskedPPOAgent(env,contract={'state_contract':env.state_contract,'feature_contract_sha256':'a'*64})
