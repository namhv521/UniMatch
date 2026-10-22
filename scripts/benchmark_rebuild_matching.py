"""Offline source-bound Phase 5 CPU worker; never invoked by the web handler."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.rebuild_benchmark import run_benchmark


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data_rebuild/v1'))
    parser.add_argument('--timesteps',type=int,default=16384)
    parser.add_argument('--seeds',type=int,nargs='+',default=[42,43,44,45,46])
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    gate=run_benchmark(args.output,total_timesteps=args.timesteps,seeds=tuple(args.seeds),smoke=args.smoke)
    print(json.dumps(gate,ensure_ascii=True))
    raise SystemExit(0 if gate['status']=='verified' else 2)
