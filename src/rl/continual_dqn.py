"""Research rehearsal adapter: immutable old-origin replay plus fresh current replay.

No semester outcome or production approval is inferred by this module. Phase-5
MaskedDQN remains unchanged; its action/target logic and optimizer are reused.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from src.rl.rebuild_dqn import MaskedDQN, ReplayBuffer, _hash, _integer, _json


REPRESENTATION_KEYS = ('state_contract', 'taxonomy_feature_order_sha256', 'reward_weights', 'quota_policy_version')
DATASET_KEYS = frozenset(('feature_contract_sha256', 'phase4_run_id', 'training_problem_sha256',
    'training_student_ids', 'snapshot_sha256', 'dataset_snapshot_sha256', 'semester_id',
    'training_semester_ids', 'data_cutoff_timestamp', 'source_dataset_sha256'))


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _registry(values, name):
    if not isinstance(values,list) or not values or any(not isinstance(v,str) or not v.strip() for v in values) or len(set(values)) != len(values):
        raise ValueError(f'invalid or duplicate {name} registry')


def validate_continual_contracts(old_contract, new_contract, *, bridge_proof=None):
    """Reject semantic changes; verify file-backed descriptor bridge for dataset changes.

    A descriptor binds feature_contract_sha256 and a representation object. The
    latter contains all REPRESENTATION_KEYS plus a nonempty feature_encoder dict
    describing the actual frozen encoder/normalization/fitted artifacts. Equal
    dimensionality alone is never a representation bridge.
    """
    if not isinstance(old_contract, dict) or not isinstance(new_contract, dict):
        raise ValueError('contracts must be objects')
    for contract in (old_contract,new_contract):
        state = contract.get('state_contract')
        if not isinstance(state,dict):
            raise ValueError('state contract required')
        _integer(state.get('dimension'),'state dimension')
        _registry(state.get('advisor_ids'),'advisor')
        if 'advisor_registry_sha256' in state and state['advisor_registry_sha256'] != _digest(state['advisor_ids']):
            raise ValueError('advisor registry hash mismatch')
        _registry(contract.get('training_student_ids'),'training student')
    for key in (*REPRESENTATION_KEYS, 'feature_contract_sha256'):
        if key not in old_contract or key not in new_contract or old_contract[key] is None or new_contract[key] is None:
            raise ValueError(f'missing required contract {key}')
    for key in REPRESENTATION_KEYS:
        if _json(old_contract[key]) != _json(new_contract[key]):
            raise ValueError(f'incompatible representation contract {key}')
    changed = sorted(key for key in set(old_contract) | set(new_contract)
                     if key not in old_contract or key not in new_contract or _json(old_contract[key]) != _json(new_contract[key]))
    if set(changed) - DATASET_KEYS:
        raise ValueError('unmapped contract change: ' + ','.join(set(changed) - DATASET_KEYS))
    report = dict(compatible=True, scope='research_rehearsal', changed_keys=changed,
                  old_contract_sha256=_digest(old_contract), new_contract_sha256=_digest(new_contract),
                  representation_sha256=_digest({key:old_contract[key] for key in REPRESENTATION_KEYS}),
                  bridge_proof_sha256=None, descriptor_documents=None)
    if not changed and bridge_proof is None:
        return report
    if not isinstance(bridge_proof, dict) or type(bridge_proof.get('version')) is not int or bridge_proof['version'] != 1:
        raise ValueError('dataset changes require explicit descriptor bridge proof')
    if bridge_proof.get('old_contract_sha256') != report['old_contract_sha256'] or bridge_proof.get('new_contract_sha256') != report['new_contract_sha256']:
        raise ValueError('bridge contract hashes mismatch')
    descriptors, resolved_artifacts = {}, {}
    for label, contract in (('old',old_contract), ('new',new_contract)):
        ref = bridge_proof.get(label+'_descriptor', {})
        if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not isinstance(ref.get('sha256'), str):
            raise ValueError('bridge descriptor reference invalid')
        path = Path(ref['path'])
        if _hash(path) != ref['sha256']:
            raise ValueError('bridge descriptor checksum mismatch')
        document = json.loads(path.read_text(encoding='utf-8'))
        representation = document.get('representation')
        if document.get('feature_contract_sha256') != contract['feature_contract_sha256'] or not isinstance(representation,dict):
            raise ValueError('descriptor feature binding missing or mismatched')
        if not isinstance(representation.get('feature_encoder'),dict) or not representation['feature_encoder']:
            raise ValueError('descriptor must describe frozen feature encoder')
        encoder = representation['feature_encoder']
        if not isinstance(encoder.get('version'),str) or not encoder['version'].strip() or not isinstance(encoder.get('artifacts'),list) or not encoder['artifacts']:
            raise ValueError('encoder version and actual artifacts required')
        refs = []
        for artifact in encoder['artifacts']:
            if not isinstance(artifact,dict) or not isinstance(artifact.get('path'),str) or not isinstance(artifact.get('sha256'),str):
                raise ValueError('invalid encoder artifact reference')
            artifact_path = Path(artifact['path'])
            if not artifact_path.is_absolute():
                artifact_path = path.parent/artifact_path
            if not artifact_path.is_file() or _hash(artifact_path) != artifact['sha256']:
                raise ValueError('encoder artifact checksum mismatch or missing')
            refs.append({**artifact,'path':str(artifact_path.resolve())})
        if not any(a.get('role') == 'code' and a['sha256'] == encoder.get('code_sha256') for a in refs):
            raise ValueError('encoder code hash must bind a verified code artifact')
        resolved_artifacts[label] = refs
        for key in REPRESENTATION_KEYS:
            if key not in representation or _json(representation[key]) != _json(contract[key]):
                raise ValueError(f'descriptor semantic binding mismatch {key}')
        descriptors[label] = document
    if _json(descriptors['old']['representation']) != _json(descriptors['new']['representation']):
        raise ValueError('feature encoder representation changed; rebuild required')
    report.update(bridge_proof_sha256=_digest(bridge_proof),descriptor_documents=descriptors,
                  representation_sha256=_digest(descriptors['old']['representation']),
                  encoder_artifacts=resolved_artifacts,
                  bridge_assurance='File integrity and descriptor equality; encoder adequacy requires external evidence review.')
    return report


class StratifiedReplay:
    """Pinned learner adapter. __len__ gates updates until each origin is ready."""
    def __init__(self, old, current, batch_size):
        self.batch_size = _integer(batch_size, 'batch_size', 2)
        if self.batch_size % 2 or old.observation_dim != current.observation_dim or old.action_count != current.action_count:
            raise ValueError('even batches and equal replay representation required')
        if len(old) < self.batch_size//2 or current.capacity < self.batch_size//2:
            raise ValueError('insufficient old replay or current buffer capacity')
        self.old, self.current = old, current
        self.origin_sample_counts = {'old':0, 'current':0}
        self.sample_batches = 0

    @property
    def ready(self):
        return min(len(self.old), len(self.current)) >= self.batch_size//2

    def __len__(self):
        return len(self.old)+len(self.current) if self.ready else 0

    def add(self, *args, **kwargs):
        if kwargs.get('current_mask') is None:
            raise ValueError('current-origin replay requires the actual current mask')
        self.current.add(*args, **kwargs)

    def sample(self, batch_size):
        batch_size = _integer(batch_size, 'batch_size', 2)
        if batch_size != self.batch_size or not self.ready:
            raise ValueError('exact configured half-origin batch not ready')
        half = batch_size//2
        old, current = self.old.sample(half), self.current.sample(half)
        result = {key:np.concatenate((old[key],current[key]),axis=0) for key in old}
        result['origins'] = np.array(['old']*half+['current']*half, dtype='<U7')
        self.origin_sample_counts['old'] += half
        self.origin_sample_counts['current'] += half
        self.sample_batches += 1
        return result


def _configuration(model, buffer_size=None):
    return dict(seed=model.seed, learning_rate=model.learning_rate, gamma=model.gamma,
                hidden_sizes=model.hidden_sizes, buffer_size=model.replay.capacity if buffer_size is None else buffer_size,
                batch_size=model.batch_size, learning_starts=model.learning_starts,
                target_update_interval=model.target_update_interval, train_frequency=model.train_frequency)


def _validate_old_provenance(model):
    if not len(model.replay) or not model.training_provenance:
        raise ValueError('old replay requires explicit train-only student provenance')
    state = model.contract['state_contract']
    if state['dimension'] != model.observation_dim or len(state['advisor_ids']) != model.action_count:
        raise ValueError('checkpoint state/action mapping contradicts contract')
    declared = model.contract.get('training_student_ids')
    if not isinstance(declared,list) or not declared or len(set(declared)) != len(declared):
        raise ValueError('old contract must declare exact training student registry')
    allowed = set(declared)
    for cohort in model.training_provenance:
        if cohort.get('metadata',{}).get('split') != 'train' or not cohort.get('student_ids') or not set(cohort['student_ids']).issubset(allowed):
            raise ValueError('old replay provenance contains undeclared/heldout students')
        if cohort['metadata'].get('policy_version') != model.contract['quota_policy_version']:
            raise ValueError('old replay quota policy mismatch or missing')


class ContinualDQN:
    """Warm-start candidate with separate, origin-preserving 50/50 replay."""
    @classmethod
    def from_checkpoint(cls, old_directory, *, old_contract, new_contract, bridge_proof=None, current_buffer_size=None):
        compatibility = validate_continual_contracts(old_contract,new_contract,bridge_proof=bridge_proof)
        old = MaskedDQN.load(old_directory, expected_contract=old_contract)
        _validate_old_provenance(old)
        candidate = MaskedDQN(old.observation_dim, old.action_count,
                             **_configuration(old,current_buffer_size),contract=new_contract)
        candidate.online.load_state_dict(old.online.state_dict())
        candidate.target.load_state_dict(old.target.state_dict())
        candidate.optimizer.load_state_dict(copy.deepcopy(old.optimizer.state_dict()))
        candidate.rng.bit_generator.state = copy.deepcopy(old.rng.bit_generator.state)
        for key in ('total_timesteps','gradient_updates','total_episodes'):
            setattr(candidate,key,getattr(old,key))
        result = cls._assemble(old,candidate,compatibility)
        result.source_checkpoint_sha256 = _hash(Path(old_directory)/'checksums.json')
        result.current_timesteps = 0
        return result

    @classmethod
    def _assemble(cls, old, candidate, compatibility):
        value = cls()
        value.old_model, value.model = old, candidate
        value.old_replay, value.current_replay = old.replay, candidate.replay
        value.replay = StratifiedReplay(value.old_replay,value.current_replay,candidate.batch_size)
        candidate.replay = value.replay
        value.compatibility = compatibility
        return value

    def q_values(self, observation):
        return self.model.q_values(observation)

    def predict(self, observation, action_masks, deterministic=True, epsilon=0.):
        return self.model.predict(observation, action_masks, deterministic, epsilon)

    def learn(self, env, total_timesteps, *, epsilon_start=1., epsilon_end=.05):
        # Pinned P5 validates source hashes/splits and masks. The adapter only
        # changes sampling; old metadata is never inserted in current provenance.
        declared = self.model.contract.get('training_student_ids')
        if not isinstance(declared,list) or not declared:
            raise ValueError('candidate contract must declare training student registry')
        provenance = getattr(env,'training_provenance',None)
        if not isinstance(provenance,list) or not provenance or any(
                not set(c.get('student_ids',[])).issubset(set(declared)) for c in provenance):
            raise ValueError('current replay rows outside candidate training registry')
        if _json(getattr(env,'reward_weights',None)) != _json(self.model.contract['reward_weights']):
            raise ValueError('current environment reward contract mismatch')
        if any(c.get('metadata',{}).get('policy_version') != self.model.contract['quota_policy_version'] for c in provenance):
            raise ValueError('current cohort quota policy mismatch or missing')
        before = dict(self.replay.origin_sample_counts)
        report = self.model.learn(env,total_timesteps,epsilon_start=epsilon_start,epsilon_end=epsilon_end)
        self.current_timesteps += report['actual_timesteps']
        report.update(scope='research_rehearsal', current_timesteps=self.current_timesteps,
            replay_origin_samples={key:self.replay.origin_sample_counts[key]-before[key] for key in before},
            replay_origin_rows={'old':len(self.old_replay),'current':len(self.current_replay)},
            old_training_provenance=copy.deepcopy(self.old_model.training_provenance),
            current_training_provenance=copy.deepcopy(self.model.training_provenance),
            compatibility=copy.deepcopy(self.compatibility), source_checkpoint_sha256=self.source_checkpoint_sha256)
        return report

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True,exist_ok=True)
        self.old_model.save(directory/'old')
        self.model.replay = self.current_replay
        try:
            self.model.save(directory/'candidate')
        finally:
            self.model.replay = self.replay
        proof = None
        documents = self.compatibility['descriptor_documents']
        artifact_names = []
        if documents is not None:
            documents = copy.deepcopy(documents)
            proof = dict(version=1,old_contract_sha256=_digest(self.old_model.contract),new_contract_sha256=_digest(self.model.contract))
            (directory/'bridge').mkdir(exist_ok=True)
            (directory/'bridge/encoder_artifacts').mkdir(exist_ok=True)
            for index,artifact in enumerate(self.compatibility['encoder_artifacts']['old']):
                relative = f'bridge/encoder_artifacts/{index}.bin'
                source = Path(artifact['path'])
                if _hash(source) != artifact['sha256']:
                    raise ValueError('encoder artifact changed since bridge validation')
                (directory/relative).write_bytes(source.read_bytes())
                artifact_names.append(relative)
                for label in ('old','new'):
                    documents[label]['representation']['feature_encoder']['artifacts'][index]['path'] = f'encoder_artifacts/{index}.bin'
            for label in ('old','new'):
                relative = f'bridge/{label}_descriptor.json'
                path = directory/relative
                path.write_text(_json(documents[label]),encoding='utf-8')
                proof[label+'_descriptor'] = {'path':relative,'sha256':_hash(path)}
        manifest = dict(version=1,algorithm='continual_masked_double_dqn',scope='research_rehearsal',
            old_contract=self.old_model.contract,new_contract=self.model.contract,bridge_proof=proof,
            source_checkpoint_sha256=self.source_checkpoint_sha256,current_timesteps=self.current_timesteps,
            sample_batches=self.replay.sample_batches,origin_sample_counts=self.replay.origin_sample_counts,
            original_bridge_proof_sha256=self.compatibility['bridge_proof_sha256'],encoder_artifact_count=len(artifact_names))
        (directory/'continual.json').write_text(_json(manifest),encoding='utf-8')
        names = ['continual.json']+[f'{label}/{name}' for label in ('old','candidate')
            for name in ('weights.pt','replay.npz','metadata.json','checksums.json')]
        if proof:
            names += [proof[label+'_descriptor']['path'] for label in ('old','new')]
            names += artifact_names
        (directory/'continual_checksums.json').write_text(_json({name:_hash(directory/name) for name in names}),encoding='utf-8')
        return manifest

    @classmethod
    def load(cls, directory, expected_contract=None):
        directory = Path(directory)
        sums = json.loads((directory/'continual_checksums.json').read_text(encoding='utf-8'))
        required = {'continual.json'} | {f'{label}/{name}' for label in ('old','candidate')
            for name in ('weights.pt','replay.npz','metadata.json','checksums.json')}
        if 'continual.json' not in sums or _hash(directory/'continual.json') != sums['continual.json']:
            raise ValueError('continual checkpoint manifest checksum mismatch')
        manifest = json.loads((directory/'continual.json').read_text(encoding='utf-8'))
        count = _integer(manifest.get('encoder_artifact_count',0),'encoder_artifact_count',0)
        if count:
            required |= {'bridge/old_descriptor.json','bridge/new_descriptor.json'}
            required |= {f'bridge/encoder_artifacts/{i}.bin' for i in range(count)}
        if set(sums) != required or any(_hash(directory/name) != digest for name,digest in sums.items()):
            raise ValueError('continual checkpoint checksum mismatch')
        if type(manifest.get('version')) is not int or manifest['version'] != 1 or manifest.get('algorithm') != 'continual_masked_double_dqn' or manifest.get('scope') != 'research_rehearsal':
            raise ValueError('unsupported continual checkpoint')
        if expected_contract is not None and _json(expected_contract) != _json(manifest['new_contract']):
            raise ValueError('candidate contract mismatch')
        proof = copy.deepcopy(manifest['bridge_proof'])
        if proof:
            for label in ('old','new'):
                ref = proof[label+'_descriptor']
                expected_path = f'bridge/{label}_descriptor.json'
                if ref.get('path') != expected_path:
                    raise ValueError('invalid embedded descriptor path')
                document = json.loads((directory/expected_path).read_text(encoding='utf-8'))
                artifacts = document.get('representation',{}).get('feature_encoder',{}).get('artifacts',[])
                if len(artifacts) != count or any(a.get('path') != f'encoder_artifacts/{i}.bin' for i,a in enumerate(artifacts)):
                    raise ValueError('invalid embedded encoder artifact paths')
                ref['path'] = str(directory/expected_path)
        compatibility = validate_continual_contracts(manifest['old_contract'],manifest['new_contract'],bridge_proof=proof)
        old = MaskedDQN.load(directory/'old',expected_contract=manifest['old_contract'])
        _validate_old_provenance(old)
        candidate = MaskedDQN.load(directory/'candidate',expected_contract=manifest['new_contract'])
        if candidate.observation_dim != old.observation_dim or candidate.action_count != old.action_count:
            raise ValueError('checkpoint action/state dimensions differ')
        declared = candidate.contract.get('training_student_ids',[])
        if any(not set(c['student_ids']).issubset(set(declared)) for c in candidate.training_provenance):
            raise ValueError('candidate replay student provenance mismatch')
        value = cls._assemble(old,candidate,compatibility)
        counts = manifest['origin_sample_counts']
        batches = _integer(manifest['sample_batches'],'sample_batches',0)
        if set(counts) != {'old','current'} or any(_integer(counts[k],k,0) != batches*candidate.batch_size//2 for k in counts):
            raise ValueError('invalid stratified sampling counters')
        value.replay.origin_sample_counts = counts
        value.replay.sample_batches = batches
        value.current_timesteps = _integer(manifest['current_timesteps'],'current_timesteps',0)
        value.source_checkpoint_sha256 = manifest['source_checkpoint_sha256']
        return value
