"""Fetch pinned official OCR language models into private rebuild tooling."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

REVISION = '87416418657359cb625c412a48b6e1d6d41c29bd'
EXPECTED = {
    'vie.traineddata': '79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1',
    'eng.traineddata': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    'LICENSE': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30',
}


def setup(destination=Path('data_rebuild/v1/tools/tessdata')):
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, expected in EXPECTED.items():
        path = destination / name
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{name}'
        if path.exists():
            data = path.read_bytes()
        else:
            with urlopen(url, timeout=30) as response:
                data = response.read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f'OCR model checksum mismatch: {name}')
        if not path.exists():
            path.write_bytes(data)
        rows.append({'name': name, 'url': url, 'sha256': actual, 'size_bytes': len(data)})
    (destination / 'manifest.json').write_text(json.dumps({
        'commit': REVISION, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'files': rows,
    }, indent=2), encoding='utf-8')
    return rows


if __name__ == '__main__':
    print(json.dumps({'verified_ocr_files': len(setup()), 'commit': REVISION}))
