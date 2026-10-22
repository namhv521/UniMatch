"""Run Phase 1 only after the accepted Phase 0 source inventory."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.source_rebuild import rebuild


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/1.pdfs'))
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--ocr', choices=['auto', 'off'], default='auto')
    args = parser.parse_args()
    result = rebuild(args.source, args.output, ocr_mode=args.ocr)
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result['status'] == 'verified' else 2)
