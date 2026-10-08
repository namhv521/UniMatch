"""Verify authenticated frontend API contract for a newly trained real RL model."""
import argparse
import http.cookiejar
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.smoke_api import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--dataset', choices=['real-train', 'real-validation'], default='real-validation')
    parser.add_argument('--algorithm', default='MaskablePPO')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    email, password = os.getenv('KLTN_LOGIN_EMAIL'), os.getenv('KLTN_LOGIN_PASSWORD')
    if not email or not password:
        parser.error('KLTN_LOGIN_EMAIL and KLTN_LOGIN_PASSWORD are required')
    base = args.base_url.rstrip('/')
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    health = request(opener, base, '/api/v1/health')
    assert health['data_loaded'] is True, 'serving data not loaded'
    request(opener, base, '/api/v1/auth/login', payload={'email': email, 'password': password})
    catalog = request(opener, base, '/api/v1/catalog')['data']
    compatible = [item for item in catalog['models'] if item['algorithm'] == args.algorithm
                  and item['seed'] == args.seed and item['status'] == 'unpromoted_research'
                  and args.dataset in item['supported_datasets']]
    assert compatible, 'no native current-snapshot real checkpoint available'
    data = request(opener, base, '/api/v1/datasets/' + args.dataset)['data']
    result = request(opener, base, '/api/v1/simulate', payload={
        'mode': 'rl_research', 'algorithm': args.algorithm, 'dataset': args.dataset, 'seed': args.seed,
    }, timeout=120)['data']
    assert len(result['assignments']) == len(data['students']), 'not every student assigned'
    assert result['metrics']['quota_violations'] == 0, 'capacity violated'
    assert result['experimental'] is True, 'research label missing'
    assert result['provenance']['dataset_sha256'] == data['provenance']['dataset_sha256']
    summary = request(opener, base, '/api/v1/results/summary')['data']
    assert summary.get('status') != 'not_evaluated', 'fresh validation report missing'
    assert result['model_version'] in [row['checkpoint_hash'] for row in summary.get('evaluated_checkpoints', [])], 'simulated checkpoint was not evaluated'
    print(json.dumps({'api_verified': True, 'dataset': args.dataset, 'algorithm': args.algorithm,
                      'students': len(data['students']), 'advisors': len(data['advisors']),
                      'quota_violations': result['metrics']['quota_violations'],
                      'invalid_proposals': result['metrics']['invalid_proposals'],
                      'selected_engine': summary.get('selected_engine'), 'promoted': False}))


if __name__ == '__main__':
    main()
