"""MaskablePPO with explicit masks, train-only provenance and state-only saves."""
import json
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

from src.data_pipeline.reconcile import _digest
from src.data_pipeline.review_decisions import record_hash


class _TrainingLog(BaseCallback):
    def __init__(self,allowed_students):
        super().__init__(); self.students=set(); self.losses=[]; self.episodes=0
        self.allowed_students=set(allowed_students)

    def _on_step(self):
        for info in self.locals.get('infos',[]):
            decision=info.get('decision')
            if decision:
                if decision['student_id'] not in self.allowed_students:
                    raise ValueError('ppo_rollout_outside_training_cohorts')
                self.students.add(decision['student_id'])
            if info.get('final_validation'): self.episodes+=1
        return True

    def _capture(self):
        values=self.model.logger.name_to_value
        loss=values.get('train/loss')
        if loss is not None:
            if not np.isfinite(loss): raise ValueError('nonfinite_ppo_training_loss')
            self.losses.append({'timesteps':int(self.model.num_timesteps),'loss':float(loss),
                'policy_gradient_loss':float(values['train/policy_gradient_loss']),
                'value_loss':float(values['train/value_loss']),
                'entropy_loss':float(values['train/entropy_loss']),
                'approx_kl':float(values['train/approx_kl'])})

    def _on_rollout_end(self): self._capture()
    def _on_training_end(self): self._capture()


class MaskedPPOAgent:
    def __init__(self,env,*,seed=42,contract=None,n_steps=256,batch_size=64,n_epochs=5,
                 hidden_sizes=(128,128),learning_rate=3e-4,gamma=.99):
        self.contract=json.loads(json.dumps(contract or {},allow_nan=False))
        if self.contract.get('state_contract',env.state_contract)!=env.state_contract:
            raise ValueError('ppo_environment_contract_mismatch')
        for key in ('feature_contract_sha256','taxonomy_feature_order_sha256'):
            if key in self.contract and any(row['metadata'].get(key)!=self.contract[key] for row in env.training_provenance):
                raise ValueError('ppo_'+key+'_mismatch')
        self.env=env
        self.config={'seed':seed,'n_steps':n_steps,'batch_size':batch_size,'n_epochs':n_epochs,
                     'hidden_sizes':list(hidden_sizes),'learning_rate':learning_rate,'gamma':gamma}
        self.model=MaskablePPO('MlpPolicy',env,seed=seed,device='cpu',verbose=0,
            n_steps=n_steps,batch_size=batch_size,n_epochs=n_epochs,learning_rate=learning_rate,gamma=gamma,
            policy_kwargs={'net_arch':list(hidden_sizes)})

    def _mask(self,observation,action_masks):
        mask=np.asarray(action_masks); obs=np.asarray(observation,dtype=np.float32)
        if (mask.dtype!=np.bool_ or mask.shape!=(self.env.action_space.n,) or not mask.any()
                or obs.shape!=self.env.observation_space.shape or not np.isfinite(obs).all()):
            raise ValueError('valid_action_mask_and_observation_required')
        return obs,mask

    def predict(self,observation,action_masks,deterministic=True):
        obs,mask=self._mask(observation,action_masks)
        action,_=self.model.predict(obs,deterministic=deterministic,action_masks=mask)
        action=int(action)
        if not mask[action]: raise RuntimeError('ppo_mask_violation')
        return action

    def probabilities(self,observation,action_masks):
        obs,mask=self._mask(observation,action_masks)
        self.model.policy.set_training_mode(False)
        with torch.no_grad():
            tensor,_=self.model.policy.obs_to_tensor(obs)
            distribution=self.model.policy.get_distribution(tensor,action_masks=mask.reshape(1,-1))
            values=distribution.distribution.probs.cpu().numpy()[0]
        if not np.isfinite(values).all() or (values[~mask]!=0).any():
            raise RuntimeError('invalid_masked_ppo_probabilities')
        return values

    def learn(self,total_timesteps):
        provenance=self.env.training_provenance
        if not provenance or any(row['metadata'].get('split')!='train' for row in provenance):
            raise ValueError('ppo_train_only_cohorts_required')
        if type(total_timesteps) is not int or total_timesteps<1:
            raise ValueError('positive_training_timesteps_required')
        log=_TrainingLog({s for row in provenance for s in row['student_ids']}); before=int(self.model.num_timesteps)
        self.model.learn(total_timesteps=total_timesteps,callback=log,reset_num_timesteps=False)
        return {'requested_timesteps':total_timesteps,'actual_timesteps':int(self.model.num_timesteps)-before,
            'epochs_completed':int(self.model._n_updates),'episodes':log.episodes,'losses':log.losses,
            'training_unique_student_count':len(log.students),
            'training_available_student_count':len({s for row in provenance for s in row['student_ids']}),
            'training_provenance':provenance,'training_provenance_sha256':record_hash(provenance),
            'contract_sha256':record_hash(self.contract),'seed':self.config['seed'],
            'algorithm':'MaskablePPO','artifact_policy':'State dictionaries only; never arbitrary cloudpickle model loading.'}

    def save(self,directory):
        directory=Path(directory); directory.mkdir(parents=True,exist_ok=False)
        torch.save({'policy':self.model.policy.state_dict(),'optimizer':self.model.policy.optimizer.state_dict(),
                    'num_timesteps':int(self.model.num_timesteps)},directory/'state.pt')
        metadata={'algorithm':'MaskablePPO','schema_version':'rebuild-ppo/1.0','config':self.config,
                  'contract':self.contract,'state_contract':self.env.state_contract,'state_sha256':_digest(directory/'state.pt')}
        metadata['manifest_sha256']=record_hash(metadata)
        (directory/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')

    @classmethod
    def load(cls,directory,env,*,expected_contract):
        directory=Path(directory); metadata=json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        expected=metadata.pop('manifest_sha256')
        if record_hash(metadata)!=expected or _digest(directory/'state.pt')!=metadata['state_sha256']:
            raise ValueError('ppo_checkpoint_hash_mismatch')
        if (metadata['contract']!=expected_contract or metadata['state_contract']!=env.state_contract
                or metadata['schema_version']!='rebuild-ppo/1.0'):
            raise ValueError('ppo_checkpoint_contract_mismatch')
        result=cls(env,contract=expected_contract,**metadata['config'])
        state=torch.load(directory/'state.pt',map_location='cpu',weights_only=True)
        result.model.policy.load_state_dict(state['policy'])
        result.model.policy.optimizer.load_state_dict(state['optimizer'])
        result.model.num_timesteps=state['num_timesteps']
        result.model.policy.set_training_mode(False)
        return result
