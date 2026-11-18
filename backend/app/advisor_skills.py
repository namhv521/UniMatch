"""Complete, fair advisor skill profiles & CSV import/export for UniMatch."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from src.data_pipeline.normalization import load_taxonomy, normalize_mentions

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_CSV = ROOT / 'docs/advisors_full_skills.csv'
TAXONOMY_PATH = ROOT / 'configs/data/taxonomy_v1.yaml'

SKILL_GROUP_TO_TAXONOMY = {
    'research_domains': 'research_domain_tags',
    'topic_tags': 'topic_tags',
    'programming_languages': 'programming_languages',
    'frameworks_libraries': 'frameworks_libraries',
    'databases': 'databases',
    'ml_ai_methods': 'ml_ai_methods',
    'software_engineering_methods': 'software_engineering_methods',
    'research_methods': 'research_methods',
}

CSV_FIELDS = (
    'advisor_id',
    'advisor_name',
    'department',
    'academic_title',
    'research_domains',
    'topic_tags',
    'programming_languages',
    'frameworks_libraries',
    'databases',
    'ml_ai_methods',
    'software_engineering_methods',
    'research_methods',
    'target_quota',
    'summary',
)

VI_LABELS = {
    'ai': 'Trí tuệ nhân tạo (AI)',
    'data_science': 'Khoa học dữ liệu',
    'software_engineering': 'Kỹ thuật phần mềm',
    'information_systems': 'Hệ thống thông tin',
    'cybersecurity': 'An toàn thông tin',
    'networks_iot': 'Mạng & IoT',
    'business_analytics': 'Phân tích kinh doanh (BA/BI)',
    'web_development': 'Phát triển Web',
    'mobile_development': 'Phát triển Di động',
    'game_development': 'Phát triển Game',
    'human_computer_interaction': 'Tương tác người-máy (HCI)',
    'blockchain': 'Blockchain',
    'machine_learning': 'Học máy (ML)',
    'computer_vision': 'Thị giác máy tính (CV)',
    'nlp': 'Xử lý ngôn ngữ tự nhiên (NLP)',
    'llm': 'LLM & RAG / AI Agent',
    'reinforcement_learning': 'Học tăng cường (RL)',
    'time_series': 'Chuỗi thời gian',
    'recommendation_systems': 'Hệ thống gợi ý',
    'optimization': 'Tối ưu hóa',
    'frontend_development': 'Frontend',
    'backend_development': 'Backend',
    'full_stack_development': 'Full-stack',
    'mobile_app_development': 'Ứng dụng Mobile',
    'game_programming': 'Lập trình Game / 3D',
    'ui_ux_design': 'Thiết kế UI/UX',
    'distributed_systems': 'Hệ thống phân tán',
    'microservices': 'Microservices',
    'embedded_systems': 'Hệ thống nhúng',
    'internet_of_things': 'IoT',
    'virtual_augmented_reality': 'VR / AR',
    'classification': 'Phân loại dữ liệu',
    'regression': 'Hồi quy & Dự báo',
    'quantitative_analysis': 'Phân tích định lượng',
    'qualitative_analysis': 'Phân tích định tính',
    'experiment_design': 'Thiết kế thực nghiệm',
    'survey': 'Nghiên cứu khảo sát',
    'literature_review': 'Tổng quan nghiên cứu',
    'software_architecture': 'Kiến trúc phần mềm',
    'api_design': 'Thiết kế API',
    'backend_engineering': 'Kỹ thuật Backend',
    'frontend_engineering': 'Kỹ thuật Frontend',
    'design_patterns': 'Design Patterns',
    'testing': 'Kiểm thử phần mềm',
    'agile': 'Agile / Scrum',
    'uml': 'Mô hình hóa UML',
    'devops': 'DevOps & Cloud',
}


def _split_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    seen = []
    for item in str(raw).replace(',', ';').split(';'):
        clean = item.strip()
        if clean and clean not in seen:
            seen.append(clean)
    return seen


def tag_label(tag: str) -> str:
    if tag in VI_LABELS:
        return VI_LABELS[tag]
    return tag.replace('_', ' ').title()


def load_default_skill_map() -> dict[str, dict]:
    if not DEFAULT_SKILLS_CSV.is_file():
        return {}
    with DEFAULT_SKILLS_CSV.open(encoding='utf-8-sig', newline='') as stream:
        return {row['advisor_id'].strip(): dict(row) for row in csv.DictReader(stream) if row.get('advisor_id')}


def load_db_skill_overrides(db) -> dict[str, dict]:
    if db is None:
        return {}
    rows = db.execute('SELECT * FROM thesis_advisor_skills ORDER BY advisor_id').fetchall()
    return {row['advisor_id']: dict(row) for row in rows}


def _taxonomy_aliases_text(profile: dict, taxonomy: dict) -> str:
    """Build canonical bilingual keyword text from structured skill tags so E4 scores every lecturer fairly."""
    phrases = []
    groups = taxonomy.get('groups', {})
    for col, tax_group in SKILL_GROUP_TO_TAXONOMY.items():
        group_defs = groups.get(tax_group, {})
        for tag in _split_tags(profile.get(col)):
            phrases.append(tag.replace('_', ' '))
            if tag in VI_LABELS:
                phrases.append(VI_LABELS[tag])
            tag_def = group_defs.get(tag, {})
            phrases.extend(tag_def.get('aliases', [])[:3])
            phrases.extend(tag_def.get('case_sensitive_aliases', [])[:2])
    if profile.get('summary'):
        phrases.append(str(profile['summary']))
    return ' ; '.join(dict.fromkeys(p for p in phrases if p))


_ENRICH_CACHE: dict[tuple, list[dict]] = {}


def build_advisor_skill_entry(advisor: dict, taxonomy: dict, default_map: dict, db_map: dict) -> dict:
    aid = advisor['advisor_id']
    name = advisor.get('advisor_name') or advisor.get('name') or aid
    base = {**default_map.get(aid, {}), **db_map.get(aid, {})}
    raw_desc = advisor.get('research_description', '') or ''
    has_base_skills = any(_split_tags(base.get(col)) for col in SKILL_GROUP_TO_TAXONOMY)
    extracted = {}
    if not has_base_skills and raw_desc:
        for match in normalize_mentions(raw_desc[:6000], taxonomy):
            extracted.setdefault(match['group'], []).append(match['tag'])

    entry = {
        'advisor_id': aid,
        'advisor_name': name,
        'department': base.get('department') or advisor.get('department') or 'Khoa Công nghệ thông tin',
        'academic_title': base.get('academic_title') or advisor.get('academic_title') or '',
        'source_url': advisor.get('source_url') or advisor.get('university_url') or '',
        'scholar_url': advisor.get('scholar_url') or '',
        'github_url': advisor.get('github_url') or '',
        'target_quota': base.get('target_quota'),
        'summary': (base.get('summary') or '').strip(),
    }
    all_tags = []
    grouped_labels = {}
    for col, tax_group in SKILL_GROUP_TO_TAXONOMY.items():
        merged = list(dict.fromkeys(_split_tags(base.get(col)) + extracted.get(tax_group, [])))
        entry[col] = merged
        grouped_labels[col] = [tag_label(t) for t in merged]
        for t in merged:
            if t not in all_tags:
                all_tags.append(t)

    if not entry['summary']:
        top_labels = [tag_label(t) for t in all_tags[:5]]
        entry['summary'] = (
            f"Hướng chuyên môn: {', '.join(top_labels)}."
            if top_labels else 'Giảng viên hướng dẫn khóa luận tốt nghiệp.'
        )

    entry['grouped_labels'] = grouped_labels
    entry['all_tags'] = all_tags
    entry['display_skills'] = [tag_label(t) for t in all_tags[:12]]
    entry['skill_count'] = len(all_tags)
    entry['fairness_ready'] = len(all_tags) >= 3 or bool(raw_desc.strip())
    entry['enriched_text'] = '\n'.join(filter(None, [raw_desc, _taxonomy_aliases_text(
        {k: ';'.join(entry[k]) for k in SKILL_GROUP_TO_TAXONOMY} | {'summary': entry['summary']},
        taxonomy,
    )]))
    return entry


def enrich_advisors(active, db=None) -> list[dict]:
    taxonomy = getattr(active, 'taxonomy', None) or load_taxonomy(TAXONOMY_PATH)
    default_map = load_default_skill_map()
    db_map = load_db_skill_overrides(db)
    cache_key = (
        id(active),
        tuple((a.get('advisor_id'), a.get('advisor_name'), (a.get('research_description') or '')[:120]) for a in active.advisors),
        tuple(sorted((aid, row.get('updated_at', ''), row.get('summary', '')) for aid, row in db_map.items())),
    )
    cached = _ENRICH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    enriched = []
    for advisor in active.advisors:
        skill_entry = build_advisor_skill_entry(advisor, taxonomy, default_map, db_map)
        enriched.append({
            **advisor,
            'advisor_name': skill_entry['advisor_name'],
            'research_description': skill_entry['enriched_text'],
            'raw_research_description': advisor.get('research_description', ''),
            'skill_profile': skill_entry,
        })
    if len(_ENRICH_CACHE) > 16:
        _ENRICH_CACHE.clear()
    _ENRICH_CACHE[cache_key] = enriched
    return enriched


def export_advisor_skills_csv(active, db=None) -> str:
    advisors = enrich_advisors(active, db=db)
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for adv in advisors:
        sp = adv['skill_profile']
        row = {
            'advisor_id': sp['advisor_id'],
            'advisor_name': sp['advisor_name'],
            'department': sp['department'],
            'academic_title': sp['academic_title'],
            'target_quota': '' if sp['target_quota'] is None else str(sp['target_quota']),
            'summary': sp['summary'],
        }
        for col in SKILL_GROUP_TO_TAXONOMY:
            row[col] = ';'.join(sp[col])
        writer.writerow({
            k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
            for k, v in row.items()
        })
    return out.getvalue()


def save_advisor_skills_csv(db, csv_text: str, valid_advisor_ids: set[str] | tuple[str, ...]) -> dict:
    if not isinstance(csv_text, str) or '\x00' in csv_text or len(csv_text) > 512 * 1024:
        raise HTTPException(422, 'invalid_advisor_skills_csv')
    taxonomy = load_taxonomy(TAXONOMY_PATH)
    allowed_ids = set(valid_advisor_ids)
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff'), newline=''), strict=True)
        headers = reader.fieldnames or []
        required = {'advisor_id', 'advisor_name'}
        if not required <= set(headers) or not set(headers) <= set(CSV_FIELDS):
            raise HTTPException(422, 'invalid_advisor_skills_headers')
        parsed = []
        seen = set()
        for row in reader:
            if not any(row.values()):
                continue
            aid = (row.get('advisor_id') or '').strip()
            name = (row.get('advisor_name') or '').strip()
            if not aid or not name or aid not in allowed_ids:
                raise HTTPException(422, {'code': 'invalid_advisor_skills_row', 'row': reader.line_num})
            if aid in seen:
                raise HTTPException(422, {'code': 'duplicate_advisor_id', 'row': reader.line_num})
            seen.add(aid)
            quota_raw = (row.get('target_quota') or '').strip()
            target_quota = None
            if quota_raw:
                if not quota_raw.isdigit() or not 0 <= int(quota_raw) <= 200:
                    raise HTTPException(422, {'code': 'invalid_advisor_quota', 'row': reader.line_num})
                target_quota = int(quota_raw)
            normalized_cols = {}
            for col, tax_group in SKILL_GROUP_TO_TAXONOMY.items():
                allowed_tags = taxonomy['groups'].get(tax_group, {})
                tags = []
                for token in _split_tags(row.get(col, '')):
                    slug = token.lower().strip().replace(' ', '_')
                    if slug in allowed_tags:
                        tags.append(slug)
                    else:
                        matched = [m['tag'] for m in normalize_mentions(token, taxonomy) if m['group'] == tax_group]
                        tags.extend(matched)
                normalized_cols[col] = ';'.join(dict.fromkeys(tags))
            summary = (row.get('summary') or '').strip()[:1000]
            if not any(normalized_cols.values()) and not summary:
                raise HTTPException(422, {'code': 'advisor_skills_empty', 'row': reader.line_num})
            parsed.append({
                'advisor_id': aid,
                'advisor_name': name[:160],
                'department': (row.get('department') or 'Khoa Công nghệ thông tin').strip()[:160],
                'academic_title': (row.get('academic_title') or '').strip()[:80],
                **normalized_cols,
                'summary': summary,
                'target_quota': target_quota,
            })
    except (csv.Error, UnicodeError):
        raise HTTPException(422, 'invalid_advisor_skills_csv') from None

    if not parsed:
        raise HTTPException(422, 'invalid_advisor_skills_csv')

    now = datetime.now(timezone.utc).isoformat()
    for item in parsed:
        db.execute(
            'INSERT INTO thesis_advisor_skills '
            '(advisor_id,advisor_name,department,academic_title,research_domains,topic_tags,'
            'programming_languages,frameworks_libraries,databases,ml_ai_methods,'
            'software_engineering_methods,research_methods,summary,target_quota,updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(advisor_id) DO UPDATE SET '
            'advisor_name=excluded.advisor_name,department=excluded.department,'
            'academic_title=excluded.academic_title,research_domains=excluded.research_domains,'
            'topic_tags=excluded.topic_tags,programming_languages=excluded.programming_languages,'
            'frameworks_libraries=excluded.frameworks_libraries,databases=excluded.databases,'
            'ml_ai_methods=excluded.ml_ai_methods,software_engineering_methods=excluded.software_engineering_methods,'
            'research_methods=excluded.research_methods,summary=excluded.summary,'
            'target_quota=excluded.target_quota,updated_at=excluded.updated_at',
            (
                item['advisor_id'], item['advisor_name'], item['department'], item['academic_title'],
                item['research_domains'], item['topic_tags'], item['programming_languages'],
                item['frameworks_libraries'], item['databases'], item['ml_ai_methods'],
                item['software_engineering_methods'], item['research_methods'], item['summary'],
                item['target_quota'], now,
            ),
        )
    return {'updated_count': len(parsed)}
