# RL training commands

All compatible scripts default to `2_000_000` timesteps. Use `--smoke` for wiring checks; smoke artifacts are not promotion evidence.

```powershell
python scripts/smoke_all_algorithms.py
python scripts/train_dqn.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_qrdqn.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_maskable_ppo.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_trpo.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_ars.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_recurrent_ppo.py --timesteps 2000000 --output-dir outputs/checkpoints
python scripts/train_dqn.py --resume outputs/checkpoints/dqn.json
Get-ChildItem outputs/checkpoints/*.json | Get-Content
```

`train_tqc.py` intentionally exits with code 2 because the current environment uses discrete actions and TQC requires continuous actions. Capacity values remain an experimental uniform-ceiling assumption until authoritative quotas exist.
