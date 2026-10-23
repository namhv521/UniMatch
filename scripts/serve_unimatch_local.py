"""Launch the additive local UniMatch API/page; never prints access tokens."""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def load_local_token(path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        # Exclusive creation prevents a second launcher from replacing a token.
        try:
            with path.open('x',encoding='utf-8') as stream:
                stream.write(secrets.token_urlsafe(32))
            path.chmod(0o600)
        except FileExistsError:
            pass
    token=path.read_text(encoding='utf-8').strip()
    if len(token)<32 or any(c.isspace() for c in token):
        raise ValueError('local_access_token_invalid; inspect the token file before replacing it')
    return token


def local_selection_path(output):
    """Choose the local selection pointer; the serving loader verifies its bytes."""
    output=Path(output).resolve();pointer=output/'reports/convergence_gate.json'
    if not pointer.exists(): return None
    gate=json.loads(pointer.read_text(encoding='utf-8'))
    if gate.get('status')!='verified': return None
    directory=Path(gate['run_dir']).resolve()
    if directory.parent!=output/'convergence_runs' or directory.name!=gate['run_id']:
        raise ValueError('local_convergence_selection_path_invalid')
    return directory/'selection_manifest.json'


def local_app_entrypoint(output):
    gate_path=Path(output)/'reports/phase8_local_gate.json'
    if gate_path.exists():
        gate=json.loads(gate_path.read_text(encoding='utf-8'))
        if (gate.get('phase')==8 and gate.get('status')=='verified'
                and gate.get('scope')=='owner_authorized_local_release'):
            return 'backend.app.rebuild_assistant_api:app'
    return 'backend.app.rebuild_api:app'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--token-file',type=Path,default=ROOT/'data_rebuild/runtime/access.token')
    parser.add_argument('--selection',type=Path,help='Explicit verified model-selection manifest')
    args=parser.parse_args()
    os.environ['UNIMATCH_REBUILD_TOKEN']=load_local_token(args.token_file)
    selection=args.selection or local_selection_path(ROOT/'data_rebuild/v1')
    if selection is not None:
        os.environ['UNIMATCH_REBUILD_SELECTION']=str(selection.resolve())
    os.environ.setdefault('OMP_NUM_THREADS','1')
    os.environ.setdefault('MKL_NUM_THREADS','1')
    os.environ.setdefault('UNIMATCH_PUBLIC_ORIGIN',f'http://127.0.0.1:{args.port}')
    print(f'Local workspace: http://127.0.0.1:{args.port}/login.html',flush=True)
    print(f'Access token file: {args.token_file.resolve()} (private; value not logged)',flush=True)
    import uvicorn
    uvicorn.run(local_app_entrypoint(ROOT/'data_rebuild/v1'),host='127.0.0.1',port=args.port,access_log=False)
