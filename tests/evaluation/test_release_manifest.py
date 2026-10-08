import importlib.util
import json
import sys
from pathlib import Path

import pytest


def test_release_fingerprints_actual_code_data_and_models(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / 'scripts/verify_release.py'
    spec = importlib.util.spec_from_file_location('verify_release', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tracked = ['scripts/run_benchmark.py', 'requirements.txt', 'Dockerfile',
               'data/features/compatibility_matrix_v2.npy', 'data/curated/split_indices.json',
               'outputs/research-real/model.zip', 'outputs/research-real/model.json']
    for name in tracked:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
    output = tmp_path/'release.json'
    (tmp_path/'frontend/dist').mkdir(parents=True)
    (tmp_path/'frontend/app.js').write_bytes(b'fixture')
    (tmp_path/'frontend/dist/app.js').write_bytes(b'fixture')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['verify_release', '--output', str(output)])
    module.main()
    first = json.loads(output.read_text())
    assert all(name in first['source_hashes'] or name in first['evidence_hashes'] for name in tracked)
    (tmp_path/'outputs/research-real/model.zip').write_bytes(b'changed')
    module.main()
    second = json.loads(output.read_text())
    assert first['evidence_bundle_sha256'] != second['evidence_bundle_sha256']
    assert second['production_ready'] is False
    assert second['runtime_asset_hashes']['app.js']
    (tmp_path/'frontend/dist/app.js').write_bytes(b'stale')
    with pytest.raises(ValueError, match='stale frontend bundle'):
        module.main()
