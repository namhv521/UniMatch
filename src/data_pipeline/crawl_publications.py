"""Decode official FIT publication page data without executing embedded JavaScript."""
import argparse
import json
import re
from pathlib import Path

import requests


def extract_publications(html):
    decoder = json.JSONDecoder()
    chunks = []
    for match in re.finditer(r'self\.__next_f\.push\(', html):
        payload, _ = decoder.raw_decode(html[match.end():].lstrip())
        if len(payload) > 1 and payload[0] == 1 and isinstance(payload[1], str):
            chunks.append(payload[1])
    rsc = ''.join(chunks)
    result = {'projects': [], 'journals': [], 'conferences': []}
    for match in re.finditer(r'"initialData"\s*:\s*', rsc):
        rows, _ = decoder.raw_decode(rsc[match.end():])
        if not isinstance(rows, list) or not rows:
            continue
        keys = set().union(*(row.keys() for row in rows))
        if 'TenDeTai' in keys:
            kind = 'projects'
        elif {'TenCongTrinh', 'MaSoISSN', 'Date'} <= keys:
            kind = 'journals'
        elif {'TenCongTrinh', 'Nam'} <= keys:
            kind = 'conferences'
        else:
            raise ValueError('Official publication schema changed; review before import')
        result[kind].extend(rows)
    if not all(result.values()):
        raise ValueError('Missing publication sections; page format may have changed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached', type=Path)
    args = parser.parse_args()
    root = Path('data/cache/fit/research')
    root.mkdir(parents=True, exist_ok=True)
    if args.cached:
        html = args.cached.read_text(encoding='utf-8')
    else:
        response = requests.get('https://fit.neu.edu.vn/publication', timeout=60)
        response.raise_for_status()
        html = response.text
        (root / 'publication.html').write_text(html, encoding='utf-8')
    data = extract_publications(html)
    for index, kind in enumerate(('projects', 'journals', 'conferences'), 1):
        (root / f'publication-initialData-{index}.json').write_text(
            json.dumps(data[kind], ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({kind: len(rows) for kind, rows in data.items()}))


if __name__ == '__main__':
    main()
