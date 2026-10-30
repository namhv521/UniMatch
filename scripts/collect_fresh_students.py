"""Fresh local thesis snapshot and full-document extraction; never reuse old gold."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.fresh_students import collect_students, verify_collection, rederive_temporal


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/1.pdfs'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--ocr', choices=('off', 'auto'), default='off')
    parser.add_argument('--tessdata', type=Path)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--rederive-temporal', type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify_collection(args.verify)
    else:
        if args.output is None:
            parser.error('--output is required and must be a new directory')
        result = rederive_temporal(args.rederive_temporal, args.output) if args.rederive_temporal else collect_students(args.source, args.output, ocr=args.ocr, tessdata=args.tessdata)
    print(json.dumps(result, ensure_ascii=True, indent=2))
