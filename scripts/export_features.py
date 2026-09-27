"""Export train-only TF-IDF compatibility and aligned identity/split provenance."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.dataset import load_dataset

if __name__ == '__main__':
    data = load_dataset()
    root = Path('data/features')
    root.mkdir(parents=True, exist_ok=True)
    np.save(root / 'compatibility_matrix.npy', data['scores'])
    manifest = {'dataset_sha256': data['sha256'], 'representation': 'train-only TF-IDF',
                'student_ids': [row['student_id'] for row in data['students']],
                'advisor_ids': [row['advisor_id'] for row in data['advisors']],
                'split': {key: value.tolist() for key, value in data['split'].items()},
                'future_indices': data['future_indices'], 'shape': list(data['scores'].shape)}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'shape': manifest['shape'], 'split': {k: len(v) for k, v in manifest['split'].items()},
                      'future_count': len(data['future_indices'])}))
