"""Attach official publication titles by exact normalized declarant identity."""
import json
import re
from pathlib import Path

from .crawl_advisors import write_csv
from .extract_documents import canonical


def identity_name(value):
    value = re.sub(r'\([^)]*\)', '', value)
    value = re.sub(r'^(?:(?:PGS|GS|TS|ThS|Th\.S|CN)[.\s]*)+', '', value, flags=re.IGNORECASE)
    return canonical(value)


def link_declarant(name, profiles):
    matches = [profile['advisor_id'] for profile in profiles
               if identity_name(name) == identity_name(profile['advisor_name'])]
    return matches[0] if len(matches) == 1 else None


def field_text(record, key):
    field = record.get(key, {})
    if isinstance(field, str):
        return field
    parts = field.get('title', field.get('rich_text', []))
    return ''.join(part.get('plain_text', part.get('text', {}).get('content', '')) for part in parts)


def main():
    root = Path('data/curated')
    profiles = json.loads((root / 'advisors.json').read_text(encoding='utf-8'))
    result = []
    for index, kind in [(1, 'project'), (2, 'journal'), (3, 'conference')]:
        source = Path(f'data/cache/fit/research/publication-initialData-{index}.json')
        for record in json.loads(source.read_text(encoding='utf-8')):
            title = field_text(record, 'TenDeTai' if kind == 'project' else 'TenCongTrinh')
            declarant = field_text(record, 'Người kê khai' if kind == 'project' else 'NguoiKeKhai')
            date = field_text(record, 'ThoiGianCongBo') or field_text(record, 'Date') or field_text(record, 'Nam')
            years = re.findall(r'\b(?:19|20)\d{2}\b', date)
            advisor_id = link_declarant(declarant, profiles)
            result.append({'publication_id': record['id'], 'title': title, 'kind': kind,
                           'year': int(years[-1]) if years else None, 'publication_date_raw': date,
                           'declarant_name': re.sub(r'\([^)]*\)', '', declarant).strip(),
                           'advisor_id': advisor_id, 'relationship': 'declarant' if advisor_id else 'unmatched',
                           'source_url': 'https://fit.neu.edu.vn/publication', 'source_cache': str(source)})
    write_csv(root / 'publication_titles.csv', result)
    (root / 'publication_titles.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    for profile in profiles:
        linked = [row for row in result if row['advisor_id'] == profile['advisor_id']]
        profile['declarant_publication_count'] = sum(row['kind'] != 'project' for row in linked)
        profile['declarant_project_count'] = sum(row['kind'] == 'project' for row in linked)
        profile['publication_titles'] = [row['title'] for row in linked if row['kind'] != 'project']
        profile['project_titles'] = [row['title'] for row in linked if row['kind'] == 'project']
    (root / 'advisors.json').write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(root / 'advisors.csv', profiles)
    print(json.dumps({'records': len(result), 'linked': sum(row['advisor_id'] is not None for row in result),
                      'unmatched': sum(row['advisor_id'] is None for row in result)}, indent=2))


if __name__ == '__main__':
    main()
