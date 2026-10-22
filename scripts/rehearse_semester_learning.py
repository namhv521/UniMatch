"""Run offline P6 continuation/rollback rehearsal. Partial gate exits 2."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.semester_rehearsal import run_rehearsal

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data_rebuild/v1'))
    parser.add_argument('--timesteps',type=int,default=1024)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    gate=run_rehearsal(args.output,timesteps=args.timesteps,seed=args.seed)
    print(json.dumps(gate,ensure_ascii=True))
    raise SystemExit(0 if gate['status']=='verified' else 2)
