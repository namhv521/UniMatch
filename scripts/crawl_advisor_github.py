"""Capture the two owner-provided public accounts without changing approved gold."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.github_advisors import crawl_accounts, verify_run
from src.data_pipeline.normalization import load_taxonomy


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('data_rebuild/github_sources'))
    parser.add_argument('--owner-receipt',type=Path,required=True)
    args=parser.parse_args()
    receipt=json.loads(args.owner_receipt.read_text(encoding='utf-8-sig'))
    if not receipt:parser.error('Owner receipt required; do not invent an approval.')
    run=crawl_accounts(args.output,{'nhthang9x':'fit_992239a385b6475451e8','vietnh1009':'fit_5a04416402925947eef7'},
                       taxonomy=load_taxonomy(),owner_receipt=receipt)
    manifest=verify_run(run)
    print(json.dumps({'run_dir':str(run.resolve()),'quality':manifest['quality']},ensure_ascii=False))
    return 0 if manifest['quality']['enumeration_complete'] and manifest['quality']['source_bytes_complete'] else 2


if __name__=='__main__':raise SystemExit(main())
