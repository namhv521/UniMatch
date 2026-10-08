from __future__ import annotations

from sb3_contrib import ARS


def train_ars(env, *, total_timesteps: int, seed: int) -> ARS:
    model = ARS("LinearPolicy", env, seed=seed, n_delta=2, n_top=1, verbose=0, device="cpu")
    return model.learn(total_timesteps=total_timesteps)
