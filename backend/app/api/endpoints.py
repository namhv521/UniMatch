import json
import os
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.baselines.classical import allocate
from src.data_pipeline.dataset import cohort, load_dataset
from src.rl.benchmark import evaluate_assignment

router = APIRouter()
STRATEGIES = {'exact_hungarian': 'exact', 'greedy': 'greedy', 'spa': 'spa', 'random': 'random'}


def get_dataset():
    return load_dataset(allow_partial=os.getenv('KLTN_ALLOW_PARTIAL') == '1')


def require_dataset():
    try:
        return get_dataset()
    except (ValueError, FileNotFoundError, KeyError) as error:
        raise HTTPException(503, 'Dataset unavailable or incomplete; finish curation before allocation.') from error


class AllocationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cohort_type: Literal['train', 'val', 'test'] = 'val'
    algorithm: Literal['exact_hungarian', 'greedy', 'spa', 'random', 'maskable_ppo'] = 'exact_hungarian'
    fairness_weight: float = Field(default=.15, ge=0, le=1)
    quota_override: int | None = Field(default=None, ge=1, strict=True)


@router.get('/health')
@router.get('/api/v1/health')
def health():
    try:
        dataset = get_dataset()
    except (ValueError, FileNotFoundError, KeyError):
        dataset = None
    return {'status': 'healthy' if dataset else 'data_unavailable', 'version': '1.0.0',
            'data_loaded': dataset is not None,
            'total_advisors': len(dataset['advisors']) if dataset else 0,
            'partial_data': dataset['partial'] if dataset else None,
            'available_models': list(STRATEGIES) if dataset else []}


@router.get('/api/v1/faculty')
def faculty():
    dataset = require_dataset()
    return {'advisors': dataset['advisors'], 'partial_data': dataset['partial']}


@router.post('/api/v1/allocate')
def allocation(request: AllocationRequest):
    if request.cohort_type == 'test':
        raise HTTPException(409, 'Holdout is locked until candidate selection is frozen.')
    if request.algorithm == 'maskable_ppo':
        raise HTTPException(409, 'No validated production PPO checkpoint is available.')
    dataset = require_dataset()
    scores, quotas, indices = cohort(dataset, request.cohort_type)
    if request.quota_override is not None:
        quotas[:] = request.quota_override
    try:
        assignment = allocate(scores, quotas, STRATEGIES[request.algorithm])
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    rows = []
    for local_index, advisor_index in enumerate(assignment):
        student = dataset['students'][indices[local_index]]
        advisor = dataset['advisors'][advisor_index]
        rows.append({**{key: student.get(key) for key in ('student_id', 'student_name', 'thesis_title')},
                     'advisor_id': advisor['advisor_id'], 'advisor_name': advisor['advisor_name'],
                     'compatibility_score': float(scores[local_index, advisor_index])})
    loads = np.bincount(assignment, minlength=len(quotas))
    return {'status': 'success', 'algorithm': request.algorithm,
            'partial_data': dataset['partial'], 'dataset_sha256': dataset['sha256'],
            'objective': 'compatibility', 'fairness_weight_applied': False,
            'metrics': evaluate_assignment(scores, quotas, assignment), 'assignments': rows,
            'advisor_loads': {row['advisor_name']: {'current_load': int(loads[i]), 'quota': int(quotas[i]),
                                                   'ratio': float(loads[i] / max(quotas[i], 1))}
                              for i, row in enumerate(dataset['advisors'])},
            'quotas': {row['advisor_id']: int(quotas[i]) for i, row in enumerate(dataset['advisors'])}}


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=2000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    top_k: int = Field(default=3, ge=1, le=20)


@router.post('/api/v1/recommend')
def recommend(request: RecommendationRequest):
    dataset = require_dataset()
    text = request.title + ' ' + ' '.join(request.keywords)
    if len(text) > 10000:
        raise HTTPException(422, 'Combined text exceeds 10000 characters.')
    scores = dataset['extractor'].compatibility([text], dataset['advisor_texts'])[0]
    rows = []
    for index in np.argsort(-scores, kind='stable')[:request.top_k]:
        advisor = dataset['advisors'][index]
        skills = advisor.get('skill_text', '').lower()
        rows.append({'advisor_id': advisor['advisor_id'], 'advisor_name': advisor['advisor_name'],
                     'compatibility_score': float(scores[index]), 'primary_field': advisor.get('primary_field'),
                     'remaining_quota': None,
                     'matching_skills': [word for word in request.keywords if word.lower() in skills]})
    return {'status': 'success', 'recommendations': rows, 'partial_data': dataset['partial'],
            'capacity_note': 'Recommendations do not reserve quota; no active cohort workload is stored.'}


@router.get('/api/v1/benchmark/summary')
def benchmark_summary():
    dataset = require_dataset()
    path = Path('outputs/results/benchmark_validation_5seeds.json')
    if not path.exists():
        raise HTTPException(409, 'The full five-seed validation benchmark is not available yet.')
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('dataset_sha256') != dataset['sha256'] or not report.get('complete'):
        raise HTTPException(409, 'Benchmark is incomplete or belongs to a different dataset.')
    return report
