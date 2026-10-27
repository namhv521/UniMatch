import copy
import hashlib
import json

import numpy as np
import pytest

from src.rl.rebuild_dqn import MaskedDQN
from src.rl.continual_dqn import ContinualDQN, StratifiedReplay, validate_continual_contracts


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def contract():
    return {'state_contract':{'dimension':2,'advisor_ids':['a','b'],'env_version':'fixture/1'},
        'taxonomy_feature_order_sha256':'t'*64,'reward_weights':{'score':1},
        'quota_policy_version':'equal/1','feature_contract_sha256':'f'*64,
        'training_student_ids':['s1','s2'],'scope':'research_only'}


class Env:
    state_contract=contract()['state_contract']
    reward_weights=contract()['reward_weights']
    def __init__(self,feature_hash='f'*64,split='train'):
        self.training_provenance=[{'problem_index':0,'student_ids':['s1','s2'],
            'metadata':{'split':split,'feature_contract_sha256':feature_hash,
                        'taxonomy_feature_order_sha256':'t'*64,'policy_version':'equal/1'}}]
    def reset(self,seed=None):
        self.pos=0
        return np.array([0,1],np.float32),{'problem_index':0,'student_ids':['s1','s2'],
            'metadata':copy.deepcopy(self.training_provenance[0]['metadata'])}
    def action_masks(self): return np.array([False,False]) if self.pos==2 else np.array([True,True])
    def step(self,action):
        assert self.action_masks()[action]
        self.pos+=1
        return np.array([self.pos,1],np.float32),1.,self.pos==2,False,{}


@pytest.fixture
def old_checkpoint(tmp_path):
    model=MaskedDQN(2,2,hidden_sizes=(4,),batch_size=4,learning_starts=2,
        train_frequency=1,target_update_interval=2,buffer_size=20,contract=contract())
    model.learn(Env(),8)
    directory=tmp_path/'old'
    model.save(directory)
    return directory


def test_equal_contract_and_representation_changes_rejected():
    old=contract()
    assert validate_continual_contracts(old,copy.deepcopy(old))['compatible']
    for key in ('state_contract','taxonomy_feature_order_sha256','reward_weights','quota_policy_version'):
        new=copy.deepcopy(old);new[key]={'changed':True}
        with pytest.raises(ValueError): validate_continual_contracts(old,new)
    new={**old,'unknown_future_flag':True}
    with pytest.raises(ValueError): validate_continual_contracts(old,new)


def bridge(tmp_path,old,new,changed_encoder=False):
    representation={k:old[k] for k in ('state_contract','taxonomy_feature_order_sha256','reward_weights','quota_policy_version')}
    artifact=tmp_path/'encoder.py';artifact.write_text('fixture frozen encoder')
    artifact_hash=hashlib.sha256(artifact.read_bytes()).hexdigest()
    representation['feature_encoder']={'version':'fixed-encoder/1','vocabulary_sha256':'v'*64,
        'code_sha256':artifact_hash,'artifacts':[{'path':str(artifact),'sha256':artifact_hash,'role':'code'}]}
    refs=[]
    for label,c in [('old',old),('new',new)]:
        rep=copy.deepcopy(representation)
        if label=='new' and changed_encoder: rep['feature_encoder']['version']='different/2'
        path=tmp_path/(label+'-descriptor.json')
        path.write_text(json.dumps({'feature_contract_sha256':c['feature_contract_sha256'],'representation':rep}))
        refs.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'version':1,'old_contract_sha256':canonical_hash(old),'new_contract_sha256':canonical_hash(new),
            'old_descriptor':refs[0],'new_descriptor':refs[1]}


def test_changed_data_requires_verified_equal_representation_bridge(tmp_path):
    old=contract();new={**old,'feature_contract_sha256':'n'*64,'training_student_ids':['s3']}
    with pytest.raises(ValueError): validate_continual_contracts(old,new)
    proof=bridge(tmp_path,old,new)
    report=validate_continual_contracts(old,new,bridge_proof=proof)
    assert report['compatible'] and report['bridge_proof_sha256']==canonical_hash(proof)
    proof['new_descriptor']['sha256']='0'*64
    with pytest.raises(ValueError): validate_continual_contracts(old,new,bridge_proof=proof)


def test_bridge_cannot_hide_encoder_semantic_change(tmp_path):
    old=contract();new={**old,'feature_contract_sha256':'n'*64}
    with pytest.raises(ValueError):
        validate_continual_contracts(old,new,bridge_proof=bridge(tmp_path,old,new,True))


def test_warmstart_q_parity_and_exact_half_batches_without_old_mutation(old_checkpoint):
    old=MaskedDQN.load(old_checkpoint,expected_contract=contract())
    continual=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())
    np.testing.assert_array_equal(old.q_values([0,1]),continual.q_values([0,1]))
    old_arrays={k:v.copy() for k,v in continual.old_replay.data.items()}
    report=continual.learn(Env(),4)
    assert report['actual_timesteps']==4 and report['gradient_updates']==3
    assert report['replay_origin_samples']=={'old':6,'current':6}
    assert len(continual.current_replay)==4 and len(continual.old_replay)==8
    assert continual.model.training_provenance==Env().training_provenance
    for k,v in old_arrays.items(): np.testing.assert_array_equal(v,continual.old_replay.data[k])
    batch=continual.replay.sample(4)
    assert list(batch['origins']).count('old')==2 and list(batch['origins']).count('current')==2


