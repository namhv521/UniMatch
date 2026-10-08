import json

import numpy as np

from src.data_pipeline.inventory import build_manifest


def test_baseline_manifest_records_required_roots_and_is_reproducible(tmp_path):
    # Historical inventory describes its own snapshot, not live data forever.
    for name in ('curated', 'extracted', 'embeddings', 'features'):
        (tmp_path / 'data' / name).mkdir(parents=True)
    (tmp_path / 'data/curated/advisors.csv').write_text('advisor_id,advisor_name\na1,Example\n')
    (tmp_path / 'data/extracted/document.json').write_text('{"title":"Example"}')
    np.save(tmp_path / 'data/embeddings/vectors.npy', np.ones((1, 2)))
    np.save(tmp_path / 'data/features/scores.npy', np.ones((1, 1)))
    recorded = json.loads(json.dumps(build_manifest(tmp_path)))
    assert recorded == build_manifest(tmp_path)
    assert set(recorded['roots']) == {'curated', 'extracted', 'embeddings', 'features'}
    assert all(item['status'] == 'available' for item in recorded['roots'].values())
    assert recorded['roots']['curated']['schemas']['advisors.csv'] == ['advisor_id', 'advisor_name']
    (tmp_path / 'data/curated/advisors.csv').write_text('advisor_id,advisor_name\na1,Changed\n')
    assert recorded['roots']['curated']['sha256'] != build_manifest(tmp_path)['roots']['curated']['sha256']
