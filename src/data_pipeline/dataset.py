"""Load grounded profiles and construct train-only TF-IDF compatibility."""
import hashlib
import json
from math import ceil
from pathlib import Path

import numpy as np

from .feature_extractor import FeatureExtractor
from .split_dataset import temporal_split_dataset


def load_dataset(data_dir='data/curated', *, allow_partial=False):
    root = Path(data_dir)
    report = json.loads((root / 'curation_report.json').read_text(encoding='utf-8'))
    if not allow_partial and not report['ready_for_full_experiment']:
        raise ValueError('Curation is incomplete; full experiments are blocked. Use --allow-partial only for smoke runs.')
    students = json.loads((root / 'theses.json').read_text(encoding='utf-8'))
    advisors = json.loads((root / 'advisors.json').read_text(encoding='utf-8'))
    if len({row['student_id'] for row in students}) != len(students):
        raise ValueError('Repeated student identity in curated data')
    if len({row['advisor_id'] for row in advisors}) != len(advisors):
        raise ValueError('Repeated advisor identity')
    eligible = [index for index, row in enumerate(students) if row['submission_year'] <= 2025]
    local_split = temporal_split_dataset(records=[students[index] for index in eligible])
    split = {key: np.array([eligible[index] for index in values], dtype=int)
             for key, values in local_split.items()}
    if any(len(indices) == 0 for indices in split.values()):
        raise ValueError('All train/val/test splits must be nonempty')
    extractor = FeatureExtractor().fit([students[i]['feature_text'] for i in split['train']])
    profiles = [row['profile_text'] + ' ' + row['skill_text'] + ' ' + row.get('skill_text_inferred', '')
                for row in advisors]
    scores = extractor.compatibility([row['feature_text'] for row in students], profiles)
    digest = hashlib.sha256(json.dumps({'students': students, 'advisors': advisors,
                                       'split': {key: value.tolist() for key, value in split.items()}},
                                      sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'students': students, 'advisors': advisors, 'split': split, 'scores': scores,
            'extractor': extractor, 'advisor_texts': profiles, 'sha256': digest,
            'future_indices': [index for index, row in enumerate(students) if row['submission_year'] > 2025],
            'partial': not report['ready_for_full_experiment']}


def cohort(dataset, split):
    indices = dataset['split'][split]
    scores = dataset['scores'][indices]
    quotas = np.array([row['quota'] if row.get('quota') is not None else ceil(len(indices) / len(dataset['advisors']))
                       for row in dataset['advisors']], dtype=int)
    return scores, quotas, indices
