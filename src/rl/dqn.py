from __future__ import annotations

from stable_baselines3 import DQN


def train_dqn(env, *, total_timesteps: int, seed: int) -> DQN:
    model = DQN(
        "MlpPolicy",
        env,
        seed=seed,
        learning_starts=0,
        buffer_size=64,
        batch_size=8,
        train_freq=1,
        gradient_steps=1,
        policy_kwargs={"net_arch": [16]},
        verbose=0,
        device="cpu",
    )
    model.learn(total_timesteps=total_timesteps)
    return model
