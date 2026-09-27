"""Single mask API used by training and inference."""


def action_mask(env):
    return env.action_masks()
