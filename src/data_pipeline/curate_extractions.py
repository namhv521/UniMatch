"""Materialize grounded LLM profiles without losing source rows or ambiguous identities."""
import json
from collections import defaultdict
from pathlib import Path

from .crawl_advisors import write_csv
from .llm_extract import validate_profile
from .merge_publications import link_declarant

FEATURES = ['thesis_title', 'field_category', 'web_languages', 'app_languages',
            'frontend_frameworks', 'backend_frameworks', 'ai_frameworks', 'database_cache',
            'app_db_backend', 'ai_problems', 'data_tools', 'data_models', 'research_methods',
            'primary_role', 'secondary_roles']


def main():
    root = Path('data/curated')
    root.mkdir(parents=True, exist_ok=True)
    advisors = json.loads((root / 'advisors.json').read_text(encoding='utf-8'))
    adjudication_path = root / 'metadata_adjudications.json'
    adjudications = json.loads(adjudication_path.read_text(encoding='utf-8')) if adjudication_path.exists() else []
    sources = []
    seen = set()
    for path in sorted(Path('data/extracted/llm').glob('*.json')):
        artifact = json.loads(path.read_text(encoding='utf-8'))
        if 'profile' not in artifact or artifact['source_sha256'] in seen:
            continue
        seen.add(artifact['source_sha256'])
        profile = artifact['profile']
        applied = [item for item in adjudications if item['source_sha256'] == artifact['source_sha256']]
        if applied:
            document = Path('data/extracted/documents') / (artifact['source_sha256'] + '.json')
            pages = json.loads(document.read_text(encoding='utf-8'))['pages']
            for item in applied:
                field = item['field']
                if field not in ('student_id', 'submission_year', 'thesis_title'):
                    raise ValueError('Metadata adjudication field is not allowed')
                profile[field] = item['value']
                profile['evidence'] = [entry for entry in profile['evidence'] if entry['field'] != field]
                profile['evidence'].append({'field': field, 'value': str(item['value']),
                                            'page': item['page'], 'quote': item['quote'], 'kind': 'direct'})
            profile = validate_profile(profile, pages)
        row = {**profile, 'thesis_id': artifact['source_sha256'][:20],
               'source_sha256': artifact['source_sha256'], 'source_file': artifact['source_file'],
               'extraction_model': artifact['model'], 'needs_review': artifact['needs_review'],
               'metadata_adjudications': applied,
               'advisor_id': link_declarant(profile.get('advisor_name') or '', advisors),
               'feature_text': ' '.join(' '.join(profile[field]) if isinstance(profile.get(field), list)
                                       else str(profile.get(field) or '') for field in FEATURES)}
        sources.append(row)
    groups = defaultdict(list)
    review = []
    for row in sources:
        if not all(row.get(key) for key in ('student_id', 'submission_year', 'thesis_title')):
            review.append({'source_sha256': row['source_sha256'], 'reason': 'missing identity/year/title'})
        else:
            groups[row['student_id']].append(row)
    curated = []
    for student, rows in sorted(groups.items()):
        if len({row['submission_year'] for row in rows}) != 1:
            review.append({'student_id': student, 'reason': 'conflicting submission years',
                           'sources': [row['source_sha256'] for row in rows]})
            continue
        # Stable canonical selection; all alternative source records remain in JSONL.
        row = max(rows, key=lambda row: (len(row['evidence']), len(row['feature_text']), row['source_sha256']))
        row = {**row, 'source_versions': [item['source_sha256'] for item in rows]}
        curated.append(row)
    with (root / 'thesis_source_records.jsonl').open('w', encoding='utf-8') as target:
        for row in sources:
            target.write(json.dumps(row, ensure_ascii=False) + '\n')
    (root / 'theses.json').write_text(json.dumps(curated, ensure_ascii=False, indent=2), encoding='utf-8')
    write_csv(root / 'theses.csv', curated)
    manifest = json.loads(Path('data/extracted/documents/manifest.json').read_text(encoding='utf-8'))
    expected = {row['sha256'] for row in manifest if row['status'] == 'extracted'}
    report = {'unique_source_documents': len(expected), 'llm_extracted_documents': len(sources),
              'pending_documents': len(expected - seen), 'curated_students': len(curated),
              'review_items': review, 'ready_for_full_experiment': expected <= seen and not review,
              'profiles_with_withheld_or_reviewed_claims': sum(row['needs_review'] for row in sources),
              'warning': ('Missing documents or metadata block full experiments' if expected - seen or review
                          else 'Grounded extraction complete; inferred skills and current advisor snapshot remain research limitations')}
    (root / 'curation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'review_items'}, indent=2))


if __name__ == '__main__':
    main()
