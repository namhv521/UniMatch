"""Holdout evaluation with explicit repair accounting and data provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from src.baselines.greedy import greedy_assignment
from src.baselines.hungarian import hungarian_assignment
from src.baselines.random import random_assignment
from src.environment.matching_env import MatchingEnv
from src.evaluation.metrics import load_variance, mean_compatibility, quota_violations


def load_split(root: Path, split='validation'):
    manifest_path = root / 'data/features/feature_manifest_v2.json'
    split_path = root / 'data/curated/split_indices.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    scores = np.load(root / 'data/features/compatibility_matrix_v2.npy', allow_pickle=False)
    if hashlib.sha256(scores.tobytes()).hexdigest() != manifest['matrix_sha256']:
        raise ValueError('feature hash mismatch')
    if hashlib.sha256(split_path.read_bytes()).hexdigest() != manifest['split_sha256']:
        raise ValueError('split hash mismatch')
    splits = json.loads(split_path.read_text(encoding='utf-8'))
    theses = json.loads((root / 'data/curated/theses.json').read_text(encoding='utf-8'))
    advisors = json.loads((root / 'data/curated/advisors.json').read_text(encoding='utf-8'))
    canonical = json.dumps(theses, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest['dataset_sha256']:
        raise ValueError('dataset hash mismatch')
    if scores.shape != (len(theses), len(advisors)) or not np.isfinite(scores).all():
        raise ValueError('feature/entity shape mismatch')
    indices = splits['indices'][split]
    if not indices or len(set(indices)) != len(indices) or min(indices) < 0 or max(indices) >= len(theses):
        raise ValueError('invalid split indices')
    if [str(theses[i]['student_id']) for i in indices] != splits['student_ids'][split]:
        raise ValueError('ordered student mapping mismatch')
    ids = [str(row.get('advisor_id', i)) for i, row in enumerate(advisors)]
    # Public evidence uses an opaque mapping hash rather than student/advisor PII.
    mapping_hash = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
    subset = scores[indices]
    capacity = np.full(scores.shape[1], int(np.ceil(len(indices) / scores.shape[1])), dtype=np.int64)
    provenance = {'dataset_hash':manifest['dataset_sha256'], 'feature_hash':manifest['matrix_sha256'],
                  'split_hash':manifest['split_sha256'], 'advisor_mapping_hash':mapping_hash,
                  'capacity_policy':'uniform-ceiling-experimental-v1', 'split':split}
    return subset, capacity, provenance


def _metrics(scores, capacities, assignments, invalid=0, fallback=0):
    best = hungarian_assignment(scores, capacities)
    optimal = mean_compatibility(scores, best)
    score = mean_compatibility(scores, assignments)
    return {'mean_compatibility':score, 'load_variance':load_variance(assignments, len(capacities)),
            'quota_violations':quota_violations(assignments, capacities),
            'invalid_proposals':invalid, 'fallback_count':fallback, 'coverage':1.0,
            'optimality_ratio':score / optimal if optimal else None}


def evaluate_baselines(scores, capacities, seeds):
    rows = []
    for seed in seeds:
        methods = {'Random':random_assignment(len(scores), capacities, seed=seed),
                   'Greedy':greedy_assignment(scores, capacities),
                   'Hungarian':hungarian_assignment(scores, capacities)}
        for algorithm, assignments in methods.items():
            rows.append({'algorithm':algorithm, 'seed':seed, 'assignments':assignments.tolist(),
                         'metrics':_metrics(scores, capacities, assignments)})
    return rows


def evaluate_policy(model, scores, capacities, algorithm, seed=42):
    env = MatchingEnv(scores, capacities)
    observation, _ = env.reset(seed=seed)
    state, episode_start = None, True
    assignments, events, invalid, fallback = [], [], 0, 0
    for i in range(env.n_students):
        kwargs = {'deterministic':True}
        if algorithm == 'MaskablePPO':
            kwargs['action_masks'] = env.action_masks()
        if algorithm == 'RecurrentPPO':
            kwargs.update(state=state, episode_start=np.array([episode_start]))
        action, state = model.predict(observation, **kwargs)
        action = int(np.asarray(action).item())
        before = env.loads.copy()
        valid = 0 <= action < env.n_advisors and bool(env.action_masks()[action])
        proposed = action
        if not valid:
            invalid += 1
            fallback += 1
            feasible = np.flatnonzero(env.action_masks())
            action = int(feasible[np.argmax(scores[i, feasible])])
        observation, reward, done, _, _ = env.step(action)
        assignments.append(action)
        events.append({'step':i+1, 'student_index':i, 'advisor_index':action,
                       'proposed_action':proposed, 'invalid_proposal':not valid, 'fallback':not valid,
                       'score':float(scores[i, action]), 'reward':float(reward),
                       'loads_before':before.tolist(), 'loads_after':env.loads.tolist()})
        episode_start = False
        if done:
            break
    return {'algorithm':algorithm, 'seed':seed, 'assignments':assignments, 'events':events,
            'metrics':_metrics(scores, capacities, assignments, invalid, fallback)}


def evaluate_checkpoint(root, manifest_path, scores, capacities, provenance, *, training_provenance=None):
    from src.rl.checkpoints import verified_checkpoint
    from src.rl.cli import _algorithm_class
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    requested = manifest.get('requested_timesteps', manifest.get('timesteps', 0))
    completed = manifest.get('completed_timesteps', 0)
    if (manifest.get('status') != 'completed' or manifest.get('smoke') is not False
            or not isinstance(requested, int) or requested <= 0
            or not isinstance(completed, int) or completed < requested):
        raise ValueError('checkpoint training run is incomplete or smoke')
    checkpoint = verified_checkpoint(manifest_path, manifest)
    model = _algorithm_class(manifest['algorithm']).load(checkpoint, device='cpu')
    if int(model.num_timesteps) != completed:
        raise ValueError('checkpoint actual timestep count differs from manifest')
    if model.observation_space.shape != (3*len(capacities),) or model.action_space.n != len(capacities):
        raise ValueError('toy checkpoint incompatible with real advisor dimensions')
    if manifest.get('training_scope') != 'curated-train' or manifest.get('environment_version') != 'matching-env-v2-real':
        raise ValueError('checkpoint has no proven real training scope')
    for key in ('dataset_hash', 'feature_hash', 'split_hash'):
        if manifest.get(key) != (training_provenance or provenance)[key]:
            raise ValueError('checkpoint provenance mismatch: '+key)
    result = evaluate_policy(model, scores, capacities, manifest['algorithm'], manifest['seed'])
    result.update({'split':provenance['split'], 'training_scope':manifest['training_scope'],
                   'training_status':manifest['status'], 'smoke':manifest['smoke'],
                   'target_timesteps':requested,
                   'contract_verified':training_provenance is None, 'training_timesteps':manifest['completed_timesteps'],
                   'checkpoint':str(checkpoint.relative_to(root)).replace('\\','/'),
                   'checkpoint_hash':manifest['sha256']})
    return result
