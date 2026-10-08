from __future__ import annotations

from sb3_contrib import QRDQN


def train_qrdqn(env, *, total_timesteps: int, seed: int) -> QRDQN:
    model = QRDQN(
        "MlpPolicy", env, seed=seed, learning_starts=0, buffer_size=64,
        batch_size=8, train_freq=1, gradient_steps=1,
        policy_kwargs={"net_arch": [16], "n_quantiles": 8}, verbose=0, device="cpu",
    )
    return model.learn(total_timesteps=total_timesteps)
