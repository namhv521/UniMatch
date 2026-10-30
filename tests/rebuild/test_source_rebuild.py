import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from src.data_pipeline.source_rebuild import rebuild


def fixture(root: Path):
    source = root / 'source'
    source.mkdir()
    path = source / 'technical.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 30), 'Inventory technical fixture. No actual student identity.')
        doc.save(path)
    output = root / 'output'
    (output / 'reports').mkdir(parents=True)
    gate = output / 'reports/phase0_gate.json'
    gate.write_text(json.dumps({'status': 'verified', 'can_start_phase1': True}), encoding='utf-8')
    import csv
    with (output / 'reports/input_inventory.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['relative_path', 'format', 'sha256'])
        writer.writeheader()
        writer.writerow({'relative_path': path.name, 'format': 'pdf', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    gate.write_text(json.dumps({'status': 'verified', 'can_start_phase1': True, 'actual_source_files': 1,
                               'inventory_sha256': hashlib.sha256((output / 'reports/input_inventory.csv').read_bytes()).hexdigest()}), encoding='utf-8')
    return source, output


def test_pipeline_requires_preceding_gate_and_accounts_for_quarantine(tmp_path):
    source, output = fixture(tmp_path)
    gate_path = output / 'reports/phase0_gate.json'
    original_gate = gate_path.read_text(encoding='utf-8')
    gate_path.write_text('{"status":"blocked","can_start_phase1":false}', encoding='utf-8')
    with pytest.raises(ValueError, match='phase0'):
        rebuild(source, output, ocr_mode='off')
    gate_path.write_text(original_gate, encoding='utf-8')
    result = rebuild(source, output, ocr_mode='off')
    assert result['status'] == 'verified'
    assert result['original_sources_accounted'] == 1
    assert result['evidence_errors'] == 0
    rows = [json.loads(line) for line in (Path(result['run_dir']) / 'bronze/student_candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 1 and rows[0]['status'] == 'quarantined'
    assert rows[0]['review_status'] == 'needs_review'


def test_modified_source_cannot_use_stale_inventory(tmp_path):
    source, output = fixture(tmp_path)
    (source / 'technical.pdf').write_bytes(b'changed after inventory')
    with pytest.raises(ValueError, match='source_hash_mismatch'):
        rebuild(source, output, ocr_mode='off')


def test_inventory_cannot_redefine_accepted_source_set(tmp_path):
    source, output = fixture(tmp_path)
    inventory = output / 'reports/input_inventory.csv'
    inventory.write_text('relative_path,format,sha256\n', encoding='utf-8-sig')
    with pytest.raises(ValueError, match='phase0_inventory'):
        rebuild(source, output, ocr_mode='off')
    gate_path = output / 'reports/phase0_gate.json'
    gate = json.loads(gate_path.read_text(encoding='utf-8'))
    gate['inventory_sha256'] = hashlib.sha256(inventory.read_bytes()).hexdigest()
    gate_path.write_text(json.dumps(gate), encoding='utf-8')
    with pytest.raises(ValueError, match='phase0_inventory'):
        rebuild(source, output, ocr_mode='off')
    assert not (output / 'phase1_runs').exists()
