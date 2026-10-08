"""Record source/data/model hashes and explicit missing release evidence."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/final_validation/release-manifest.json')
    args = parser.parse_args()
    files = {}
    for folder in ('src','backend','frontend','scripts','.github'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.js','.css','.html','.json','.yml','.yaml') and 'dist' not in path.parts:
                files[str(path.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('requirements.txt','Dockerfile','docker-compose.yml','.dockerignore','run_dashboard.py'):
        path = ROOT/name
        if path.is_file():
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    evidence = {}
    runtime_assets = {}
    for path in sorted((ROOT/'frontend/dist').glob('*')):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            original = ROOT/'frontend'/path.name
            if original.is_file() and hashlib.sha256(original.read_bytes()).hexdigest() != digest:
                raise ValueError('stale frontend bundle: '+path.name)
            runtime_assets[path.name] = digest
    for name in ('data/features/feature_manifest_v2.json','outputs/benchmarks/validation-2026-10-07.json'):
        path = ROOT/name
        evidence[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    for folder in ('data/curated','data/features','outputs/checkpoints','outputs/research-real'):
        for path in sorted((ROOT/folder).rglob('*')):
            if path.is_file() and path.suffix in ('.json','.npy','.zip'):
                evidence[str(path.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    benchmark_path=ROOT/'outputs/benchmarks/validation-2026-10-07.json'
    report=json.loads(benchmark_path.read_text()) if benchmark_path.exists() else {}
    promoted=[name for name,gate in report.get('promotion',{}).items() if gate.get('promoted')]
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'source_hashes':files,
              'source_bundle_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
              'evidence_hashes':evidence,'promoted_models':promoted,
              'runtime_asset_hashes':runtime_assets,
              'evidence_bundle_sha256':hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest(),
              'production_ready':False,'academic_final_validation_complete':False,
              'limitations':['official advisor quota unavailable','external deployment not verified',
                             'manual thesis review and institution submission not performed'],
              'selected_engine':report.get('selected_engine','Hungarian')}
    if not promoted:
        manifest['limitations'].append('no full-budget multi-seed real-data RL candidate passed promotion')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'source_files':len(files),'production_ready':False}))


if __name__=='__main__':
    main()
