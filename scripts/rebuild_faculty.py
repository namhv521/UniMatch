"""Crawl observed official faculty links after the accepted Phase 1 gate."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.lecturer_crawl import crawl_faculty


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--directory-capture', type=Path,
                        default=Path('data_rebuild/v1/raw_index/faculty_directory_capture.json'))
    args = parser.parse_args()
    result = crawl_faculty(args.output, args.directory_capture)
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result['status'] == 'verified' else 2)
