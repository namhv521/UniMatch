"""Audit locally produced checkpoint hashes and milestone coverage without loading models."""
import hashlib
import json
from pathlib import Path

if __name__ == '__main__':
    results = []
    for path in sorted(Path('outputs/models').glob('*_steps*.json')):
        metadata = json.loads(path.read_text(encoding='utf-8'))
        model = path.with_suffix('.zip')
        valid = model.exists() and hashlib.sha256(model.read_bytes()).hexdigest() == metadata['model_sha256']
        valid = valid and metadata['actual_timesteps'] >= metadata['requested_timesteps']
        valid = valid and metadata['partial_data_smoke_only'] is False
        results.append({'checkpoint': str(model), 'valid': valid,
                        'dataset_sha256': metadata['configuration']['dataset_sha256'],
                        'algorithm': metadata['configuration']['algorithm'],
                        'seed': metadata['configuration']['seed'],
                        'requested_steps': metadata['requested_timesteps'],
                        'actual_steps': metadata['actual_timesteps']})
    report = {'valid_existing_checkpoints': bool(results) and all(row['valid'] for row in results),
              'checkpoint_count': len(results), 'expected_grid_checkpoint_count': 80,
              'full_grid_present': len(results) == 80, 'checkpoints': results,
              'scope': 'Hash and milestone consistency, not evidence of model quality or bitwise-resumable RNG.'}
    target = Path('outputs/training/checkpoint_integrity_audit.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'checkpoints'}))
    raise SystemExit(0 if report['valid_existing_checkpoints'] else 1)
