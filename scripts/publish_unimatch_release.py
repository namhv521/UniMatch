"""Export a verified private release; optionally publish immutably to PostgreSQL."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'data_rebuild/deployment/serving.tar.gz')
    parser.add_argument('--publish-key', help='Publish under a new immutable key using DATABASE_URL')
    args = parser.parse_args()
    from backend.app.production_release import export_release, publish_release
    result = export_release(args.bundle, args.selection, args.output)
    if args.publish_key:
        from backend.app.portal_database import Database, database_location
        location = database_location()
        if not location.startswith(('postgres://', 'postgresql://')):
            raise ValueError('postgresql_required_for_publish')
        result['published_sha256'] = publish_release(Database(location), args.publish_key, args.output)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
