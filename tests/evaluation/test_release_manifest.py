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
               'outputs/research-real/model.zip', 'outputs/research-real/model.json',
               'outputs/research-current/current.zip', 'outputs/research-current/current.json',
               'database/schema.sql', 'docker-compose.production.yml', 'deployment/Caddyfile',
               'configs/student_upload_schema.json', 'configs/student_survey_schema.json',
               'assets/student-skills-template.xlsx',
               'scripts/build_student_template.mjs']
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


def test_release_uses_current_validation_and_never_historical_promotion(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / 'scripts/verify_release.py'
    spec = importlib.util.spec_from_file_location('verify_current_release', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    benchmark_dir = tmp_path / 'outputs/benchmarks'
    benchmark_dir.mkdir(parents=True)
    historical = {'selected_engine': 'DQN', 'promotion': {'DQN': {'promoted': True}}}
    (benchmark_dir / 'validation-2026-10-07.json').write_text(json.dumps(historical))
    current = benchmark_dir / 'current-validation.json'
    current.write_text(json.dumps({'selected_engine': 'Hungarian', 'promotion': {}}))
    output = tmp_path / 'release.json'
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['verify_release', '--output', str(output)])
    module.main()
    manifest = json.loads(output.read_text())
    assert manifest['selected_engine'] == 'Hungarian'
    assert manifest['promoted_models'] == []
    assert manifest['benchmark_status'] == 'present'
    assert manifest['evidence_hashes']['outputs/benchmarks/current-validation.json']
    current.unlink()
    module.main()
    manifest = json.loads(output.read_text())
    assert manifest['selected_engine'] is None
    assert manifest['promoted_models'] == []
    assert manifest['evidence_hashes']['outputs/benchmarks/current-validation.json'] is None
    assert manifest['benchmark_status'] == 'missing'
    assert 'current validation benchmark is missing' in manifest['limitations']
