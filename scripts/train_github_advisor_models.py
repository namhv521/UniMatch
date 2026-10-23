"""Validate a frozen local bundle, or explicitly execute the isolated experiment."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.evaluation.github_retraining import run_retraining, validate_bundle, load_bundle, PLAN


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-workers',type=int,choices=(1,2),default=2)
    parser.add_argument('--execute',action='store_true',help='Start actual from-scratch training; default only validates.')
    args=parser.parse_args()
    if args.execute:
        result=run_retraining(args.bundle,args.output,max_workers=args.max_workers)
    else:
        suite=validate_bundle(load_bundle(args.bundle))
        result={'status':'bundle_validated_no_training','train':sum(len(p.student_ids) for p in suite['train']),
                'validation':len(suite['validation'].student_ids),'reserved_test':len(suite['test'].student_ids),'plan':PLAN}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.execute and result['status']!='verified':raise SystemExit(2)


if __name__=='__main__':main()
