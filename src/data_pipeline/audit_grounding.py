"""Revalidate cached extractions locally after grounding rules change; no API calls."""
import json
from pathlib import Path

from .llm_extract import ground_profile


def main():
    counts = {'audited': 0, 'withheld_fields': 0}
    for path in Path('data/extracted/llm').glob('*.json'):
        artifact = json.loads(path.read_text(encoding='utf-8'))
        if 'profile' not in artifact:
            continue
        source = Path('data/extracted/documents') / (artifact['source_sha256'] + '.json')
        pages = json.loads(source.read_text(encoding='utf-8'))['pages']
        profile, rejected = ground_profile(artifact.get('raw_profile', artifact['profile']), pages)
        counts['withheld_fields'] += sum(profile.get(key) != value for key, value in artifact['profile'].items()
                                        if key not in ('evidence', 'warnings'))
        artifact.update(profile=profile, rejected_evidence=rejected, grounding_version=2,
                        needs_review=bool(rejected) or not all(profile.get(key)
                                    for key in ('student_id', 'submission_year', 'thesis_title')))
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
        counts['audited'] += 1
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
