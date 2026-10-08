from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checkpoints import save_checkpoint, validate_resume_manifest, verified_checkpoint
from .training import (
    add_common_arguments,
    build_environment,
    config_from_args,
    count_invalid_proposals,
    run_manifest,
)


def run_training(algorithm: str, trainer, argv=None) -> dict:
    import torch
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    args = parser.parse_args(argv)
    config = config_from_args(algorithm, args)
    env = build_environment(config)
    prior_timesteps = 0
    if args.resume:
        resume_manifest = json.loads(Path(args.resume).read_text(encoding="utf-8"))
        validate_resume_manifest(resume_manifest, config)
        checkpoint = verified_checkpoint(args.resume, resume_manifest)
        prior_timesteps = int(resume_manifest.get("completed_timesteps", 0))
        if prior_timesteps >= config.timesteps:
            raise ValueError("resume checkpoint already meets or exceeds requested timesteps")
        model = _algorithm_class(algorithm).load(checkpoint, env=env, device="cpu")
        model.learn(total_timesteps=config.timesteps - prior_timesteps, reset_num_timesteps=False)
    else:
        model = trainer(env, total_timesteps=config.timesteps, seed=config.seed)
    invalid = count_invalid_proposals(model, env, masked=algorithm == "MaskablePPO", recurrent=algorithm == "RecurrentPPO")
    metadata = run_manifest(config, completed_timesteps=int(model.num_timesteps), status="completed")
    metadata["invalid_proposals"] = invalid
    stem = algorithm.lower().replace("-", "_")
    output = config.output_dir / (f"{stem}-resume-{config.timesteps}" if args.resume else stem)
    metadata["prior_completed_timesteps"] = prior_timesteps
    manifest = save_checkpoint(model, output, algorithm=algorithm, seed=config.seed, run_manifest=metadata)
    print(json.dumps(manifest))
    return manifest


def _algorithm_class(algorithm: str):
    from sb3_contrib import ARS, QRDQN, TRPO, MaskablePPO, RecurrentPPO
    from stable_baselines3 import DQN
    classes = {"DQN": DQN, "QRDQN": QRDQN, "MaskablePPO": MaskablePPO,
               "TRPO": TRPO, "ARS": ARS, "RecurrentPPO": RecurrentPPO}
    return classes[algorithm]
