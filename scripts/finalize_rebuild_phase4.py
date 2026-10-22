"""Finalize Phase 4 from a receipt of explicit owner approval."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.features.rebuild_acceptance import finalize_features


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('data_rebuild/v1'))
    parser.add_argument('--authority',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(finalize_features(args.output,args.authority),ensure_ascii=True))
