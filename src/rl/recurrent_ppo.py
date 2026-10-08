from __future__ import annotations

from sb3_contrib import RecurrentPPO


def train_recurrent_ppo(env, *, total_timesteps: int, seed: int) -> RecurrentPPO:
    model = RecurrentPPO("MlpLstmPolicy", env, seed=seed, n_steps=4, batch_size=2,
                         n_epochs=1, policy_kwargs={"net_arch": [16], "lstm_hidden_size": 16},
                         verbose=0, device="cpu")
    return model.learn(total_timesteps=total_timesteps)


def predict_episode(model, env) -> list[int]:
    observation, _ = env.reset()
    state, episode_start, actions = None, True, []
    done = False
    while not done:
        action, state = model.predict(observation, state=state,
                                      episode_start=[episode_start], deterministic=True)
        observation, _, terminated, truncated, _ = env.step(int(action))
        actions.append(int(action))
        done = terminated or truncated
        episode_start = done
    return actions
