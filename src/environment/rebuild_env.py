"""Shared masked allocation MDP; outputs proposals, never academic approvals."""
from __future__ import annotations

import hashlib
import json
from numbers import Integral, Real

import gymnasium as gym
import numpy as np

from src.domain.rebuild_matching import AllocationProblem, action_mask, feasible, validate_assignments


ENV_VERSION = 'rebuild-matching-env/1.0'
STATE_CONTRACT_VERSION = '9M+2K+1/1.0'
CANDIDATE_LAYOUT = ('current_scores','remaining_ratios','normalized_loads','current_allowed',
                    'remaining_demand_fraction','present','score_available','current_preferences','preference_known')
DEFAULT_REWARD_WEIGHTS = {'score':1.0,'preference':.1,'fairness':.15,'terminal_completion':1.0}


class MatchingEnv(gym.Env):
    """One complete cohort per episode with immutable advisor action semantics."""
    metadata = {'render_modes': []}

    def __init__(self, problems: list[AllocationProblem], *, shuffle_students=False, reward_weights=None):
        super().__init__()
        if not problems or any(not isinstance(p,AllocationProblem) for p in problems):
            raise ValueError('allocation_problems_required')
        self.problems = tuple(problems)
        self.advisor_ids = tuple(self.problems[0].advisor_ids)
        self.feature_dimension = self.problems[0].student_features.shape[1]
        if any(tuple(p.advisor_ids)!=self.advisor_ids for p in self.problems):
            raise ValueError('advisor_registry_mismatch')
        if any(p.student_features.shape[1]!=self.feature_dimension for p in self.problems):
            raise ValueError('student_feature_dimension_mismatch')
        if any(((p.student_features<0)|(p.student_features>1)).any() for p in self.problems):
            raise ValueError('student_features_outside_unit_interval')
        if type(shuffle_students) is not bool: raise ValueError('shuffle_students_must_be_boolean')
        self.shuffle_students = shuffle_students
        self.reward_weights = dict(DEFAULT_REWARD_WEIGHTS)
        if reward_weights is not None:
            if not isinstance(reward_weights,dict) or set(reward_weights)-set(self.reward_weights):
                raise ValueError('invalid_reward_weights')
            self.reward_weights.update(reward_weights)
        if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real) or not np.isfinite(v) or v<0
               for v in self.reward_weights.values()): raise ValueError('invalid_reward_weights')
        if any(not np.isclose(self.reward_weights['preference'],p.preference_weight,atol=1e-12,rtol=0)
               for p in self.problems): raise ValueError('preference_weight_mismatch')
        self.action_space = gym.spaces.Discrete(len(self.advisor_ids))
        self.observation_space = gym.spaces.Box(0,1,shape=(9*len(self.advisor_ids)+2*self.feature_dimension+1,),dtype=np.float32)
        cursor, layout = 0, {}
        for name,size in [(name,len(self.advisor_ids)) for name in CANDIDATE_LAYOUT]+[
                ('student_features',self.feature_dimension),('student_feature_known',self.feature_dimension),('remaining_student_fraction',1)]:
            layout[name] = [cursor,cursor+size];cursor += size
        registry_hash = hashlib.sha256(json.dumps(self.advisor_ids,separators=(',',':')).encode()).hexdigest()
        self.state_contract = {'env_version':ENV_VERSION,'version':STATE_CONTRACT_VERSION,'layout':layout,
            'advisor_ids':list(self.advisor_ids),'advisor_registry_sha256':registry_hash,
            'feature_dimension':self.feature_dimension,'dimension':cursor,'dtype':'float32',
            'unknown_policy':'Storage zero is meaningful only with corresponding known/presence masks.'}
        self.problem = self.problems[0]
        self.problem_index = 0
        self.remaining_students = []
        self.remaining_capacities = np.array(self.problem.capacities,copy=True)
        self.assignments, self.trace = {}, []
        self.invalid_action_count = 0
        self._done = True
        self._mask_cache = None

    @property
    def current_problem(self): return self.problem

    @property
    def training_provenance(self):
        return [{'problem_index':i,'student_ids':list(p.student_ids),'metadata':dict(p.metadata)}
                for i,p in enumerate(self.problems)]

    def action_masks(self):
        if self._done: return np.zeros(len(self.advisor_ids),dtype=bool)
        if self._mask_cache is None:
            self._mask_cache = np.asarray(action_mask(self.problem,self.remaining_students,self.remaining_capacities),dtype=bool)
        return self._mask_cache.copy()

    def _loads(self): return np.asarray(self.problem.capacities)-self.remaining_capacities

    def _ratios(self,values):
        result=np.zeros(len(self.advisor_ids),dtype=np.float64)
        np.divide(values,self.problem.capacities,out=result,where=np.asarray(self.problem.capacities)>0)
        return result*np.asarray(self.problem.present,dtype=bool)

    def _potential(self):
        included=np.asarray(self.problem.present,dtype=bool)&(np.asarray(self.problem.capacities)>0)
        return -float(np.var(self._ratios(self._loads())[included])) if included.any() else 0.0

    def observation(self):
        if self._done: return np.zeros(self.observation_space.shape,dtype=np.float32)
        p=self.problem;i=self.remaining_students[0]
        present=np.asarray(p.present,dtype=bool)
        known=np.asarray(p.available[i],dtype=bool)&present
        pref_known=np.asarray(p.preference_known[i],dtype=bool)&present
        features_known=np.asarray(p.student_feature_known[i],dtype=bool)
        demand=np.asarray(p.allowed[self.remaining_students],dtype=bool).mean(axis=0)
        demand *= present&(self.remaining_capacities>0)
        values=[np.where(known,p.scores[i],0),self._ratios(self.remaining_capacities),self._ratios(self._loads()),
                self.action_masks(),demand,present,known,np.where(pref_known,p.preferences[i],0),pref_known,
                np.where(features_known,p.student_features[i],0),features_known,
                [len(self.remaining_students)/len(p.student_ids)]]
        return np.concatenate(values).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        # A rejected reset must not leave a previous allocation episode usable.
        self._done,self._mask_cache=True,None
        options=dict(options or {})
        if set(options)-{'problem_index','student_order'}: raise ValueError('invalid_reset_options')
        index=options.get('problem_index')
        if index is None: index=int(self.np_random.integers(len(self.problems)))
        if isinstance(index,(bool,np.bool_)) or not isinstance(index,Integral) or not 0<=index<len(self.problems):
            raise ValueError('invalid_problem_index')
        p=self.problems[int(index)];order=list(range(len(p.student_ids)))
        requested=options.get('student_order')
        if requested is not None:
            converted=[]
            for value in requested:
                if isinstance(value,str) and value in p.student_ids: converted.append(p.student_ids.index(value))
                elif isinstance(value,Integral) and not isinstance(value,(bool,np.bool_)): converted.append(int(value))
                else: raise ValueError('invalid_student_order')
            if sorted(converted)!=order: raise ValueError('invalid_student_order')
            order=converted
        elif self.shuffle_students:
            order=list(map(int,self.np_random.permutation(order)))
        capacities=np.array(p.capacities,copy=True)
        if not feasible(p,remaining_students=order,remaining_capacities=capacities):
            if capacities.sum()<len(order): reason='INSUFFICIENT_CAPACITY'
            elif any(not np.asarray(p.allowed[i],dtype=bool).any() for i in order): reason='STUDENT_WITHOUT_ALLOWED_PAIR'
            else: reason='GLOBAL_MATCHING_OR_FIXED_ASSIGNMENT_CONFLICT'
            raise ValueError('infeasible_problem:'+reason)
        self.problem,self.problem_index=p,int(index)
        self.remaining_students,self.remaining_capacities=order,capacities
        self.assignments,self.trace={},[]
        self.invalid_action_count=0
        self._done=not bool(order)
        self._mask_cache=None
        self._student_order=[p.student_ids[i] for i in order]
        info={'problem_index':self.problem_index,'student_order':list(self._student_order),
              'student_ids':list(p.student_ids),'metadata':dict(p.metadata),'seed':seed,
              'state_contract':self.state_contract,'invalid_action_count':0}
        return self.observation(),info

    def step(self,action):
        if self._done: raise ValueError('episode_done')
        mask=self.action_masks()
        if (isinstance(action,(bool,np.bool_)) or not isinstance(action,Integral)
                or not 0<=action<len(self.advisor_ids) or not mask[int(action)]):
            self.invalid_action_count += 1
            raise ValueError('invalid_action')
        j=int(action);p=self.problem;i=self.remaining_students[0]
        loads_before=self._loads().tolist();potential_before=self._potential()
        score_known=bool(p.available[i,j]);preference_known=bool(p.preference_known[i,j])
        score=float(p.scores[i,j]) if score_known else 0.0
        preference=float(p.preferences[i,j]) if preference_known else 0.0
        self.assignments[p.student_ids[i]]=self.advisor_ids[j]
        self.remaining_capacities[j]-=1
        self.remaining_students=self.remaining_students[1:]
        self._done=not bool(self.remaining_students)
        self._mask_cache=None
        potential_after=self._potential()
        weights=self.reward_weights
        components={'score':float(weights['score']*score),'preference':float(weights['preference']*preference),
                    'fairness':float(weights['fairness']*(potential_after-potential_before)),
                    'terminal_completion':float(weights['terminal_completion'] if self._done else 0)}
        reward=float(sum(components.values()))
        decision={'step':len(self.trace),'student_id':p.student_ids[i],'advisor_id':self.advisor_ids[j],
                  'action_index':j,'pre_action_mask':mask.tolist(),'score':score if score_known else None,
                  'score_known':score_known,'preference':preference if preference_known else None,
                  'preference_known':preference_known,'reward_components':components,'total_reward':reward,
                  'capacities':np.asarray(p.capacities).tolist(),'loads_before':loads_before,'loads_after':self._loads().tolist(),
                  'potential_before':potential_before,'potential_after':potential_after,
                  'advisor_registry':list(self.advisor_ids),'advisor_registry_sha256':self.state_contract['advisor_registry_sha256'],
                  'env_version':ENV_VERSION,'state_contract_version':STATE_CONTRACT_VERSION,
                  'problem_index':self.problem_index,'student_order':list(self._student_order)}
        self.trace.append(decision)
        info={'decision':decision,'invalid_action_count':self.invalid_action_count}
        if self._done:
            validation=validate_assignments(p,[{'student_id':s,'advisor_id':a} for s,a in self.assignments.items()])
            info['final_validation']=validation
            if not validation['valid']: raise RuntimeError('terminal_assignment_invalid')
        return self.observation(),reward,self._done,False,info
