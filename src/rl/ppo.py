from __future__ import annotations

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker


def train_maskable_ppo(env, *, total_timesteps: int, seed: int) -> MaskablePPO:
    masked_env = ActionMasker(env, lambda wrapped: wrapped.unwrapped.action_masks())
    model = MaskablePPO(
        "MlpPolicy",
        masked_env,
        seed=seed,
        n_steps=8,
        batch_size=4,
        n_epochs=1,
        policy_kwargs={"net_arch": [16]},
        verbose=0,
        device="cpu",
    )
    model.learn(total_timesteps=total_timesteps)
    return model
