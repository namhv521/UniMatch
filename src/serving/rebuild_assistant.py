"""Deterministic, source-bound read-only tools; no LLM, network or training."""
import copy
import json
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from src.data_pipeline.normalization import normalize_mentions


FIELDS = ('research_topics', 'teaching_topics', 'profile_intro')
DISCLOSURE = 'Trợ lý deterministic chỉ đọc; điểm phù hợp chủ đề không phải độ chính xác phân công hoặc cam kết hướng dẫn.'


def _norm(text):
    text = unicodedata.normalize('NFD', str(text).lower()).replace('đ', 'd')
    return ' '.join(re.findall(r'\w+', ''.join(c for c in text if unicodedata.category(c) != 'Mn')))


def _contains(text, phrase):
    return bool(phrase) and (' '+phrase+' ') in (' '+text+' ')


def _unsafe(text):
    value = _norm(text)
    return bool(re.search(r'ignore.*(?:instruction|system|rules)|bo qua.*(?:huong dan|quy tac|bao mat)|'
                          r'system prompt|developer message|database_url|api key|password|mat khau|access token|'
                          r'secret|private key|tat ca (?:ma )?sinh vien|liet ke.*sinh vien|danh sach sinh vien|all students|list.*student|'
                          r'other student|email|dien thoai|contact|phone', value)
                or re.search(r'__import__|os\.system|subprocess|(?:eval|exec)\s*\(|file://|<script|\.\.[/\\]', text, re.I))


def _safe_source(text):
    return (isinstance(text, str) and bool(text.strip()) and not _unsafe(text)
            and not re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}|https?://|(?<!\d)(?:\+84|0)[\d .()-]{8,}(?!\d)', text, re.I))


def _official(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.hostname == 'fit.neu.edu.vn'
            and parsed.path.startswith('/lecturer/') and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment)


