"""Launch an explicitly verified GitHub-enriched bundle on loopback."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.serve_unimatch_local import load_local_token


def make_app(**kwargs):
    from backend.app.github_rebuild_api import create_app
    return create_app(**kwargs)


def private_path(path):
    resolved = Path(path).resolve()
    roots = (ROOT.resolve()/'data_rebuild/runtime', ROOT.resolve()/'data_rebuild/v1/runtime')
    if not any(resolved.is_relative_to(root) for root in roots):
        raise ValueError('private_local_path_required')
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, default=ROOT/'data_rebuild/runtime/github')
    parser.add_argument('--token-file', type=Path, default=ROOT/'data_rebuild/runtime/access.token')
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args(argv)
    runtime = private_path(args.runtime)
    token_path = private_path(args.token_file)
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
    os.environ.setdefault('UNIMATCH_PUBLIC_ORIGIN', f'http://127.0.0.1:{args.port}')
    app = make_app(bundle_path=args.bundle.resolve(), selection_path=args.selection.resolve(),
                   runtime_dir=runtime, token=load_local_token(token_path), frontend_dir=ROOT/'frontend/dist')
    print(f'Local workspace: http://127.0.0.1:{args.port}/login.html', flush=True)
    print(f'Access token file: {token_path} (private; value not logged)', flush=True)
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
