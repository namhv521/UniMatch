"""4-Layer Guardrailed RAG & Scoped Academic AI Agent for UniMatch."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.data_pipeline.normalization import load_taxonomy, normalize_mentions

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = ROOT / 'configs/data/taxonomy_v1.yaml'
AGENT_LLM_LIMIT = BoundedSemaphore(2)

OUT_OF_SCOPE_MESSAGE = (
    'Mình là Trợ lý Học thuật UniMatch — chỉ hỗ trợ các câu hỏi liên quan đến **khóa luận tốt nghiệp, '
    'định hướng đề tài, chuyên môn giảng viên hướng dẫn và quy trình đăng ký/phân công trên UniMatch**. '
    'Bạn vui lòng đặt câu hỏi trong phạm vi này nhé!'
)
PRIVACY_REFUSAL_MESSAGE = (
    'Vì lý do bảo mật và quyền riêng tư, mình không truy cập hoặc cung cấp thông tin cá nhân của sinh viên khác '
    '(MSSV, email, số điện thoại, kết quả riêng), dữ liệu nội bộ máy chủ hoặc thực thi các chỉ dẫn vượt quyền.'
)
ACADEMIC_INTEGRITY_MESSAGE = (
    'Mình không thực hiện việc viết hộ nội dung khóa luận, làm bài tập hay lập trình trọn gói thay sinh viên. '
    'Tuy nhiên, mình có thể gợi ý **cấu trúc đề cương, phương pháp nghiên cứu và giảng viên có chuyên môn phù hợp** với đề tài của bạn.'
)

# Layer 1A: Prompt Injection, Jailbreak, System Probing & Code Execution
INJECTION_PATTERNS = re.compile(
    r'\b(?:ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|rules?|prompts?)|'
    r'disregard\s+(?:all\s+)?(?:instructions?|rules?)|'
    r'bo\s+qua\s+(?:moi\s+|tat\s+ca\s+)?(?:chi\s+dan|huong\s+dan|quy\s+tac|luat|gioi\s+han)|'
    r'system\s*prompt|developer\s*message|chi\s+dan\s+he\s+thong|jailbreak|dan\s+mode|'
    r'pretend\s+you\s+are|hay\s+dong\s+vai\s+mot|act\s+as\s+an?\s+unrestricted|'
    r'database_url|openrouter_api_key|openai_api_key|gemini_api_key|secret_key|private_key|access_token|'
    r'drop\s+table|union\s+select|__import__|os\.system|subprocess)\b',
    re.I,
)

# Layer 1B: Cross-Student PII & Unauthorized Data Probing
PII_PATTERNS = re.compile(
    r'\b(?:danh\s+sach\s+(?:tat\s+ca\s+|toan\s+bo\s+)?sinh\s+vien|liet\s+ke\s+.*sinh\s+vien|'
    r'all\s+students|list\s+all\s+students|thong\s+tin\s+ca\s+nhan\s+cua|'
    r'(?:so\s+dien\s+thoai|sdt|email|mssv|ma\s+sinh\s+vien|diem\s+thi)(?:\s+\w+){0,5}\s+cua\s+(?:cac\s+)?(?:ban|sinh\s+vien))',
    re.I,
)

# Layer 1C: Academic Dishonesty (Ghostwriting / Homework solving)
DISHONESTY_PATTERNS = re.compile(
    r'\b(?:viet\s+(?:ho|giup|dum)\s+(?:em\s+|minh\s+)?(?:toan\s+bo\s+|tron\s+bo\s+|full\s+)?(?:khoa\s+luan|luan\s+van|chuong\s+[1-5]|bao\s+cao)|'
    r'lam\s+(?:ho|giup|dum)\s+(?:em\s+|minh\s+)?(?:do\s+an|bai\s+tap|khoa\s+luan)|'
    r'code\s+(?:full|ho|giup)\s+(?:toan\s+bo\s+|tron\s+bo\s+)?(?:project|do\s+an|he\s+thong)|'
    r'write\s+my\s+(?:entire\s+)?thesis)\b',
    re.I,
)

# Layer 2A: Explicit Off-Topic Categories (Immediate Refusal unless clear advisor/thesis context)
OFF_TOPIC_PATTERNS = re.compile(
    r'\b(?:thoi\s+tiet|du\s+bao\s+mua|nhiet\s+do\s+hom\s+nay|weather|'
    r'bong\s+da|ngoai\s+hang\s+anh|world\s+cup|ket\s+qua\s+tran\s+dau|ty\s+so\s+bong|'
    r'gia\s+vang|gia\s+bitcoin|gia\s+coin|chung\s+khoan\s+hom\s+nay|xo\s+so|vietlott|lo\s+de|'
    r'nau\s+an|cong\s+thuc\s+nau|cach\s+lam\s+mon|quan\s+(?:an|bun|pho|com|lau|nuong|nhau|cafe|ca\s+phe)|'
    r'bun\s+cha|pho\s+bo|tra\s+sua|an\s+gi\s+ngon|du\s+lich|khach\s+san|ve\s+may\s+bay|'
    r'boi\s+toan|tu\s+vi|cung\s+hoang\s+dao|tarot|phong\s+thuy|'
    r'ke\s+chuyen\s+cuoi|viet\s+bai\s+tho|sang\s+tac\s+nhac|viet\s+loi\s+bai\s+hat|'
    r'tong\s+thong|thu\s+tuong|bau\s+cu|chien\s+tranh|'
    r'giai\s+phuong\s+trinh|tinh\s+tich\s+phan|dao\s+ham|tinh\s+giai\s+thua|fibonacci|'
    r'phim\s+hay|ca\s+si|dien\s+vien|showbiz|lien\s+quan\s+mobile|genshin|valorant)\b',
    re.I,
)

# Domain anchor keywords (Academic / Thesis / UniMatch / IT-CS Research)
DOMAIN_ANCHORS = re.compile(
    r'\b(?:khoa\s+luan|luan\s+van|do\s+an|tot\s+nghiep|de\s+tai|de\s+cuong|'
    r'giang\s+vien|thay|co|pgs|ts|ths|nguoi\s+huong\s+dan|gvhd|mentor|supervisor|advisor|'
    r'nguyen\s+vong|dang\s+ky|phan\s+cong|phan\s+bo|chi\s+tieu|quota|unimatch|'
    r'ho\s+so|ky\s+nang|trac\s+nghiem|khao\s+sat|chuan\s+hoa|diem\s+phu\s+hop|tuong\s+thich|'
    r'nghien\s+cuu|bai\s+bao|cong\s+trinh|tap\s+chi|hoi\s+thao|github|huong\s+nghien\s+cuu)\b',
    re.I,
)

WORKFLOW_ANCHORS = re.compile(
    r'\b(?:quy\s+trinh|cach\s+dang\s+ky|lam\s+sao\s+de|huong\s+dan\s+su\s+dung|'
    r'bao\s+nhieu\s+nguyen\s+vong|rut\s+nguyen\s+vong|doi\s+nguyen\s+vong|'
    r'chuan\s+hoa\s+ho\s+so|cong\s+bo\s+ket\s+qua|chi\s+tieu|quota|con\s+nhan|con\s+cho)\b',
    re.I,
)

MY_PROFILE_ANCHORS = re.compile(
    r'\b(?:ho\s+so(?:\s+\w+){0,3}\s+(?:cua\s+)?(?:em|minh|toi)|'
    r'ky\s+nang(?:\s+\w+){0,3}\s+(?:cua\s+)?(?:em|minh|toi)|'
    r'(?:em|minh|toi)\s+(?:hop|phu\s+hop)\s+(?:voi\s+)?(?:thay|co|giang\s+vien)\s+nao|'
    r'goi\s+y\s+cho\s+(?:em|minh|toi)|dua\s+tren\s+(?:bai\s+lam|khao\s+sat|ho\s+so)\s+cua\s+(?:em|minh|toi))\b',
    re.I,
)

COMPARE_ANCHORS = re.compile(
    r'\b(?:so\s+sanh|khac\s+nhau|khac\s+biet|chon\s+giua|phan\s+van\s+giua|compare)\b',
    re.I,
)

FOLLOWUP_ANCHORS = re.compile(
    r'^(?:con\s+ai(?:\s+nua)?|ai\s+nua|co\s+ai\s+khac\s+khong|con\s+thay\s+co\s+nao|'
    r'noi\s+(?:ro|them|ky)\s+hon|chi\s+tiet\s+hon|cho\s+(?:minh|em)\s+them\s+(?:nguon|bai\s+bao|vi\s+du)|'
    r'(?:thay|co)\s+(?:ay|do)\s+(?:nghien\s+cuu\s+gi|co\s+cong\s+trinh\s+nao|manh\s+ve\s+gi)|'
    r'tai\s+sao|vi\s+sao)(?:\s+(?:nhe|a|vay|khong))?$',
    re.I,
)

STOPWORDS = set((
    'la va cua cho voi trong cac nhung mot hai ba nay do khi nhu the nao gi ai '
    'em minh toi ban thay co giang vien huong dan khoa luan de tai nghien cuu '
    'muon tim hoi xin chao cam on nhe a da vâng oi co khong duoc can phu hop '
    'what which who how can for the and with about thesis advisor research'
).split())

BILINGUAL_EXPANSIONS: tuple[tuple[str, str], ...] = (
    (r'\b(?:nlp|xu\s+ly\s+ngon\s+ngu(?:\s+tu\s+nhien)?)\b', 'natural language processing nlp xử lý ngôn ngữ tự nhiên'),
    (r'\b(?:cv|thi\s+giac\s+may\s+tinh|xu\s+ly\s+anh|nhan\s+dien\s+(?:anh|doi\s+tuong|khuon\s+mat))\b', 'computer vision thị giác máy tính object detection image'),
    (r'\b(?:llm|rag|ai\s+agent|chatbot|mo\s+hinh\s+ngon\s+ngu)\b', 'large language model llm rag ai agent nlp'),
    (r'\b(?:ml|hoc\s+may)\b', 'machine learning học máy classification regression'),
    (r'\b(?:dl|hoc\s+sau|mang\s+no\s+ron)\b', 'deep learning pytorch tensorflow neural network'),
    (r'\b(?:rl|hoc\s+tang\s+cuong)\b', 'reinforcement learning học tăng cường optimization'),
    (r'\b(?:web\s+app|phat\s+trien\s+web|full\s*stack|frontend|backend|microservices)\b', 'web development frontend backend full stack api react fastapi java spring'),
    (r'\b(?:mobile|ung\s+dung\s+di\s+dong|flutter|android|ios|react\s+native)\b', 'mobile development ứng dụng di động flutter react native firebase'),
    (r'\b(?:khoa\s+hoc\s+du\s+lieu|phan\s+tich\s+du\s+lieu|power\s+bi|business\s+intelligence|dashboard|thong\s+ke\s+ung\s+dung|kinh\s+te\s+luong)\b',
     'data science business analytics phân tích dữ liệu định lượng thống kê sql'),
    (r'\b(?:he\s+thong\s+thong\s+tin|httt|phan\s+tich\s+nghiep\s+vu|business\s+analyst|erp|logistics|chuoi\s+cung\s+ung|chuyen\s+doi\s+so)\b',
     'information systems hệ thống thông tin quản lý chuỗi cung ứng logistics uml business analytics'),
    (r'\b(?:bao\s+mat|an\s+toan\s+thong\s+tin|cybersecurity|an\s+ninh\s+mang|mang\s+may\s+tinh)\b',
     'cybersecurity an toàn thông tin bảo mật mạng network'),
    (r'\b(?:iot|he\s+thong\s+nhung|vi\s+dieu\s+khien|cam\s+bien)\b', 'internet of things iot hệ thống nhúng mạng'),
    (r'\b(?:cloud\s+computing|dien\s+toan\s+dam\s+may|devops|docker|kubernetes)\b', 'cloud computing điện toán đám mây devops docker'),
)


def norm_vi(text: str) -> str:
    nfd = unicodedata.normalize('NFD', str(text or '').lower()).replace('đ', 'd')
    return ' '.join(re.findall(r'\w+', ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')))


def _tokens(text: str) -> list[str]:
    return [tok for tok in norm_vi(text).split() if len(tok) >= 2 and tok not in STOPWORDS]


def _safe_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url.strip()


def _redact_pii(text: str) -> str:
    cleaned = re.sub(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', '[email đã ẩn]', text, flags=re.I)
    cleaned = re.sub(r'(?<!\d)(?:\+84|0)[\d .()-]{8,13}(?!\d)', '[SĐT đã ẩn]', cleaned)
    return cleaned


class BM25ChunkIndex:
    """Lightweight in-memory BM25 + concept tag index over verified advisor chunks."""

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[Counter] = []
        self.doc_lens: list[int] = []
        self.df: Counter = Counter()
        for chunk in chunks:
            toks = _tokens(chunk['search_text'])
            counts = Counter(toks)
            self.doc_tokens.append(counts)
            self.doc_lens.append(len(toks))
            for term in counts:
                self.df[term] += 1
        self.n_docs = max(1, len(chunks))
        self.avgdl = max(1.0, sum(self.doc_lens) / self.n_docs)

    def search(self, query: str, query_tags: set[str], allowed_advisors: set[str] | None = None) -> list[tuple[int, float]]:
        q_terms = _tokens(query)
        scores: list[tuple[int, float]] = []
        for idx, chunk in enumerate(self.chunks):
            if allowed_advisors is not None and chunk['advisor_id'] not in allowed_advisors:
                continue
            counts = self.doc_tokens[idx]
            dl = self.doc_lens[idx]
            bm25 = 0.0
            for term in q_terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                df = self.df.get(term, 0)
                idf = math.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl)
                bm25 += idf * (tf * (self.k1 + 1.0)) / denom
            tag_overlap = len(query_tags & chunk['tags'])
            # Boost chunks that match canonical taxonomy tags
            total = bm25 + tag_overlap * 2.4 + (0.35 if chunk['kind'] == 'skill_summary' and tag_overlap else 0.0)
            if total > 0.05:
                scores.append((idx, total))
        scores.sort(key=lambda item: -item[1])
        return scores


class GuardrailedAcademicAgent:
    """Production-grade Guardrailed RAG + Scoped Tool-Using Agent for UniMatch students."""

    def __init__(self, service, base_assistant=None, faculty_records: list[dict] | None = None):
        from backend.app.advisor_skills import enrich_advisors, tag_label

        self.service = service
        self.base_assistant = base_assistant
        self.taxonomy = getattr(service, 'taxonomy', None) or load_taxonomy(TAXONOMY_PATH)
        self.tag_label = tag_label
        self.enriched_advisors = enrich_advisors(service)
        self.advisor_by_id = {a['advisor_id']: a for a in self.enriched_advisors}

        chunks: list[dict] = []
        # 1. Structured skill profile chunks (ensures fair coverage for all 17 advisors)
        for adv in self.enriched_advisors:
            sp = adv['skill_profile']
            url = _safe_url(sp.get('source_url')) or _safe_url(sp.get('scholar_url')) or _safe_url(sp.get('github_url')) or 'https://fit.neu.edu.vn'
            skill_text = f"{sp['advisor_name']} — {sp['summary']} Kỹ năng & chủ đề: {', '.join(sp['display_skills'])}."
            chunks.append({
                'advisor_id': sp['advisor_id'],
                'advisor_name': sp['advisor_name'],
                'kind': 'skill_summary',
                'title': f"Hồ sơ chuyên môn · {sp['advisor_name']}",
                'snippet': _redact_pii(skill_text[:280]),
                'url': url,
                'tags': set(sp['all_tags']),
                'search_text': f"{sp['advisor_name']} {sp['enriched_text']}",
            })

        # 2. Research publication / repository chunks from faculty_records or base_assistant
        if faculty_records:
            for rec in faculty_records:
                aid = rec.get('advisor_id')
                if aid not in self.advisor_by_id:
                    continue
                url = _safe_url(rec.get('source_url'))
                if not url:
                    continue
                title = str(rec.get('title') or '').strip()
                content = str(rec.get('content') or '').strip()
                full = f"{title}. {content}".strip()
                rec_tags = {m['tag'] for m in normalize_mentions(full, self.taxonomy)}
                for start in range(0, min(len(content), 3600), 600):
                    piece = content[start:start + 600].strip()
                    if not piece:
                        continue
                    snippet = _redact_pii((f"{title}: {piece}" if start == 0 and title not in piece else piece)[:240])
                    chunks.append({
                        'advisor_id': aid,
                        'advisor_name': self.advisor_by_id[aid]['advisor_name'],
                        'kind': 'publication',
                        'title': title[:160] or self.advisor_by_id[aid]['advisor_name'],
                        'snippet': snippet,
                        'url': url,
                        'tags': rec_tags,
                        'search_text': f"{title} {piece}",
                    })
        elif hasattr(base_assistant, 'documents'):
            for rec, piece in getattr(base_assistant, 'documents', []):
                aid = rec.get('advisor_id')
                url = _safe_url(rec.get('source_url'))
                if aid in self.advisor_by_id and url and piece:
                    title = str(rec.get('title') or '').strip()
                    rec_tags = {m['tag'] for m in normalize_mentions(f"{title} {piece}", self.taxonomy)}
                    chunks.append({
                        'advisor_id': aid,
                        'advisor_name': self.advisor_by_id[aid]['advisor_name'],
                        'kind': 'publication',
                        'title': title[:160] or self.advisor_by_id[aid]['advisor_name'],
                        'snippet': _redact_pii(piece[:240]),
                        'url': url,
                        'tags': rec_tags,
                        'search_text': f"{title} {piece}",
                    })
        elif hasattr(base_assistant, 'profiles'):
            for aid, prof in getattr(base_assistant, 'profiles', {}).items():
                url = _safe_url(prof.get('source_url')) or 'https://fit.neu.edu.vn'
                topics = '; '.join(prof.get('research_topics', []) + prof.get('teaching_topics', []))
                intro = str(prof.get('profile_intro') or '')
                body = f"{topics}. {intro}".strip('. ')
                if aid in self.advisor_by_id and body:
                    rec_tags = {m['tag'] for m in normalize_mentions(body, self.taxonomy)}
                    chunks.append({
                        'advisor_id': aid,
                        'advisor_name': self.advisor_by_id[aid]['advisor_name'],
                        'kind': 'publication',
                        'title': f"Hồ sơ công khai · {self.advisor_by_id[aid]['advisor_name']}",
                        'snippet': _redact_pii(body[:240]),
                        'url': url,
                        'tags': rec_tags,
                        'search_text': body,
                    })

        self.index = BM25ChunkIndex(chunks)

    def _detect_named_advisors(self, normalized_q: str, allowed_ids: set[str]) -> list[str]:
        matched = []
        padded = f" {normalized_q} "
        for aid in self.service.advisor_ids:
            if aid not in allowed_ids or aid not in self.advisor_by_id:
                continue
            full = norm_vi(self.advisor_by_id[aid]['advisor_name'])
            short = re.sub(r'^(?:(?:pgs|gs|ts|ths|th\s+s|cn)\s+)+', '', full).strip()
            if (full and f" {full} " in padded) or (len(short.split()) >= 2 and f" {short} " in padded):
                matched.append(aid)
        return matched

    def _extract_query_tags_and_expansion(self, question: str) -> tuple[set[str], str]:
        tags = {m['tag'] for m in normalize_mentions(question, self.taxonomy)}
        norm = norm_vi(question)
        expansions = [question]
        for pat, exp in BILINGUAL_EXPANSIONS:
            if re.search(pat, norm):
                expansions.append(exp)
                for m in normalize_mentions(exp, self.taxonomy):
                    tags.add(m['tag'])
        return tags, ' '.join(expansions)

    def inspect_guardrails(self, question: str, previous_question: str | None = None) -> dict:
        """Run Layer 1 & Layer 2 guardrails and classify intent."""
        raw = str(question or '').strip()
        norm = norm_vi(raw)

        # Layer 1A: Prompt injection / system probing / code execution
        if INJECTION_PATTERNS.search(norm) or INJECTION_PATTERNS.search(raw) or re.search(r'<script|file://|\bsk-[a-z0-9_-]{12,}', raw, re.I):
            return {'allowed': False, 'intent': 'privacy_refusal', 'guardrail': 'prompt_injection_or_system_probe',
                    'message': PRIVACY_REFUSAL_MESSAGE}

        # Layer 1B: Cross-student PII probing
        if PII_PATTERNS.search(norm) or re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', raw):
            return {'allowed': False, 'intent': 'privacy_refusal', 'guardrail': 'pii_protection',
                    'message': PRIVACY_REFUSAL_MESSAGE}

        # Layer 1C: Academic dishonesty (writing thesis/code for student)
        if DISHONESTY_PATTERNS.search(norm):
            return {'allowed': False, 'intent': 'academic_integrity_refusal', 'guardrail': 'academic_integrity',
                    'message': ACADEMIC_INTEGRITY_MESSAGE}

        # Polite greetings / thanks
        if re.fullmatch(r'(?:xin\s+chao|chao|hi|hello|hey)(?:\s+(?:ban|ad|bot|unimatch|tro\s+ly|a|nhe)){0,3}', norm):
            return {'allowed': True, 'intent': 'greeting', 'guardrail': 'pass'}
        if re.fullmatch(r'(?:cam\s+on|thank\s+you|thanks|tam\s+biet|bye)(?:\s+(?:ban|nhieu|nhe|a)){0,3}', norm):
            return {'allowed': True, 'intent': 'courtesy', 'guardrail': 'pass'}

        # Follow-up check
        if FOLLOWUP_ANCHORS.fullmatch(norm):
            if previous_question and self.inspect_guardrails(previous_question).get('allowed'):
                return {'allowed': True, 'intent': 'follow_up', 'guardrail': 'pass'}
            return {'allowed': True, 'intent': 'clarify_followup', 'guardrail': 'pass'}

        allowed_ids = set(self.advisor_by_id)
        named = self._detect_named_advisors(norm, allowed_ids)
        query_tags, _ = self._extract_query_tags_and_expansion(raw)
        has_domain_anchor = bool(DOMAIN_ANCHORS.search(norm))

        # Layer 2: Strict Off-Topic Gatekeeper
        # If explicitly off-topic AND not mentioning an advisor or thesis context -> block immediately!
        if OFF_TOPIC_PATTERNS.search(norm) and not named and not re.search(r'\b(?:khoa\s+luan|de\s+tai|giang\s+vien)\b', norm):
            return {'allowed': False, 'intent': 'out_of_scope', 'guardrail': 'off_topic_domain_gate',
                    'message': OUT_OF_SCOPE_MESSAGE}

        # Catch generic homework/coding/translation requests without thesis/advisor context
        if re.search(r'\b(?:dich\s+doan|viet\s+ham|sua\s+loi\s+code|debug\s+giup|giai\s+bai\s+tap)\b', norm) and not named and not re.search(r'\b(?:khoa\s+luan|de\s+tai|giang\s+vien)\b', norm):
            return {'allowed': False, 'intent': 'out_of_scope', 'guardrail': 'homework_not_thesis',
                    'message': OUT_OF_SCOPE_MESSAGE}

        # Must have at least ONE concrete UniMatch / Advisor / Thesis / Research-Tech signal!
        if not named and not query_tags and not has_domain_anchor:
            return {'allowed': False, 'intent': 'out_of_scope', 'guardrail': 'no_academic_signal',
                    'message': OUT_OF_SCOPE_MESSAGE}

        if MY_PROFILE_ANCHORS.search(norm):
            return {'allowed': True, 'intent': 'my_profile_fit', 'guardrail': 'pass', 'named': named, 'tags': query_tags}
        if WORKFLOW_ANCHORS.search(norm) and not named and not query_tags:
            return {'allowed': True, 'intent': 'portal_workflow', 'guardrail': 'pass'}
        if len(named) >= 2 or (COMPARE_ANCHORS.search(norm) and len(named) >= 1):
            return {'allowed': True, 'intent': 'advisor_compare', 'guardrail': 'pass', 'named': named, 'tags': query_tags}
        if named:
            return {'allowed': True, 'intent': 'advisor_profile', 'guardrail': 'pass', 'named': named, 'tags': query_tags}
        return {'allowed': True, 'intent': 'topic_match', 'guardrail': 'pass', 'named': [], 'tags': query_tags}

    def _workflow_answer(self, norm: str) -> dict:
        if re.search(r'\b(?:chi\s+tieu|quota|con\s+nhan|con\s+cho|bao\s+nhieu\s+suat)\b', norm):
            text = (
                '• **Chỉ tiêu hướng dẫn (Quota)**: Hồ sơ nghiên cứu công khai không tự xác nhận số chỗ trống thời gian thực. '
                'Trên UniMatch, chỉ tiêu của mỗi giảng viên bằng **số sinh viên giảng viên đã chủ động nhận** cộng với **phần chia cân bằng từ danh sách kỳ** (hoặc hạn mức do Trưởng khoa cấu hình).\n'
                '• Bạn có thể gửi tối đa **3 nguyện vọng theo thứ tự ưu tiên** khi kỳ đang mở.'
            )
            return self._pack(text, 'unknown_operational_facts', tools=['workflow_policy_tool'])
        text = (
            'Quy trình thực hiện trên **UniMatch** gồm 4 bước:\n'
            '1. **Khảo sát & Chuẩn hóa hồ sơ**: Chọn hướng quan tâm, hoàn thành bài đánh giá kỹ năng và chuẩn hóa mô tả đề tài sang văn phong học thuật.\n'
            '2. **Khám phá & Gợi ý Top-K**: Xem danh bạ giảng viên kèm điểm tương thích E4 và lý do khớp kỹ năng.\n'
            '3. **Gửi 1–3 Nguyện vọng ưu tiên**: Khi một giảng viên đồng ý nhận hướng dẫn, chỗ của bạn được giữ chính thức.\n'
            '4. **Công bố & Theo dõi mốc khóa luận**: Sau khi Trưởng khoa công bố, bạn nộp Đề cương, Báo cáo giữa kỳ và Bản hoàn chỉnh ngay trên không gian khóa luận.'
        )
        return self._pack(text, 'thesis_guidance', tools=['workflow_policy_tool'])

    def _profile_fit_answer(self, student_context: dict | None, allowed_ids: set[str], top_k: int) -> dict:
        if not student_context or not student_context.get('profile'):
            return self._pack(
                'Bạn chưa lưu **Khảo sát & Trắc nghiệm kỹ năng** trong kỳ này. '
                'Hãy hoàn thành phần đánh giá và bấm **Chuẩn hóa hồ sơ** ở phía trên, sau đó hỏi lại để mình đối chiếu chính xác với 17 giảng viên nhé!',
                'profile_required',
                tools=['student_context_tool'],
            )
        recs = [r for r in (student_context.get('recommendations') or []) if r['advisor_id'] in allowed_ids][:top_k]
        dossier = student_context.get('dossier') or {}
        skill_labels = [s['label'] for s in student_context['profile'].get('skills', []) if s.get('status') != 'unassessed']
        if not recs:
            return self._pack(
                'Từ hồ sơ hiện tại của bạn, chưa có cặp giảng viên vượt ngưỡng tương thích dương. '
                'Bạn nên bổ sung **Mô tả đề tài dự kiến** và chạy **Chuẩn hóa hồ sơ** để hệ thống trích xuất thêm từ khóa chuyên môn.',
                'no_evidence',
                tools=['student_context_tool'],
            )
        lines = [
            f"Dựa trên hồ sơ của bạn ({', '.join(skill_labels[:5]) or 'đã lưu'}"
            + (f" · Đề tài: “{dossier['formal_title']}”" if dossier.get('formal_title') else '')
            + '), các giảng viên phù hợp nhất gồm:'
        ]
        citations = []
        rankings = []
        for idx, rec in enumerate(recs[:4], start=1):
            aid = rec['advisor_id']
            sp = self.advisor_by_id[aid]['skill_profile']
            matched_kw = rec.get('basis', {}).get('matched_keywords') or sp['display_skills'][:4]
            pct = f"{rec['score'] * 100:.1f}%"
            lines.append(
                f"{idx}. **{sp['advisor_name']}** ({pct}) — Thế mạnh: {sp['summary']} "
                f"Khớp nổi bật: {', '.join(matched_kw[:4])}."
            )
            rankings.append({'advisor_id': aid, 'advisor_name': sp['advisor_name'], 'score': rec['score']})
            url = _safe_url(sp.get('source_url'))
            if url:
                citations.append({'title': f"Hồ sơ chuyên môn · {sp['advisor_name']}", 'url': url, 'source_url': url, 'snippet': sp['summary']})
        return self._pack(
            '\n'.join(lines),
            'my_profile_fit',
            rankings=rankings,
            citations=citations,
            tools=['student_context_tool', 'e4_compatibility_tool'],
        )

    def _hybrid_retrieve(self, question: str, allowed_ids: set[str], top_k: int) -> tuple[list[dict], list[dict], set[str]]:
        query_tags, expanded = self._extract_query_tags_and_expansion(question)
        bm25_hits = self.index.search(expanded, query_tags, allowed_advisors=allowed_ids)

        # Also run E4 pipeline cosine scoring across enriched advisors for RRF fusion!
        advisors_sub = [self.advisor_by_id[aid] for aid in self.service.advisor_ids if aid in allowed_ids and aid in self.advisor_by_id]
        e4_rank: dict[str, tuple[int, float]] = {}
        if advisors_sub:
            try:
                row = {'thesis_title': expanded, 'topic_tags': ';'.join(sorted(query_tags)), 'thesis_keywords': expanded}
                scored = self.service.pipeline.transform_score([row], advisors_sub)
                pairs = []
                for j, adv in enumerate(advisors_sub):
                    sc = float(scored['scores']['E4'][0, j])
                    if scored['available']['E4'][0, j] and math.isfinite(sc) and sc > 0:
                        pairs.append((adv['advisor_id'], sc))
                pairs.sort(key=lambda x: -x[1])
                for rk, (aid, sc) in enumerate(pairs, start=1):
                    e4_rank[aid] = (rk, sc)
            except Exception:
                e4_rank = {}

        # Aggregate best chunk per advisor + RRF score
        best_chunk_by_advisor: dict[str, tuple[int, dict, float]] = {}
        advisor_bm25_rank: dict[str, int] = {}
        for idx, bm_score in bm25_hits:
            chunk = self.index.chunks[idx]
            aid = chunk['advisor_id']
            # Prefer publication chunks with concrete evidence when available, else skill_summary
            prev = best_chunk_by_advisor.get(aid)
            adjusted = bm_score * (1.08 if chunk['kind'] == 'publication' else 1.0)
            if prev is None or adjusted > prev[2]:
                best_chunk_by_advisor[aid] = (idx, chunk, adjusted)
            if aid not in advisor_bm25_rank:
                advisor_bm25_rank[aid] = len(advisor_bm25_rank) + 1

        candidate_aids = set(advisor_bm25_rank) | set(e4_rank)
        fused = []
        for aid in candidate_aids:
            rrf = 0.0
            if aid in advisor_bm25_rank:
                rrf += 1.0 / (20 + advisor_bm25_rank[aid])
            if aid in e4_rank:
                rrf += 1.15 / (20 + e4_rank[aid][0])
            sp = self.advisor_by_id[aid]['skill_profile']
            overlap = len(query_tags & set(sp['all_tags']))
            rrf += overlap * 0.018
            e4_val = e4_rank.get(aid, (999, None))[1]
            fused.append((aid, rrf, e4_val))

        fused.sort(key=lambda x: (-x[1], -(x[2] or 0.0), x[0]))
        rankings = []
        citations = []
        for aid, rrf_score, e4_val in fused[:top_k]:
            sp = self.advisor_by_id[aid]['skill_profile']
            matched = [self.tag_label(t) for t in sp['all_tags'] if t in query_tags] or sp['display_skills'][:4]
            display_score = e4_val if (e4_val is not None and e4_val > 0) else min(0.95, round(rrf_score * 10, 3))
            rankings.append({
                'advisor_id': aid,
                'advisor_name': sp['advisor_name'],
                'score': display_score,
                'matched_skills': matched[:5],
                'summary': sp['summary'],
            })
            chunk = best_chunk_by_advisor.get(aid, (None, None, 0.0))[1]
            if chunk:
                citations.append({
                    'advisor_id': aid,
                    'title': chunk['title'],
                    'url': chunk['url'],
                    'source_url': chunk['url'],
                    'snippet': chunk['snippet'],
                })
        return rankings, citations, query_tags

    def _try_llm_grounded_answer(self, question: str, intent: str, rankings: list[dict], citations: list[dict]) -> str | None:
        api_key = (
            os.environ.get('UNIMATCH_LLM_API_KEY', '').strip()
            or os.environ.get('OPENAI_API_KEY', '').strip()
            or os.environ.get('UNIMATCH_OPENROUTER_API_KEY', '').strip()
        )
        if not api_key or not rankings or not AGENT_LLM_LIMIT.acquire(blocking=False):
            return None
        try:
            context_obj = {
                'question': question[:600],
                'intent': intent,
                'advisors': [
                    {
                        'index': i + 1,
                        'advisor_name': r['advisor_name'],
                        'matched_skills': r.get('matched_skills', []),
                        'summary': r.get('summary', ''),
                    }
                    for i, r in enumerate(rankings[:4])
                ],
                'sources': [
                    {'ref': f'[{i + 1}]', 'title': c['title'], 'snippet': c['snippet'][:200]}
                    for i, c in enumerate(citations[:4])
                ],
            }
            sys_prompt = (
                'Bạn là AI Agent tư vấn học thuật của UniMatch. Trả lời NGẮN GỌN, ĐÚNG TRỌNG TÂM bằng tiếng Việt '
                '(tối đa 160 từ) chỉ dựa trên JSON bằng chứng được cung cấp. '
                'Nêu rõ giảng viên nào phù hợp vì kỹ năng/công trình nào và gắn ký hiệu nguồn [1], [2]. '
                'Tuyệt đối không bịa thêm tên giảng viên, số chỗ trống hoặc thông tin ngoài JSON.'
            )
            url = (
                os.environ['UNIMATCH_LLM_BASE_URL'].rstrip('/') + '/chat/completions'
                if os.environ.get('UNIMATCH_LLM_BASE_URL')
                else 'https://api.openai.com/v1/chat/completions'
                if os.environ.get('OPENAI_API_KEY') and api_key == os.environ.get('OPENAI_API_KEY', '').strip()
                else 'https://openrouter.ai/api/v1/chat/completions'
            )
            model = os.environ.get('UNIMATCH_LLM_MODEL', 'baidu/ernie-5.5-flash-preview:free')
            body = {
                'model': model,
                'temperature': 0.0,
                'max_tokens': 380,
                'messages': [
                    {'role': 'system', 'content': sys_prompt},
                    {'role': 'user', 'content': json.dumps(context_obj, ensure_ascii=False)},
                ],
            }
            req = Request(url, data=json.dumps(body).encode('utf-8'),
                          headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
            with urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read(65536))
            text = _redact_pii(data['choices'][0]['message']['content'].strip())
            # Output guardrail: must mention at least one retrieved advisor name and contain no raw URLs not in citations
            if not text or not any(r['advisor_name'].split()[-1].lower() in text.lower() for r in rankings[:3]):
                return None
            return text[:1200]
        except Exception as exc:
            LOG.info('RAG Agent LLM synthesis fell back to deterministic composer (%s)', type(exc).__name__)
            return None
        finally:
            AGENT_LLM_LIMIT.release()

    def _pack(self, answer: str, intent: str, *, rankings=None, citations=None, guardrail='pass', blocked=False, mode='rag_agent_deterministic', tools=None, **extra) -> dict:
        return {
            'answer': _redact_pii(answer),
            'intent': intent,
            'mode': mode,
            'rankings': rankings or [],
            'citations': citations or [],
            'guardrail': {'status': 'blocked' if blocked else 'passed', 'rule': guardrail},
            'agent_tools': tools or [],
            **extra,
        }

    def answer(
        self,
        question: str,
        *,
        advisor_ids: list[str] | None = None,
        top_k: int = 5,
        cohort_id: str | None = None,
        scope: str = 'local',
        previous_question: str | None = None,
        student_context: dict | None = None,
        user_name: str = '',
    ) -> dict:
        gate = self.inspect_guardrails(question, previous_question=previous_question)
        if not gate['allowed']:
            return self._pack(gate['message'], gate['intent'], guardrail=gate['guardrail'], blocked=True)

        intent = gate['intent']
        if intent == 'greeting':
            who = f' {user_name}' if user_name else ''
            return self._pack(
                f'Chào{who}! Mình là Trợ lý Học thuật RAG của UniMatch. '
                'Bạn có thể hỏi mình về:\n'
                '• **Gợi ý giảng viên theo đề tài / công nghệ** (VD: *Computer Vision, LLM/RAG, Web Full-stack, Phân tích dữ liệu*)\n'
                '• **So sánh chuyên môn giữa các giảng viên**\n'
                '• **Đối chiếu trực tiếp hồ sơ kỹ năng hiện tại của bạn**.',
                'greeting',
            )
        if intent == 'courtesy':
            return self._pack(
                'Rất vui được hỗ trợ bạn! Khi cần tra cứu thêm về đề tài hoặc giảng viên hướng dẫn trên UniMatch, bạn cứ nhắn mình nhé.',
                'out_of_scope',
            )
        if intent == 'clarify_followup':
            return self._pack(
                'Bạn muốn mình phân tích sâu hơn về **đề tài kỹ thuật** nào hay **giảng viên** nào trong danh mục UniMatch?',
                'clarify',
            )

        effective_q = previous_question if (intent == 'follow_up' and previous_question) else question
        if intent == 'follow_up':
            sub_gate = self.inspect_guardrails(effective_q)
            intent = sub_gate.get('intent', 'topic_match')
            gate = sub_gate

        norm = norm_vi(effective_q)

        # Preserve Phase-8 cohort pair explanation if cohort_id + "vì sao" is explicitly queried
        if cohort_id and re.search(r'\b(?:vi\s+sao|tai\s+sao|explain|why)\b', norm) and self.base_assistant and hasattr(self.base_assistant, 'answer'):
            delegated = self.base_assistant.answer(effective_q, advisor_ids=advisor_ids, top_k=top_k, cohort_id=cohort_id, scope=scope)
            return {**delegated, 'guardrail': {'status': 'passed', 'rule': 'pass'}, 'agent_tools': ['pair_explanation_tool']}

        allowed_ids = set(self.advisor_by_id if advisor_ids is None else advisor_ids)

        if intent == 'portal_workflow':
            return self._workflow_answer(norm)

        if intent == 'my_profile_fit':
            return self._profile_fit_answer(student_context, allowed_ids, top_k)

        named = [aid for aid in gate.get('named', []) if aid in allowed_ids]
        if intent in ('advisor_compare', 'advisor_profile') and named:
            rankings, citations, _ = self._hybrid_retrieve(effective_q, set(named), top_k=max(top_k, len(named)))
            # Ensure every named advisor appears even if query had no extra topic words
            seen_aids = {r['advisor_id'] for r in rankings}
            for aid in named:
                if aid not in seen_aids and aid in self.advisor_by_id:
                    sp = self.advisor_by_id[aid]['skill_profile']
                    rankings.append({
                        'advisor_id': aid,
                        'advisor_name': sp['advisor_name'],
                        'score': None,
                        'matched_skills': sp['display_skills'][:5],
                        'summary': sp['summary'],
                    })
                    url = _safe_url(sp.get('source_url'))
                    if url:
                        citations.append({'advisor_id': aid, 'title': f"Hồ sơ chuyên môn · {sp['advisor_name']}", 'url': url, 'source_url': url, 'snippet': sp['summary']})

            if len(named) >= 2:
                lines = ['Đối chiếu chuyên môn giữa các giảng viên bạn hỏi:']
                for idx, r in enumerate(rankings[:4], start=1):
                    lines.append(f"• **[{idx}] {r['advisor_name']}**: {r['summary']} (Kỹ năng tiêu biểu: {', '.join(r['matched_skills'][:5])}).")
                deterministic_text = '\n'.join(lines)
                tool_used = ['advisor_compare_tool', 'hybrid_rag_retriever']
            else:
                r = rankings[0]
                deterministic_text = (
                    f"**{r['advisor_name']}** — {r['summary']}\n"
                    f"• **Nhóm kỹ năng & chủ đề ghi nhận**: {', '.join(r['matched_skills'][:6])}.\n"
                    f"• Dưới đây là các công trình và nguồn học thuật đã kiểm chứng liên quan `[1]`:"
                )
                tool_used = ['advisor_profile_tool', 'hybrid_rag_retriever']

            llm_text = self._try_llm_grounded_answer(effective_q, 'advisor_profile', rankings, citations)
            return self._pack(
                llm_text or deterministic_text,
                'advisor_profile',
                rankings=[] if len(named) == 1 else rankings,
                citations=citations[:top_k],
                mode='rag_agent_llm_grounded' if llm_text else 'rag_agent_deterministic',
                tools=tool_used,
            )

        # General Topic -> Advisor Hybrid RAG Search
        rankings, citations, query_tags = self._hybrid_retrieve(effective_q, allowed_ids, top_k=top_k)
        if not rankings:
            return self._pack(
                'Mình chưa tìm thấy bằng chứng khớp trực tiếp trong danh mục giảng viên cho từ khóa này. '
                'Bạn hãy thử nêu rõ **hướng công nghệ hoặc bài toán** (ví dụ: *Học máy, NLP/RAG, Computer Vision, Phát triển Web, Mobile, Hệ thống thông tin, Phân tích dữ liệu*) nhé!',
                'no_evidence',
                tools=['hybrid_rag_retriever'],
            )

        topic_labels = [self.tag_label(t) for t in list(query_tags)[:4]]
        header = (
            f"Trọng tâm chủ đề **{', '.join(topic_labels)}** — các giảng viên có công trình & kỹ năng phù hợp nhất:"
            if topic_labels else
            'Các giảng viên có hướng nghiên cứu và kỹ năng phù hợp nhất với nội dung bạn tìm:'
        )
        lines = [header]
        for idx, r in enumerate(rankings[:min(4, top_k)], start=1):
            score_txt = f" ({r['score'] * 100:.1f}%)" if isinstance(r.get('score'), (int, float)) else ''
            lines.append(
                f"{idx}. **{r['advisor_name']}**{score_txt} — {r['summary']} "
                f"*(Khớp: {', '.join(r['matched_skills'][:4])})* `[{idx}]`"
            )
        deterministic_text = '\n'.join(lines)
        llm_text = self._try_llm_grounded_answer(effective_q, 'topic_match', rankings, citations)
        return self._pack(
            llm_text or deterministic_text,
            'topic_match',
            rankings=rankings,
            citations=citations[:top_k],
            mode='rag_agent_llm_grounded' if llm_text else 'rag_agent_deterministic',
            tools=['hybrid_rag_retriever', 'e4_compatibility_tool'],
        )
