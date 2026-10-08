import json
from pathlib import Path

import numpy as np
import pytest

from scripts.train_real_rl import preflight, select_resume, verify_target
from src.rl.training import TrainingConfig
from src.serving.model_registry import ModelRegistry

ROOT = Path(__file__).parents[2]


def test_preflight_uses_every_train_student_and_advisor():
    result = preflight(ROOT)
    split = json.loads((ROOT / 'data/curated/split_indices.json').read_text())
    matrix = np.load(ROOT / 'data/features/compatibility_matrix_v2.npy', allow_pickle=False)
    assert result['students'] == len(split['indices']['train'])
    assert result['advisors'] == matrix.shape[1]
    assert result['observation_shape'] == [3 * matrix.shape[1]]
    assert result['smoke'] is False


def test_resume_skips_old_snapshot_instead_of_loading_it(tmp_path):
    config = TrainingConfig('DQN', timesteps=100)
    candidate = tmp_path / 'dqn-seed42-steps16.json'
    candidate.write_text(json.dumps({**config.contract(), 'dataset_hash': 'old',
                                    'completed_timesteps': 16, 'smoke': False, 'status': 'completed'}))
    resume, rejected = select_resume(tmp_path, config)
    assert resume is None
    assert len(rejected) == 1
    assert 'dataset_hash' in rejected[0]['reason']


def test_registry_scans_current_research_and_does_not_promote(tmp_path):
    target = tmp_path / 'outputs/research-current'
    target.mkdir(parents=True)
    (target / 'broken.json').write_text('{}')
    [record] = ModelRegistry(tmp_path).catalog()
    assert record['research'] is True
    assert record['status'] == 'invalid'
    assert record['promoted'] is False


def test_exact_target_rejects_fake_completed_steps(tmp_path):
    import shutil
    source = ROOT / 'outputs/research-current/dqn-seed42-steps256-07e16374f68e.json'
    metadata = json.loads(source.read_text())
    shutil.copy2(source.parent / metadata['checkpoint'], tmp_path / metadata['checkpoint'])
    metadata['completed_timesteps'] = 2_000_000
    target = tmp_path / source.name
    target.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='steps'):
        verify_target(target, TrainingConfig('DQN', timesteps=256), preflight()['advisors'])
