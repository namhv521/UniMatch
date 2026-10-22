"""CPU masked Double DQN for versioned, train-only allocation environments."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return int(value)


def _number(value, name, lower=0., upper=None, exclusive_lower=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f'invalid {name}')
    value = float(value)
    if not np.isfinite(value) or value < lower or (exclusive_lower and value == lower) or (upper is not None and value > upper):
        raise ValueError(f'invalid {name}')
    return value


def _mask(value, shape):
    result = np.asarray(value)
    if result.dtype != np.bool_ or result.shape != shape:
        raise ValueError(f'mask must be boolean with shape {shape}')
    return result


def _observation(value, dim):
    result = np.asarray(value, dtype=np.float32)
    if result.shape != (dim,) or not np.isfinite(result).all():
        raise ValueError('observation shape or values invalid')
    return result


def masked_double_dqn_targets(rewards, terminated, next_online_q, next_target_q, next_masks, gamma):
    """Online masked argmax; target-network evaluation. Truncation is not termination."""
    gamma = _number(gamma, 'gamma', upper=1.)
    online = np.asarray(next_online_q, dtype=np.float32)
    target = np.asarray(next_target_q, dtype=np.float32)
    reward = np.asarray(rewards, dtype=np.float32)
    done = np.asarray(terminated)
    if online.ndim != 2 or online.shape[1] == 0 or target.shape != online.shape:
        raise ValueError('Q arrays must have equal [batch, action] shape')
    n = online.shape[0]
    masks = _mask(next_masks, online.shape)
    if done.dtype != np.bool_ or done.shape != (n,) or reward.shape != (n,):
        raise ValueError('reward/termination shape or dtype invalid')
    if not all(np.isfinite(a).all() for a in (online, target, reward)):
        raise ValueError('nonfinite Q or reward')
    if np.any(~done & ~masks.any(axis=1)):
        raise ValueError('nonterminal next state has no valid action')
    best = np.where(masks, online, -np.inf).argmax(axis=1)
    bootstrap = target[np.arange(n), best]
    return reward + gamma * np.where(done, 0., bootstrap)


class ReplayBuffer:
    """Bounded copied transitions, including exact next-action masks."""
    def __init__(self, capacity, observation_dim, action_count, seed=42):
        self.capacity = _integer(capacity, 'capacity')
        self.observation_dim = _integer(observation_dim, 'observation_dim')
        self.action_count = _integer(action_count, 'action_count')
        self.rng = np.random.default_rng(seed)
        self.position = self.size = 0
        self.data = {
            'observations': np.zeros((capacity, observation_dim), np.float32),
            'actions': np.zeros(capacity, np.int64),
            'rewards': np.zeros(capacity, np.float32),
            'next_observations': np.zeros((capacity, observation_dim), np.float32),
            'terminated': np.zeros(capacity, bool),
            'truncated': np.zeros(capacity, bool),
            'next_masks': np.zeros((capacity, action_count), bool),
        }

    def __len__(self):
        return self.size

    def add(self, observation, action, reward, next_observation, terminated, next_mask, *, truncated=False, current_mask=None):
        observation = _observation(observation, self.observation_dim)
        next_observation = _observation(next_observation, self.observation_dim)
        action = _integer(action, 'action', 0)
        reward = _number(reward, 'reward', lower=-float('inf'))
        if abs(reward) > float(np.finfo(np.float32).max):
            raise ValueError('reward outside replay float32 range')
        if action >= self.action_count or not isinstance(terminated, (bool, np.bool_)) or not isinstance(truncated, (bool, np.bool_)):
            raise ValueError('invalid action or terminal flags')
        mask = _mask(next_mask, (self.action_count,))
        if not terminated and not mask.any():
            raise ValueError('nonterminal next state has no valid action')
        if current_mask is not None and not _mask(current_mask, (self.action_count,))[action]:
            raise ValueError('replay action forbidden by current mask')
        values = dict(observations=observation, actions=action, rewards=reward,
                      next_observations=next_observation, terminated=terminated,
                      truncated=truncated, next_masks=mask)
        for key, value in values.items():
            self.data[key][self.position] = value
        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def sample(self, batch_size):
        batch_size = _integer(batch_size, 'batch_size')
        if batch_size > self.size:
            raise ValueError('insufficient replay rows')
        indices = self.rng.choice(self.size, size=batch_size, replace=False)
        return {key: value[indices].copy() for key, value in self.data.items()}


class MaskedDQN:
    def __init__(self, observation_dim, action_count, *, seed=42, learning_rate=1e-3,
                 gamma=.99, hidden_sizes=(128, 128), buffer_size=10000, batch_size=64,
                 learning_starts=128, target_update_interval=200, train_frequency=4, contract=None):
        self.observation_dim = _integer(observation_dim, 'observation_dim')
        self.action_count = _integer(action_count, 'action_count')
        self.seed = _integer(seed, 'seed', 0)
        self.learning_rate = _number(learning_rate, 'learning_rate', exclusive_lower=True)
        self.gamma = _number(gamma, 'gamma', upper=1.)
        self.hidden_sizes = tuple(_integer(n, 'hidden size') for n in hidden_sizes)
        self.batch_size = _integer(batch_size, 'batch_size')
        self.learning_starts = _integer(learning_starts, 'learning_starts', 0)
        self.target_update_interval = _integer(target_update_interval, 'target_update_interval')
        self.train_frequency = _integer(train_frequency, 'train_frequency')
        self.contract = json.loads(_json({} if contract is None else contract))
        if not isinstance(self.contract, dict):
            raise ValueError('contract must be a JSON object')
        self.contract_sha256 = hashlib.sha256(_json(self.contract).encode()).hexdigest()
        self.rng = np.random.default_rng(self.seed)
        # Isolate initialization from other models and the process-global RNG.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.seed)
            layers = []
            previous = self.observation_dim
            for width in self.hidden_sizes:
                layers.extend([nn.Linear(previous, width), nn.ReLU()])
                previous = width
            layers.append(nn.Linear(previous, self.action_count))
            self.online = nn.Sequential(*layers).cpu()
        self.target = copy.deepcopy(self.online).eval()
        self.target.requires_grad_(False)
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=self.learning_rate)
        self.replay = ReplayBuffer(buffer_size, observation_dim, action_count, seed=self.seed + 1)
        if self.batch_size > self.replay.capacity:
            raise ValueError('batch_size exceeds buffer capacity')
        self.total_timesteps = self.gradient_updates = self.total_episodes = 0
        self.training_provenance = []

    def q_values(self, observation):
        obs = _observation(observation, self.observation_dim)
        with torch.no_grad():
            result = self.online(torch.from_numpy(obs.copy())).numpy().copy()
        if not np.isfinite(result).all():
            raise ValueError('nonfinite learned Q values')
        return result

    def predict(self, observation, action_masks, deterministic=True, epsilon=0.0):
        masks = _mask(action_masks, (self.action_count,))
        epsilon = _number(epsilon, 'epsilon', upper=1.)
        if not isinstance(deterministic, (bool, np.bool_)) or not masks.any():
            raise ValueError('invalid deterministic flag or no valid action')
        q = self.q_values(observation)
        if not deterministic and self.rng.random() < epsilon:
            return int(self.rng.choice(np.flatnonzero(masks)))
        return int(np.where(masks, q, -np.inf).argmax())

    def _update(self):
        b = self.replay.sample(self.batch_size)
        nxt = torch.from_numpy(b['next_observations'])
        with torch.no_grad():
            targets = masked_double_dqn_targets(b['rewards'], b['terminated'],
                self.online(nxt).numpy(), self.target(nxt).numpy(), b['next_masks'], self.gamma)
        chosen = self.online(torch.from_numpy(b['observations'])).gather(
            1, torch.from_numpy(b['actions'])[:, None]).squeeze(1)
        loss = nn.functional.smooth_l1_loss(chosen, torch.from_numpy(targets))
        if not torch.isfinite(loss):
            raise ValueError('nonfinite training loss')
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10., error_if_nonfinite=True)
        self.optimizer.step()
        self.gradient_updates += 1
        return float(loss.detach())

    def learn(self, env, total_timesteps, *, epsilon_start=1., epsilon_end=.05):
        steps = _integer(total_timesteps, 'total_timesteps')
        start = _number(epsilon_start, 'epsilon_start', upper=1.)
        end = _number(epsilon_end, 'epsilon_end', upper=1.)
        provenance = copy.deepcopy(getattr(env, 'training_provenance', None))
        if not isinstance(provenance, list) or not provenance:
            raise ValueError('training provenance required')
        allowed, cohorts = set(), {}
        for index, cohort in enumerate(provenance):
            if cohort.get('metadata', {}).get('split') != 'train' or not cohort.get('student_ids'):
                raise ValueError('all replay source cohorts must be train-only')
            for key in ('feature_contract_sha256', 'taxonomy_feature_order_sha256'):
                if key in self.contract and (not isinstance(cohort['metadata'].get(key), str)
                        or cohort['metadata'][key] != self.contract[key]):
                    raise ValueError(f'training cohort feature contract {key} mismatch or missing')
            if len(set(cohort['student_ids'])) != len(cohort['student_ids']):
                raise ValueError('duplicate training rows in cohort')
            allowed.update(cohort['student_ids'])
            cohort_index = cohort.get('problem_index', index)
            if cohort_index in cohorts:
                raise ValueError('duplicate provenance problem index')
            cohorts[cohort_index] = cohort
        if (hasattr(env, 'observation_space') and env.observation_space.shape != (self.observation_dim,)) or (hasattr(env, 'action_space') and env.action_space.n != self.action_count):
            raise ValueError('environment observation/action dimension mismatch')
        expected = self.contract.get('state_contract')
        if expected is not None and _json(expected) != _json(getattr(env, 'state_contract', None)):
            raise ValueError('environment contract mismatch')
        losses, loss_steps, episodes, seen, encountered = [], [], 0, set(), set()
        def reset():
            obs, info = env.reset(seed=int(self.rng.integers(0, 2**31 - 1)))
            cohort_index = info.get('problem_index', next(iter(cohorts)) if len(cohorts) == 1 else None)
            if cohort_index not in cohorts:
                raise ValueError('reset missing or invalid problem index')
            cohort = cohorts[cohort_index]
            ids = info.get('student_ids')
            if ids is None and len(provenance) == 1:
                ids = cohort['student_ids']
            if not ids or len(ids) != len(cohort['student_ids']) or set(ids) != set(cohort['student_ids']):
                raise ValueError('reset rows mismatch selected training cohort')
            if 'metadata' in info and _json(info['metadata']) != _json(cohort['metadata']):
                raise ValueError('reset source metadata mismatch')
            order = info.get('student_order', ids)
            if len(order) != len(ids) or set(order) != set(ids):
                raise ValueError('invalid reset student order')
            if cohort not in self.training_provenance:
                self.training_provenance.append(copy.deepcopy(cohort))
            return obs, list(order), cohort_index
        observation, ids, cohort_index = reset()
        position = 0
        for local_step in range(steps):
            if position >= len(ids):
                raise ValueError('episode exceeds declared training rows')
            epsilon = start + (end - start) * local_step / max(steps - 1, 1)
            mask = _mask(env.action_masks(), (self.action_count,)).copy()
            action = self.predict(observation, mask, deterministic=False, epsilon=epsilon)
            next_obs, reward, terminated, truncated, _ = env.step(action)
            next_mask = _mask(env.action_masks(), (self.action_count,)).copy()
            self.replay.add(observation, action, reward, next_obs, terminated, next_mask,
                            truncated=truncated, current_mask=mask)
            seen.add(ids[position]); encountered.add(cohort_index); position += 1
            self.total_timesteps += 1
            if len(self.replay) >= self.batch_size and self.total_timesteps >= self.learning_starts and self.total_timesteps % self.train_frequency == 0:
                losses.append(self._update()); loss_steps.append(self.total_timesteps)
            if self.total_timesteps % self.target_update_interval == 0:
                self.target.load_state_dict(self.online.state_dict())
            observation = next_obs
            if terminated or truncated:
                episodes += 1; self.total_episodes += 1
                if local_step + 1 < steps:
                    observation, ids, cohort_index = reset(); position = 0
        return dict(actual_timesteps=steps, total_timesteps=self.total_timesteps, episodes=episodes,
                    gradient_updates=len(losses), losses=losses, loss_steps=loss_steps,
                    training_unique_student_count=len(seen), training_available_student_count=len(allowed),
                    training_encountered_student_ids=sorted(seen), training_transition_count=steps,
                    training_encountered_cohort_count=len(encountered), training_provenance=provenance,
                    training_provenance_sha256=hashlib.sha256(_json(provenance).encode()).hexdigest(),
                    contract_sha256=self.contract_sha256, epsilon_start=start, epsilon_end=end)

    def save(self, directory):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
        torch.save(dict(online=self.online.state_dict(), target=self.target.state_dict(),
                        optimizer=self.optimizer.state_dict()), directory / 'weights.pt')
        np.savez_compressed(directory / 'replay.npz', **{k: v[:len(self.replay)] for k,v in self.replay.data.items()})
        metadata = dict(format_version=1, algorithm='masked_double_dqn',
            observation_dim=self.observation_dim, action_count=self.action_count,
            seed=self.seed, learning_rate=self.learning_rate, gamma=self.gamma,
            hidden_sizes=self.hidden_sizes, buffer_size=self.replay.capacity, batch_size=self.batch_size,
            learning_starts=self.learning_starts, target_update_interval=self.target_update_interval,
            train_frequency=self.train_frequency, contract=self.contract, contract_sha256=self.contract_sha256,
            total_timesteps=self.total_timesteps, gradient_updates=self.gradient_updates,
            total_episodes=self.total_episodes, replay_size=len(self.replay), replay_position=self.replay.position,
            rng_state=self.rng.bit_generator.state, replay_rng_state=self.replay.rng.bit_generator.state,
            torch_version=str(torch.__version__), replay_contract_sha256=self.contract_sha256)
        metadata['training_provenance'] = self.training_provenance
        (directory / 'metadata.json').write_text(_json(metadata), encoding='utf-8')
        manifest = {name:_hash(directory/name) for name in ('weights.pt','replay.npz','metadata.json')}
        (directory / 'checksums.json').write_text(_json(manifest), encoding='utf-8')
        return metadata

    @classmethod
    def load(cls, directory, expected_contract=None):
        directory = Path(directory)
        checksums = json.loads((directory/'checksums.json').read_text(encoding='utf-8'))
        if set(checksums) != {'weights.pt','replay.npz','metadata.json'}:
            raise ValueError('checkpoint checksum manifest invalid')
        if any(_hash(directory/name) != value for name,value in checksums.items()):
            raise ValueError('checkpoint checksum mismatch')
        m = json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        if m.get('format_version') != 1 or m.get('algorithm') != 'masked_double_dqn':
            raise ValueError('unsupported checkpoint format')
        contract_hash = hashlib.sha256(_json(m['contract']).encode()).hexdigest()
        if m['contract_sha256'] != contract_hash or m['replay_contract_sha256'] != contract_hash:
            raise ValueError('replay/checkpoint contract hash mismatch')
        if expected_contract is not None and _json(expected_contract) != _json(m['contract']):
            raise ValueError('checkpoint incompatible with expected contract')
        keys = ('seed','learning_rate','gamma','hidden_sizes','buffer_size','batch_size','learning_starts','target_update_interval','train_frequency','contract')
        model = cls(m['observation_dim'], m['action_count'], **{k:m[k] for k in keys})
        if not isinstance(m.get('training_provenance'), list) or any(c.get('metadata', {}).get('split') != 'train' or not c.get('student_ids') for c in m['training_provenance']):
            raise ValueError('checkpoint training provenance invalid')
        for key in ('feature_contract_sha256', 'taxonomy_feature_order_sha256'):
            if key in model.contract and any(not isinstance(c['metadata'].get(key), str)
                    or c['metadata'][key] != model.contract[key] for c in m['training_provenance']):
                raise ValueError(f'replay provenance feature contract {key} mismatch or missing')
        model.training_provenance = m['training_provenance']
        weights = torch.load(directory/'weights.pt', map_location='cpu', weights_only=True)
        model.online.load_state_dict(weights['online'], strict=True)
        model.target.load_state_dict(weights['target'], strict=True)
        model.optimizer.load_state_dict(weights['optimizer'])
        if any(not torch.isfinite(p).all() for net in (model.online, model.target) for p in net.parameters()):
            raise ValueError('nonfinite checkpoint weights')
        size = _integer(m['replay_size'], 'replay_size', 0)
        position = _integer(m['replay_position'], 'replay_position', 0)
        if size > model.replay.capacity or position >= model.replay.capacity or (size < model.replay.capacity and position != size):
            raise ValueError('invalid replay cursor')
        with np.load(directory/'replay.npz', allow_pickle=False) as archive:
            if set(archive.files) != set(model.replay.data):
                raise ValueError('invalid replay arrays')
            for key, dest in model.replay.data.items():
                value = archive[key]
                if value.shape != (size, *dest.shape[1:]) or value.dtype != dest.dtype or not np.isfinite(value).all():
                    raise ValueError(f'invalid replay {key}')
                dest[:size] = value
        replay = model.replay; replay.size = size; replay.position = position
        if np.any((replay.data['actions'][:size] < 0) | (replay.data['actions'][:size] >= model.action_count)) or np.any(~replay.data['terminated'][:size] & ~replay.data['next_masks'][:size].any(axis=1)):
            raise ValueError('invalid stored transitions')
        for key in ('total_timesteps','gradient_updates','total_episodes'):
            setattr(model, key, _integer(m[key], key, 0))
        model.rng.bit_generator.state = m['rng_state']
        model.replay.rng.bit_generator.state = m['replay_rng_state']
        return model
