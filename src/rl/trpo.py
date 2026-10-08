from __future__ import annotations

from sb3_contrib import TRPO


def train_trpo(env, *, total_timesteps: int, seed: int) -> TRPO:
    model = TRPO("MlpPolicy", env, seed=seed, n_steps=4, batch_size=2,
                 policy_kwargs={"net_arch": [16]}, verbose=0, device="cpu")
    return model.learn(total_timesteps=total_timesteps)
