import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from scripts.filtered_experiment import prepare, verify_transfer

ROOT = Path(__file__).parents[2]


def test_exclusion_preserves_split_and_checkpoint_evaluation_contract(tmp_path):
    source = ROOT / 'outputs/snapshot-220-before-exclusion'
    source = source if source.exists() else ROOT
    for name in ('curated', 'features'):
        shutil.copytree(source / 'data' / name, tmp_path / 'data' / name)
    failures = ROOT / 'outputs/data_quality/v2026-09-28/failure_report.json'
    old = json.loads((tmp_path / 'data/curated/theses.json').read_text(encoding='utf-8'))
    old_split = json.loads((tmp_path / 'data/curated/split_indices.json').read_text())
    result = prepare(tmp_path, failures)
    assert result['retained'] == 215 and result['excluded'] == 5
    current = json.loads((tmp_path / 'data/curated/split_indices.json').read_text())
    excluded = {r['student_id'] for r in old if r['source_sha256'] in result['excluded_sources']}
    for name, ids in old_split['student_ids'].items():
        assert current['student_ids'][name] == [i for i in ids if i not in excluded]
    verify_transfer(tmp_path, tmp_path / 'outputs/snapshot-220-before-exclusion')
    assert prepare(tmp_path, failures) == result
    matrix_path = tmp_path / 'data/features/compatibility_matrix_v2.npy'
    matrix = np.load(matrix_path)
    matrix[0, 0] += .01
    np.save(matrix_path, matrix)
    with pytest.raises(ValueError):
        verify_transfer(tmp_path, tmp_path / 'outputs/snapshot-220-before-exclusion')
