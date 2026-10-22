"""Train-only, evidence-scoped features for the rebuilt private gold snapshot."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from numbers import Real
from pathlib import Path

import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

VERSION = 'rebuild-features/1.0'
TECH_COLUMNS = ('programming_languages', 'frameworks_libraries', 'databases', 'ml_ai_methods',
                'data_engineering_tools', 'cloud_devops_tools', 'security_network_tools',
                'software_engineering_methods', 'research_methods', 'math_statistics_topics')
IDENTITY_COLUMNS = ('student_id', 'student_name', 'advisor_id', 'advisor_name')


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=8)
def _identity_pattern(identities):
    alternatives = [r'\s+'.join(re.escape(p) for p in identity.split()) for identity in identities]
    return re.compile(r'(?<!\w)(?:' + '|'.join(alternatives) + r')(?!\w)',re.IGNORECASE)


def preprocess_text(text, identities=()):
    """Remove identity/contact metadata; return text and counts without raw values."""
    text = unicodedata.normalize('NFC', str(text or ''))
    counts = Counter()
    patterns = {
        'metadata_lines': r'(?im)^\s*(?:sinh viên|họ và tên|tên sinh viên|mssv|mã sinh viên|giảng viên hướng dẫn|người hướng dẫn|student name|student id|supervisor)\s*[:：].*$',
        'email': r'(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b',
        'url': r'(?i)(?:https?://|www\.)\S+',
        'phone': r'(?<!\w)(?:\+?84|0)[\s().-]*(?:\d[\s().-]*){8,10}(?!\w)',
        'long_id': r'\b\w*\d{7,}\w*\b',
        'academic_boilerplate': r'(?i)\b(?:khóa luận tốt nghiệp|khoá luận tốt nghiệp|báo cáo thực tập|đại học kinh tế quốc dân|khoa công nghệ thông tin)\b',
    }
    for name, pattern in patterns.items():
        text, count = re.subn(pattern, ' ', text)
        counts[name] += count
    identities = tuple(sorted({unicodedata.normalize('NFC',str(i).strip()) for i in identities if str(i).strip()},
                              key=lambda x: (-len(x),x)))
    if identities:
        # Full identities are a redaction registry, never features or learned weights.
        text, count = _identity_pattern(identities).subn(' ', text)
        counts['known_identity'] += count
    return re.sub(r'\s+', ' ', text).strip(), dict(counts)


def _tags(row, columns):
    return {(column if column != 'expertise_topic_tags' else 'topic_tags', value.strip())
            for column in columns for value in str(row.get(column) or '').split(';') if value.strip()}


def _quality(row, column):
    value = row.get(column)
    if isinstance(value, (bool,np.bool_)): raise ValueError('invalid_evidence_quality')
    if value is None or value == '': return None
    try: value = float(value)
    except (ValueError, TypeError): raise ValueError('invalid_evidence_quality') from None
    if not np.isfinite(value) or not 0 <= value <= 1: raise ValueError('invalid_evidence_quality')
    return value


class FeaturePipeline:
    """TF-IDF E0/E1, Jaccard E2, evidence-weighted Jaccard E3, convex E4.

    Missing slots contain zero solely for matrix storage and MUST use `available`.
    E4 defaults to an uncalibrated equal-weight baseline, never a calibration claim.
    No publication summaries, personal proficiency or unconfirmed preferences used.
    """

    def __init__(self, config=None):
        self.config = dict(config or {})
        self.weights = dict(self.config.get('hybrid_weights', {'E1': 1/3, 'E2': 1/3, 'E3': 1/3}))
        if (set(self.weights) != {'E1','E2','E3'} or any(isinstance(v,(bool,np.bool_)) or not isinstance(v,Real)
                or not np.isfinite(v) or v < 0 for v in self.weights.values())
                or not np.isclose(sum(self.weights.values()), 1)):
            raise ValueError('hybrid_weights_must_be_convex')
        preference_weight = self.config.get('preference_weight', 0)
        if isinstance(preference_weight,(bool,np.bool_)) or not isinstance(preference_weight,Real):
            raise ValueError('invalid_preference_weight')
        self.preference_weight = float(preference_weight)
        if not np.isfinite(self.preference_weight) or not 0 <= self.preference_weight <= 1:
            raise ValueError('invalid_preference_weight')
        self.identities = tuple(sorted(set(self.config.get('known_identities', ()))))
        self.vectorizers = {}

    def _registry(self, rows):
        return tuple(sorted(set(self.identities) | {str(row[k]) for row in rows
                            for k in IDENTITY_COLUMNS if row.get(k)}))

    def _texts(self, rows, entity, identities):
        result, counts = {'E0': [], 'E1': []}, Counter()
        for row in rows:
            if entity == 'students':
                title = row.get('thesis_title') or ''
                values = {'E0':title, 'E1':title + '\n' + (row.get('thesis_abstract') or '')}
            else:
                # This field contains reviewed research/teaching topics from gold;
                # raw profile_text, publication author strings and contacts excluded.
                values = {'E0':row.get('research_description') or '', 'E1':row.get('research_description') or ''}
            for key, text in values.items():
                clean, redactions = preprocess_text(text, identities)
                result[key].append(clean)
                counts.update(redactions)
        return result, counts

    def fit(self, train_students, advisors):
        train_students, advisors = list(train_students), list(advisors)
        self.identities = self._registry(train_students + advisors)
        texts, _ = self._texts(train_students, 'students', self.identities)
        for key in ('E0','E1'):
            vectorizer = TfidfVectorizer(lowercase=True, strip_accents=None, ngram_range=(1,2),
                                         token_pattern=r'(?u)\b\w\w+\b', norm='l2', dtype=np.float64)
            try: vectorizer.fit(texts[key])
            except ValueError as error:
                if 'empty vocabulary' not in str(error): raise
                vectorizer = None
            self.vectorizers[key] = vectorizer
        return self

    def transform_score(self, students, advisors):
        if set(self.vectorizers) != {'E0','E1'}: raise ValueError('pipeline_not_fitted')
        students, advisors = list(students), list(advisors)
        identities = self._registry(students + advisors)
        student_texts, counts = self._texts(students, 'students', identities)
        advisor_texts, more = self._texts(advisors, 'advisors', identities)
        counts.update(more)
        shape = (len(students), len(advisors))
        scores = {key:np.zeros(shape) for key in ('E0','E1','E2','E3','E4')}
        available = {key:np.zeros(shape, dtype=bool) for key in scores}
        for key, vectorizer in self.vectorizers.items():
            if vectorizer is None or not all(shape): continue
            left, right = vectorizer.transform(student_texts[key]), vectorizer.transform(advisor_texts[key])
            scores[key] = np.clip((left @ right.T).toarray(), 0, 1)
            available[key] = np.outer(left.getnnz(axis=1)>0, right.getnnz(axis=1)>0)
        overlap_counts = {key:np.zeros(shape,dtype=int) for key in ('E2','E3')}
        for i, student in enumerate(students):
            for j, advisor in enumerate(advisors):
                for key, columns in [('E2',('research_domain_tags','topic_tags')),
                                     ('E3',TECH_COLUMNS)]:
                    other_columns = tuple('expertise_topic_tags' if c == 'topic_tags' else c for c in columns)
                    left, right = _tags(student, columns), _tags(advisor, other_columns)
                    if not left or not right: continue
                    overlap_counts[key][i,j] = len(left & right)
                    value = len(left & right) / len(left | right)
                    if key == 'E3':
                        a, b = _quality(student,'skill_confidence'), _quality(advisor,'expertise_confidence')
                        if a is None or b is None: continue
                        value *= np.sqrt(a*b)
                    scores[key][i,j] = value
                    available[key][i,j] = True
        preference_scores, preference_available = np.zeros(shape), np.zeros(shape,dtype=bool)
        for i, student in enumerate(students):
            preferred = set(str(student.get('preferred_advisor_ids') or '').split(';')) - {''}
            if student.get('preferences_confirmed') is True and preferred:
                for j, advisor in enumerate(advisors):
                    preference_available[i,j] = True
                    preference_scores[i,j] = float(advisor.get('advisor_id') in preferred)
        numerator, denominator = np.zeros(shape), np.zeros(shape)
        for key, weight in self.weights.items():
            effective = (1-self.preference_weight)*weight*available[key]
            numerator += effective*scores[key]
            denominator += effective
        effective = self.preference_weight*preference_available
        numerator += effective*preference_scores
        denominator += effective
        available['E4'] = denominator>0
        np.divide(numerator,denominator,out=scores['E4'],where=available['E4'])
        diagnostics = {key:{'unavailable_pairs':int((~mask).sum()),
                            'students_without_available_candidates':int((~mask.any(axis=1)).sum()),
                            'advisors_without_available_students':int((~mask.any(axis=0)).sum())}
                       for key,mask in available.items()}
        return {'scores':scores, 'available':available, 'redaction_counts':dict(counts),
                'components':{'overlap_counts':overlap_counts,'hybrid_denominator':denominator,
                    'availability_diagnostics':diagnostics,
                    'hybrid_weights':self.weights,'calibration_status':'uncalibrated_configured_baseline',
                    'preferences_available':preference_available,'preference_scores':preference_scores,
                    'publications_available':False,'publication_reason':'no_approved_publication_summaries',
                    'proficiency_used':False, 'version':VERSION}}

    def explain_pair(self, student, advisor):
        """Reconstruct a pair score from shared terms/tags and observed weights.

        Terms describe lexical overlap, never causal quality or personal mastery.
        Source references stay with the approved input rows/reviewer packet.
        """
        result = self.transform_score([student], [advisor])
        identities = self._registry([student, advisor])
        left, _ = self._texts([student], 'students', identities)
        right, _ = self._texts([advisor], 'advisors', identities)
        explanation = {}
        for key in ('E0', 'E1'):
            vectorizer = self.vectorizers[key]
            shared = []
            if vectorizer is not None:
                products = vectorizer.transform(left[key]).multiply(vectorizer.transform(right[key])).tocoo()
                names = vectorizer.get_feature_names_out()
                shared = sorted([{'term': str(names[j]), 'contribution': float(value)}
                                 for j, value in zip(products.col, products.data)],
                                key=lambda item: (-item['contribution'], item['term']))
            explanation[key] = {'shared_terms': shared}
        for key, columns in [('E2', ('research_domain_tags', 'topic_tags')), ('E3', TECH_COLUMNS)]:
            other = tuple('expertise_topic_tags' if c == 'topic_tags' else c for c in columns)
            a, b = _tags(student, columns), _tags(advisor, other)
            explanation[key] = {'shared_tags': [list(tag) for tag in sorted(a & b)],
                                'union_count': len(a | b)}
        qualities = (_quality(student, 'skill_confidence'), _quality(advisor, 'expertise_confidence'))
        explanation['E3']['evidence_quality_factor'] = (float(np.sqrt(qualities[0]*qualities[1]))
                                                       if all(q is not None for q in qualities) else None)
        denominator = float(result['components']['hybrid_denominator'][0, 0])
        contributions = {key: (float((1-self.preference_weight)*weight*result['scores'][key][0,0]/denominator)
                              if denominator and result['available'][key][0,0] else 0.0)
                         for key, weight in self.weights.items()}
        contributions['confirmed_preference'] = (float(self.preference_weight*result['components']['preference_scores'][0,0]/denominator)
                                                if denominator and result['components']['preferences_available'][0,0] else 0.0)
        explanation['E4'] = {'configured_weights': self.weights, 'observed_weight_total': denominator,
                             'contributions': contributions}
        for key in explanation:
            observed = bool(result['available'][key][0,0])
            explanation[key].update(available=observed, score=float(result['scores'][key][0,0]) if observed else None)
        return explanation

    def save(self, path):
        path = Path(path); path.mkdir(parents=True,exist_ok=True)
        arrays = {key:value.idf_ for key,value in self.vectorizers.items() if value is not None}
        np.savez_compressed(path/'idf.npz', **arrays)
        config = {k:v for k,v in self.config.items() if k != 'known_identities'}
        payload = {'version':VERSION,'sklearn_version':sklearn.__version__,'config':config,
                   'redaction_registry_sha256':_hash(self.identities),
                   'idf_sha256':hashlib.sha256((path/'idf.npz').read_bytes()).hexdigest(),
                   'vocabularies':{key:value.vocabulary_ if value is not None else None for key,value in self.vectorizers.items()}}
        payload['manifest_sha256'] = _hash(payload)
        (path/'transformer.json').write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True),encoding='utf-8')

    @classmethod
    def load(cls, path, *, known_identities=()):
        path = Path(path)
        payload = json.loads((path/'transformer.json').read_text(encoding='utf-8'))
        expected = payload.pop('manifest_sha256')
        if _hash(payload) != expected or hashlib.sha256((path/'idf.npz').read_bytes()).hexdigest() != payload['idf_sha256']:
            raise ValueError('artifact_hash_mismatch')
        if payload['version'] != VERSION or payload['sklearn_version'] != sklearn.__version__:
            raise ValueError('transformer_version_mismatch')
        result = cls({**payload['config'],'known_identities':list(known_identities)})
        if _hash(result.identities) != payload['redaction_registry_sha256']:
            raise ValueError('redaction_registry_mismatch')
        with np.load(path/'idf.npz',allow_pickle=False) as arrays:
            for key,vocabulary in payload['vocabularies'].items():
                if vocabulary is None: result.vectorizers[key] = None; continue
                vectorizer = TfidfVectorizer(vocabulary=vocabulary, ngram_range=(1,2),
                                             token_pattern=r'(?u)\b\w\w+\b',dtype=np.float64)
                vectorizer.fit(['placeholder'])
                vectorizer.idf_ = arrays[key]
                result.vectorizers[key] = vectorizer
        return result
