import json

import numpy as np

from src.environment.matching_env import MatchingEnv
from src.rl.checkpoints import save_checkpoint
from src.rl.dqn import train_dqn
from src.rl.ppo import train_maskable_ppo


def _env():
    return MatchingEnv(
        np.array([[0.9, 0.2], [0.1, 0.8]], dtype=np.float32),
        np.array([1, 1]),
    )


def test_dqn_smoke_training_and_checkpoint_manifest(tmp_path):
    model = train_dqn(_env(), total_timesteps=16, seed=42)

    manifest = save_checkpoint(model, tmp_path / "dqn", algorithm="DQN", seed=42)

    assert manifest["sha256"]
    assert json.loads((tmp_path / "dqn.json").read_text())["algorithm"] == "DQN"


def test_maskable_ppo_never_predicts_exhausted_advisor_after_smoke_training():
    env = _env()
    model = train_maskable_ppo(env, total_timesteps=16, seed=42)
    observation, _ = env.reset(seed=42)
    observation, *_ = env.step(0)

    action, _ = model.predict(observation, action_masks=env.action_masks(), deterministic=True)

    assert int(action) == 1