def test_new_buffer_warmup_prevents_old_only_training(old_checkpoint):
    continual=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())
    report=continual.learn(Env(),1)
    assert report['gradient_updates']==0 and report['losses']==[]
    assert report['replay_origin_samples']=={'old':0,'current':0}
    with pytest.raises(ValueError): continual.replay.sample(4)


def test_train_only_and_registry_guards(old_checkpoint):
    new={**contract(),'state_contract':{'dimension':2,'advisor_ids':['b','a'],'env_version':'fixture/1'}}
    with pytest.raises(ValueError): ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=new)
    c=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())
    with pytest.raises(ValueError): c.learn(Env(split='test'),2)
    with pytest.raises(ValueError): c.learn(Env(feature_hash='wrong'),2)
    assert len(c.current_replay)==0


def test_checkpoint_preserves_origins_counters_rng_and_inference(old_checkpoint,tmp_path):
    c=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())
    c.learn(Env(),4)
    path=tmp_path/'continual';c.save(path)
    loaded=ContinualDQN.load(path,expected_contract=contract())
    np.testing.assert_array_equal(c.q_values([.1,.2]),loaded.q_values([.1,.2]))
    assert loaded.old_model.contract==contract() and loaded.model.contract==contract()
    assert loaded.old_model.training_provenance==c.old_model.training_provenance
    assert loaded.replay.origin_sample_counts==c.replay.origin_sample_counts
    ba,bb=c.replay.sample(4),loaded.replay.sample(4)
    for key in ba: np.testing.assert_array_equal(ba[key],bb[key])
    ra,rb=c.learn(Env(),4),loaded.learn(Env(),4)
    assert ra['losses']==rb['losses']
    path.joinpath('candidate','replay.npz').write_bytes(b'tamper')
    with pytest.raises(ValueError): ContinualDQN.load(path,expected_contract=contract())


def test_bridge_checkpoint_portable_and_old_provenance_not_relabelled(old_checkpoint,tmp_path):
    old=contract();new={**old,'feature_contract_sha256':'n'*64}
    proof=bridge(tmp_path,old,new)
    c=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=old,new_contract=new,bridge_proof=proof)
    c.learn(Env(feature_hash='n'*64),4)
    assert c.old_model.training_provenance[0]['metadata']['feature_contract_sha256']=='f'*64
    assert c.model.training_provenance[0]['metadata']['feature_contract_sha256']=='n'*64
    path=tmp_path/'continued';c.save(path)
    for key in ('old_descriptor','new_descriptor'):
        from pathlib import Path
        Path(proof[key]['path']).unlink()
    (tmp_path/'encoder.py').unlink()
    loaded=ContinualDQN.load(path,expected_contract=new)
    np.testing.assert_array_equal(c.q_values([0,1]),loaded.q_values([0,1]))


def test_wrong_old_contract_fails_strict_loading(old_checkpoint):
    old={**contract(),'feature_contract_sha256':'wrong'}
    with pytest.raises(ValueError): ContinualDQN.from_checkpoint(old_checkpoint,old_contract=old,new_contract=old)


def test_actual_environment_reward_and_quota_semantics_are_checked(old_checkpoint):
    c=ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())
    env=Env();env.reward_weights={'score':.5}
    with pytest.raises(ValueError,match='reward'): c.learn(env,2)
    env=Env();env.training_provenance[0]['metadata']['policy_version']='other/2'
    with pytest.raises(ValueError,match='quota'): c.learn(env,2)
    assert len(c.current_replay)==0


def test_odd_batches_and_old_replay_undeclared_students_rejected(old_checkpoint):
    from src.rl.rebuild_dqn import ReplayBuffer
    old=ReplayBuffer(8,2,2);current=ReplayBuffer(8,2,2)
    for _ in range(4): old.add([0,1],0,1,[0,1],True,[False,False])
    with pytest.raises(ValueError): StratifiedReplay(old,current,3)
    loaded=MaskedDQN.load(old_checkpoint)
    loaded.training_provenance[0]['student_ids'].append('heldout-id')
    loaded.save(old_checkpoint)
    with pytest.raises(ValueError,match='undeclared'): ContinualDQN.from_checkpoint(old_checkpoint,old_contract=contract(),new_contract=contract())


def test_bridge_rejects_tampered_actual_encoder_file(tmp_path):
    old=contract();new={**old,'feature_contract_sha256':'n'*64}
    proof=bridge(tmp_path,old,new)
    (tmp_path/'encoder.py').write_text('changed code same descriptors')
    with pytest.raises(ValueError,match='artifact'):
        validate_continual_contracts(old,new,bridge_proof=proof)


@pytest.mark.parametrize('field,value', [('advisor_ids',['a','a']),('dimension',True),('dimension',0)])
def test_invalid_duplicate_or_dimension_state_contract_rejected(field,value):
    c=contract();c['state_contract'][field]=value
    with pytest.raises(ValueError): validate_continual_contracts(c,c)


def test_contract_duplicate_students_rejected():
    c=contract();c['training_student_ids']=['s1','s1']
    with pytest.raises(ValueError): validate_continual_contracts(c,c)
