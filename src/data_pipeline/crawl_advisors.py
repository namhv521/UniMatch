"""Crawl public FIT profiles and retain auditable course/publication skill evidence."""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .extract_documents import canonical

ENDPOINT = 'https://fit.neu.edu.vn/api/lecturers'
# Direct keyword extraction is intentionally conservative; generic DL does not imply PyTorch.
SKILLS = {
    'Python': ('python',), 'Java': ('java',), 'JavaScript': ('javascript',),
    'C++': ('c++',), 'C#': ('c#',), 'React': ('react', 'reactjs'),
    'FastAPI': ('fastapi',), 'Django': ('django',), 'Docker': ('docker',),
    'Kubernetes': ('kubernetes',), 'PyTorch': ('pytorch',), 'TensorFlow': ('tensorflow',),
    'SQL': ('sql',), 'Machine Learning': ('machine learning', 'học máy'),
    'Deep Learning': ('deep learning', 'học sâu'),
    'Natural Language Processing': ('natural language processing', 'xử lý ngôn ngữ tự nhiên'),
    'Computer Vision': ('computer vision', 'thị giác máy tính', 'xử lý ảnh'),
    'Data Mining': ('data mining', 'khai phá dữ liệu'),
    'Data Analysis': ('data analysis', 'phân tích dữ liệu'),
    'Web Development': ('web development', 'lập trình web', 'thiết kế web', 'công nghệ web'),
    'Mobile Development': ('mobile', 'di động'),
    'Cybersecurity': ('cybersecurity', 'an toàn thông tin', 'an ninh mạng', 'bảo mật'),
    'IoT': ('internet of things', 'iot', 'internet vạn vật'),
    'Cloud Computing': ('cloud computing', 'điện toán đám mây'),
    'Databases': ('database', 'cơ sở dữ liệu'),
    'Computer Networks': ('computer network', 'mạng máy tính', 'quản trị mạng'),
    'Software Engineering': ('software engineering', 'kỹ thuật phần mềm', 'công nghệ phần mềm'),
    'Reinforcement Learning': ('reinforcement learning', 'học tăng cường'),
    'Optimization': ('optimization', 'tối ưu hóa', 'tối ưu hoá'),
}


def blocks(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    tags = soup.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    return [tag.get_text(' ', strip=True) for tag in tags
            if not tag.find(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]


def parse_profile(record):
    advisor_id = str(record.get('documentId') or record['id'])
    url = 'https://fit.neu.edu.vn/lecturer/' + record.get('slug', '')
    name = record.get('displayName', '').strip()
    title_match = re.match(r'^((?:(?:PGS|GS|TS|ThS|Th\.S)[.\s]*)+)', name, flags=re.IGNORECASE)
    title = title_match.group(0).strip() if title_match else ''
    sections = {'courses': [], 'research_fields': [], 'publications': [], 'projects': [], 'books': [], 'other': []}
    current = 'other'
    for text in blocks(record.get('additionalInfo')):
        normalized = canonical(text)
        heading = None
        if len(text) < 160 and text.upper() == text:
            if 'giảng dạy' in normalized:
                heading = 'courses'
            elif 'lĩnh vực nghiên cứu' in normalized or 'hướng nghiên cứu' in normalized:
                heading = 'research_fields'
            elif 'bài báo' in normalized or 'công bố' in normalized:
                heading = 'publications'
            elif 'đề tài' in normalized:
                heading = 'projects'
            elif 'sách' in normalized or 'giáo trình' in normalized:
                heading = 'books'
        if heading:
            current = heading
        elif text:
            sections[current].append(text)
    evidence, publications = [], []
    seen_publications = set()
    for section in ('courses', 'research_fields', 'publications', 'projects', 'books'):
        for text in sections[section]:
            source_id = hashlib.sha256((advisor_id + section + canonical(text)).encode()).hexdigest()[:20]
            years = re.findall(r'\b(?:19|20)\d{2}\b', text)
            year = max(map(int, years)) if years else None
            if section == 'publications' and canonical(text) not in seen_publications:
                publications.append({'advisor_id': advisor_id, 'evidence_id': source_id,
                                     'citation_text': text, 'year': year, 'source_url': url,
                                     'title_status': 'source citation; exact title requires structured parsing'})
                seen_publications.add(canonical(text))
            for skill, terms in SKILLS.items():
                if any(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', canonical(text)) for term in terms):
                    evidence.append({'advisor_id': advisor_id, 'skill_name': skill,
                                     'evidence_id': source_id, 'source_kind': section,
                                     'quote': text, 'year': year, 'source_url': url,
                                     'inference_kind': 'title_supported' if section in ('publications', 'projects') else 'direct',
                                     'method': 'keyword evidence v1'})
    skills = sorted({item['skill_name'] for item in evidence})
    profile = {'advisor_id': advisor_id, 'advisor_name': name, 'academic_title': title,
               'primary_field': '; '.join(sections['research_fields']),
               'skill_text': '; '.join(skills), 'skill_count': len(skills),
               'publication_evidence_count': len(publications),
               'courses': sections['courses'], 'research_fields': sections['research_fields'],
               'projects': sections['projects'], 'profile_text': '\n'.join(
                   sections['courses'] + sections['research_fields'] + sections['publications'] + sections['projects']),
               'quota': None, 'quota_source': 'not published; set per cohort ceil(N/M)',
               'source_url': url, 'source_updated_at': record.get('updatedAt'),
               'needs_review': not bool(skills),
               'temporal_note': 'Current snapshot; undated evidence is not verified available before 2025'}
    return profile, evidence, publications


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                         for key, value in row.items()} for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached', type=Path, help='Use an existing official API JSON snapshot')
    args = parser.parse_args()
    cache = Path('data/cache/fit')
    cache.mkdir(parents=True, exist_ok=True)
    records = []
    if args.cached:
        body = json.loads(args.cached.read_text(encoding='utf-8-sig'))
        records = body['data']
        if len(records) != body['meta']['pagination']['total']:
            raise ValueError('Cached response is incomplete; fetch all pages')
    else:
        page = 1
        while True:
            response = requests.get(ENDPOINT, params={'populate': '*', 'pagination[pageSize]': 100,
                                                      'pagination[page]': page, 'locale': 'vi'}, timeout=45)
            response.raise_for_status()
            body = response.json()
            (cache / f'lecturers-page-{page}.json').write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')
            records.extend(body['data'])
            if page >= body['meta']['pagination']['pageCount']:
                break
            page += 1
    advisors, evidence, publications = [], [], []
    for record in records:
        profile, skill_rows, publication_rows = parse_profile(record)
        advisors.append(profile)
        evidence.extend(skill_rows)
        publications.extend(publication_rows)
    output = Path('data/curated')
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [('advisors', advisors), ('advisor_skill_evidence', evidence), ('advisor_publications', publications)]:
        write_csv(output / f'{name}.csv', rows)
        (output / f'{name}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {'retrieved_at': datetime.now(timezone.utc).isoformat(), 'source': ENDPOINT,
               'advisor_count': len(advisors), 'publication_citations': len(publications),
               'skill_evidence_rows': len(evidence), 'profiles_needing_review': sum(a['needs_review'] for a in advisors),
               'expected_count_in_old_spec': 39, 'count_matches_old_spec': len(advisors) == 39}
    (output / 'advisor_crawl_report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