class AdvisorAssistant:
    def __init__(self, profiles, service, *, versions=None):
        self.service = service
        self.versions = copy.deepcopy(versions or {})
        catalog = {row['advisor_id']: row for row in service.advisors}
        self.profiles = {}
        for source in profiles:
            key = source.get('advisor_id')
            if key not in service.advisor_ids or source.get('review_status') != 'approved':
                continue
            if key in self.profiles:
                raise ValueError('duplicate_assistant_profile')
            row = copy.deepcopy(source)
            if (not _official(row.get('source_url', ''))
                    or not re.fullmatch('[a-f0-9]{64}', row.get('source_sha256', ''))
                    or any(row.get(field) != catalog[key].get(field) for field in ('source_sha256', 'source_url', 'advisor_name'))):
                raise ValueError('assistant_profile_source_binding_mismatch')
            if datetime.fromisoformat(row['retrieved_at'].replace('Z', '+00:00')).tzinfo is None:
                raise ValueError('assistant_source_timestamp_required')
            if any(not isinstance(row.get(field, []), list) or any(not isinstance(v, str) for v in row.get(field, []))
                   for field in ('research_topics', 'teaching_topics')):
                raise ValueError('invalid_assistant_profile_field')
            self.profiles[key] = row

    @classmethod
    def from_artifacts(cls, output, service):
        from src.features.rebuild_experiments import _load_snapshot
        from src.data_pipeline.reconcile import _read_bound_phase, _digest
        output = Path(output).resolve()
        _, gold, snapshot = _load_snapshot(output)
        gate, path = _read_bound_phase(output, 3, 'silver/review_records.jsonl')
        if (set(row['advisor_id'] for row in gold) != set(service.advisor_ids)
                or service.versions.get('phase3_run_id') != snapshot['run_id'] or gate['run_id'] != snapshot['run_id']):
            raise ValueError('assistant_approved_snapshot_mismatch')
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        result = cls([row for row in rows if row.get('entity_type') == 'advisors'], service,
                     versions={'phase3_run_id': snapshot['run_id'], 'source_manifest_sha256': snapshot['manifest_sha256'],
                               'silver_sha256': _digest(path), 'gold_advisors_sha256': snapshot['advisors_sha256'],
                               'scope': 'Cached approved public profile evidence; no live web verification.'})
        if set(result.profiles) != set(service.advisor_ids):
            raise ValueError('assistant_approved_profile_coverage_mismatch')
        return result

    def _selection(self, advisor_ids, top_k):
        if type(top_k) is not int or not 1 <= top_k <= 10:
            raise ValueError('assistant_top_k_must_be_1_to_10')
        selected = list(self.profiles) if advisor_ids is None else advisor_ids
        if (not isinstance(selected, list) or any(not isinstance(key, str) or key not in self.profiles for key in selected)
                or len(selected) != len(set(selected))):
            raise ValueError('assistant_unknown_or_duplicate_advisor')
        return selected

    def _citation(self, advisor_id, query='', *, require_concepts=False):
        row = self.profiles[advisor_id]
        catalog = next(item for item in self.service.advisors if item['advisor_id'] == advisor_id)
        confidence = catalog.get('expertise_confidence')
        taxonomy = getattr(self.service, 'taxonomy', {'groups': {}})
        concepts = {(m['group'], m['tag']) for m in normalize_mentions(query, taxonomy)} if require_concepts else set()
        candidates = []
        for field in FIELDS:
            values = row.get(field, '') if field == 'profile_intro' else row.get(field, [])
            values = [values] if isinstance(values, str) else values
            for index, value in enumerate(values):
                if not _safe_source(value):
                    continue
                evidence = next((ev for ev in row.get('evidence', []) if ev.get('field') == field
                                 and ev.get('snippet') == value and ev.get('locator')
                                 and all(ev.get(key) == row.get(key) for key in ('source_url', 'source_sha256', 'retrieved_at'))), None)
                if evidence is None:
                    continue
                mentions = [m for m in normalize_mentions(value, taxonomy) if (m['group'], m['tag']) in concepts]
                if concepts and not mentions:
                    continue
                words = list(re.finditer(r'\S+', value))
                first = next((i for i, word in enumerate(words) if word.end() > mentions[0]['start']), 0) if mentions else 0
                start = words[first].start() if mentions else 0
                end = words[min(len(words), first+20)-1].end()
                snippet = value[start:end]
                overlap = len(set(_norm(query).split()) & set(_norm(value).split()))
                candidates.append((-overlap, FIELDS.index(field), index, {
                    'title': row['advisor_name'], 'source_url': row['source_url'], 'snippet': snippet,
                    'source_sha256': row['source_sha256'], 'retrieved_at': row['retrieved_at'],
                    'locator': evidence['locator'], 'field': field, 'index': index, 'start': start, 'end': end,
                    'attribution': 'research' if field == 'research_topics' else 'teaching' if field == 'teaching_topics' else 'profile_intro',
                    'evidence_confidence': confidence if confidence not in ('', None) else None,
                    'confidence_semantics': 'Approved valid-evidence ratio; not proficiency or supervision probability.',
                    'evidence_policy': 'literal-query-concept/1.0' if concepts else 'source-field-whitelist/1.0',
                    'matched_concepts': [{'group': group, 'tag': tag} for group, tag in sorted(
                        {(m['group'], m['tag']) for m in mentions if m['start'] >= start and m['end'] <= end})],
                    'scope': 'Cached public source; not proficiency, participation or outcome evidence.'}))
        return sorted(candidates, key=lambda item: item[:3])[0][3] if candidates else None

    def get_advisor_evidence(self, advisor_id):
        if not isinstance(advisor_id, str) or advisor_id not in self.profiles:
            raise ValueError('assistant_unknown_advisor')
        citation = self._citation(advisor_id)
        return {'advisor_id': advisor_id, 'citations': [citation] if citation else [], 'versions': self.versions}

    def match_topic_to_advisors(self, topic, advisor_ids=None, top_k=5):
        selected = self._selection(advisor_ids, top_k)
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 4000:
            raise ValueError('assistant_question_required_max_4000')
        if not selected or _unsafe(topic):
            return []
        expansion = self.expand_query(topic)
        advisors = [row for row in self.service.advisors if row['advisor_id'] in selected]
        scored = self.service.pipeline.transform_score([{'thesis_title': expansion['expanded_query']}], advisors)
        rows = []
        for j, advisor in enumerate(advisors):
            score = float(scored['scores']['E4'][0, j])
            citation = self._citation(advisor['advisor_id'], topic, require_concepts=True)
            if scored['available']['E4'][0, j] and math.isfinite(score) and 0 < score <= 1 and citation:
                rows.append({'advisor_id': advisor['advisor_id'], 'advisor_name': advisor['advisor_name'],
                             'score': score, 'citation': citation})
        return sorted(rows, key=lambda row: (-row['score'], row['advisor_id']))[:top_k]

    def expand_query(self, topic):
        """Only aliases of literally matched approved concepts; no hierarchy or inferred tags."""
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 4000:
            raise ValueError('assistant_question_required_max_4000')
        taxonomy = getattr(self.service, 'taxonomy', {'groups': {}})
        aliases, concepts = [], []
        if not _unsafe(topic):
            for match in normalize_mentions(topic, taxonomy):
                concept = (match['group'], match['tag'])
                if concept in concepts:
                    continue
                concepts.append(concept)
                definition = taxonomy['groups'][concept[0]][concept[1]]
                for alias in definition.get('aliases', []) + definition.get('case_sensitive_aliases', []):
                    if (alias.casefold() not in {item.casefold() for item in aliases}
                            and not re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)', topic, re.I)):
                        aliases.append(alias)
        return {'original_query': topic, 'expanded_query': ' '.join([topic, *aliases]),
                'expanded_aliases': aliases, 'query_expansion_policy': 'approved-literal-concept-aliases/1.0',
                'taxonomy_version': taxonomy.get('taxonomy_version'),
                'matched_concepts': [{'group': group, 'tag': tag} for group, tag in concepts]}

    def search_advisor_profiles(self, query, advisor_ids=None, top_k=5):
        return self.match_topic_to_advisors(query, advisor_ids, top_k)

    def explain_assignment(self, cohort_id, student_id, advisor_id, *, scope='local'):
        if not isinstance(advisor_id, str) or advisor_id not in self.profiles:
            raise ValueError('assistant_unknown_advisor')
        students = self.service.get_students(cohort_id, scope=scope)
        matched = [row for row in students if row['student_id'] == student_id]
        if len(matched) != 1:
            raise ValueError('assistant_authorized_student_required')
        advisor = next(row for row in self.service.advisors if row['advisor_id'] == advisor_id)
        return {'student_id': student_id, 'advisor_id': advisor_id, 'assignment_verified': False,
                'explanation': self.service.pipeline.explain_pair(matched[0], advisor),
                'citations': [citation] if (citation := self._citation(advisor_id, matched[0].get('thesis_title', ''))) else []}

    def _response(self, answer, intent, *, citations=None, **extra):
        return {'answer': answer, 'intent': intent, 'mode': 'deterministic_read_only', 'disclosure': DISCLOSURE,
                'citations': citations or [], 'versions': self.versions, 'rankings': [], **extra}

    def answer(self, question, *, advisor_ids=None, top_k=5, cohort_id=None, scope='local'):
        selected = self._selection(advisor_ids, top_k)
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError('assistant_question_required_max_4000')
        normalized = _norm(question)
        if _unsafe(question):
            return self._response('Tôi không cung cấp dữ liệu sinh viên hàng loạt, liên hệ, bí mật hoặc thực thi chỉ dẫn trong câu hỏi/nguồn.', 'privacy_refusal')
        if re.search(r'capacity|quota|chi tieu|con nhan|con trong|bao nhieu (?:cho|suat|sinh vien)|do chinh xac|t[yi] le (?:dung|thanh cong)|hai long|ket qua huong dan|cam ket|guarantee', normalized):
            return self._response('Hồ sơ công khai không xác nhận capacity, việc nhận hướng dẫn hoặc kết quả thực tế. Quota trên giao diện là chính sách chia đều do điều phối xác nhận; compatibility không phải accuracy.', 'unknown_operational_facts')
        names = []
        for key in selected:
            full = _norm(self.profiles[key]['advisor_name'])
            short = re.sub(r'^(?:(?:pgs|gs|ts|ths|th s|cn)\s+)+', '', full)
            if _contains(normalized, full) or _contains(normalized, short):
                names.append(key)
        explaining = bool(re.search(r'\b(?:vi sao|tai sao|explain|why)\b', normalized))
        if explaining:
            if not cohort_id or len(names) != 1:
                return self._response('Cần cohort được phép và chỉ rõ một sinh viên, một giảng viên để giải thích cặp; tôi không tra sinh viên toàn cục.', 'privacy_refusal')
            try:
                students = self.service.get_students(cohort_id, scope=scope)
                matches = [row for row in students if _contains(normalized, _norm(row['student_id']))
                           or row.get('student_name') and _contains(normalized, _norm(row['student_name']))]
                if len(matches) != 1:
                    raise ValueError('explicit_single_student_required')
                result = self.explain_assignment(cohort_id, matches[0]['student_id'], names[0], scope=scope)
            except ValueError:
                return self._response('Không có quyền hoặc chưa xác định được duy nhất sinh viên trong cohort này.', 'privacy_refusal')
            return self._response('Đây là giải thích độ phù hợp của cặp theo encoder cố định; không xác nhận đã phân công hoặc được nhận hướng dẫn.',
                                  'pair_explanation', **result)
        if names:
            citations = [c for key in names[:top_k] if (c := self._citation(key, question))]
            text = ('Bằng chứng dưới đây lấy từ hồ sơ công khai đã duyệt; nhãn research/teaching phân biệt nghiên cứu với giảng dạy.'
                    if citations else 'Chưa có bằng chứng trích dẫn hợp lệ trong các trường được phép của hồ sơ này; tôi không suy đoán dữ liệu còn thiếu.')
            return self._response(text,
                                  'advisor_profile', citations=citations)
        ranked = self.match_topic_to_advisors(question, selected, top_k)
        answer = ('Các hồ sơ dưới đây được xếp theo compatibility từ matching function cố định, chỉ phản ánh liên hệ chủ đề; không áp dụng quota và không phải xác suất hướng dẫn thành công.'
                  if ranked else 'Chưa có bằng chứng hoặc overlap phù hợp trong các hồ sơ đã chọn. Hãy mô tả đề tài đầy đủ hơn bằng từ ngữ của hồ sơ; tôi không suy đoán dữ liệu còn thiếu.')
        return self._response(answer, 'topic_match', citations=[row['citation'] for row in ranked],
                              rankings=[{key: value for key, value in row.items() if key != 'citation'} for row in ranked],
                              quota_applied=False, **self.expand_query(question))
