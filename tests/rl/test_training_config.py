import pytest
from src.rl.training import DEFAULT_TIMESTEPS, FEATURE_MATRIX, SMOKE_TIMESTEPS, TrainingConfig, run_manifest
import hashlib
import numpy as np
from src.rl.checkpoints import validate_resume_manifest

def test_default_and_smoke_contract():
    config = TrainingConfig("DQN")
    assert config.timesteps == DEFAULT_TIMESTEPS == 2_000_000
    assert config.with_smoke().timesteps == SMOKE_TIMESTEPS
    assert config.with_smoke().smoke
    assert config.feature_hash == hashlib.sha256(np.load(FEATURE_MATRIX, allow_pickle=False).tobytes()).hexdigest()

def test_resume_rejects_mismatch_and_smoke():
    config = TrainingConfig("DQN")
    manifest = run_manifest(config, completed_timesteps=config.timesteps, status="completed")
    validate_resume_manifest(manifest, config)
    with pytest.raises(ValueError, match="algorithm"):
        validate_resume_manifest(manifest, TrainingConfig("QRDQN"))
    with pytest.raises(ValueError, match="completion_state"):
        validate_resume_manifest(run_manifest(config.with_smoke(), status="completed"), config)
