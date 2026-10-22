"""Run fixed five-seed16k->24k->32k local validation-only continuation."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation.rl_convergence import run_convergence
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data_rebuild/v1'))
    args=parser.parse_args()
    result=run_convergence(args.output)
    print(json.dumps(result,ensure_ascii=True))
    raise SystemExit(0 if result['status']=='verified' else 2)
