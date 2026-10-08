"""Fail if the current Git index still includes private data, secrets or caches."""
import json
import subprocess
from pathlib import Path


def private_tracked_files(root: Path) -> list[str]:
    root = root.resolve()
    result = subprocess.run(['git', '-c', f'safe.directory={root.as_posix()}', '-C', str(root),
                             'ls-files', '-z'], capture_output=True, check=True)
    private = []
    for name in result.stdout.decode('utf-8').split('\0'):
        if not name:
            continue
        path = Path(name)
        secret = (path.name == '.env' or path.name.startswith('.env.')) and path.name != '.env.example'
        if (path.parts[0] in {'data', 'outputs', 'backups'} or secret or '__pycache__' in path.parts
                or path.suffix.lower() in {'.pyc', '.pem', '.key', '.p12', '.dump'}):
            private.append(name)
    return sorted(private)


def main():
    private = private_tracked_files(Path(__file__).resolve().parents[1])
    print(json.dumps({'publish_index_safe': not private, 'private_tracked_files': private}))
    raise SystemExit(1 if private else 0)


if __name__ == '__main__':
    main()
