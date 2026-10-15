"""Upload an immutable inference bundle to the deployment database."""
import argparse
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.artifacts import ALLOWED_ROOTS, artifact_target


def main():
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    rows = []
    for directory in sorted(ALLOWED_ROOTS):
        for path in sorted((args.source / directory).glob("*")):
            if path.suffix not in {".json", ".npy", ".zip"} or not path.is_file():
                continue
            relative = path.relative_to(args.source).as_posix()
            artifact_target(args.source, relative)
            content = path.read_bytes()
            rows.append((args.bundle, relative, hashlib.sha256(content).hexdigest(), content))
    if not rows:
        raise RuntimeError("No serving files found")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=30) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS serving_artifacts (
            bundle text NOT NULL, path text NOT NULL, sha256 char(64) NOT NULL,
            payload bytea NOT NULL, PRIMARY KEY(bundle, path))""")
        if connection.execute("SELECT count(*) FROM serving_artifacts WHERE bundle=%s", (args.bundle,)).fetchone()[0]:
            raise RuntimeError("Bundle already exists; choose a new version")
        with connection.cursor() as cursor:
            cursor.executemany("INSERT INTO serving_artifacts(bundle,path,sha256,payload) VALUES (%s,%s,%s,%s)", rows)
    print(f"Uploaded {len(rows)} files ({sum(len(row[3]) for row in rows)} bytes); bundle {args.bundle}")


if __name__ == "__main__":
    main()
