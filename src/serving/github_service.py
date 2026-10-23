"""Additive serving for explicitly selected, source-verified GitHub bundles."""
import json
import math
import re
from pathlib import Path
from urllib.parse import quote

import numpy as np

from src.data_pipeline.github_advisors import canonical, digest, verify_run
from src.data_pipeline.normalization import load_taxonomy, normalize_mentions
from src.data_pipeline.review_decisions import record_hash
from src.environment.rebuild_env import MatchingEnv
from src.serving.rebuild_assistant import AdvisorAssistant, _safe_source
from src.serving.rebuild_service import RebuildService, POLICY_VERSION


ROOT = Path(__file__).resolve().parents[2]


def _read(path):
    return json.loads(Path(path).read_bytes())


def _load_bundle(path):
    from src.features.github_enrichment import load_training_bundle
    return load_training_bundle(path)


def _load_selection(path):
    from src.evaluation.github_retraining import load_selection
    return load_selection(path)


def load_github_service(bundle_path, selection_path, runtime_dir):
    """Verify first; no incumbent fallback, training, network or artifact writes."""
    from src.evaluation.github_retraining import validate_bundle
    from src.features.rebuild_features import FeaturePipeline
    from src.rl.rebuild_dqn import MaskedDQN
    from src.rl.rebuild_ppo import MaskedPPOAgent
    import torch

    if not bundle_path or not selection_path:
        raise ValueError('explicit_github_bundle_and_selection_required')
    bundle_path, selection_path = Path(bundle_path).resolve(), Path(selection_path).resolve()
    runtime = Path(runtime_dir).resolve()
    # Compare the resolved destination with physical private paths, not resolved aliases.
    # A symlink/junction from either private path into frontend must also fail closed.
    private_roots = (ROOT/'data_rebuild/runtime',ROOT/'data_rebuild/v1/runtime')
    if not any(runtime.is_relative_to(path) for path in private_roots):
        raise ValueError('private_runtime_directory_required')
    if runtime.is_relative_to(bundle_path.parent) or runtime.is_relative_to(selection_path.parent):
        raise ValueError('runtime_must_not_modify_frozen_artifacts')
    bundle = _load_bundle(bundle_path)
    selected = _load_selection(selection_path)
    # The verified selected-run manifest binds this file; contracts alone omit text payloads.
    training_input = _read(selection_path.parent/'input_manifest.json')
    bundle_sha256 = digest(bundle_path.read_bytes())
    if training_input.get('bundle_sha256') != bundle_sha256:
        raise ValueError('github_training_bundle_hash_mismatch')
    suite = validate_bundle(bundle)
    serving = bundle['serving']
    bound={str(Path(item['path']).resolve()):item['sha256'] for item in bundle['source_artifacts']}
    for key in ('students_path','advisors_path','index_path','scores_path','available_path','taxonomy_path','feature_contract_path'):
        path=Path(serving[key]).resolve()
        if path.is_symlink() or bound.get(str(path)) != digest(path.read_bytes()):
            raise ValueError('github_serving_path_not_source_bound')
    students = _read(serving['students_path']); advisors = _read(serving['advisors_path'])
    index = _read(serving['index_path'])
    ids = tuple(row['advisor_id'] for row in advisors)
    if (len(ids) != 35 or len(set(ids)) != 35 or ids != suite['train'][0].advisor_ids
            or list(ids) != index['advisor_ids']
            or [row['student_id'] for row in students] != index['student_ids']):
        raise ValueError('github_serving_registry_mismatch')
    scores = np.load(serving['scores_path'], allow_pickle=False)
    available = np.load(serving['available_path'], allow_pickle=False)
    shape = (len(students),len(advisors))
    if (scores.shape != shape or available.shape != shape or list(shape) != index['shape']
            or scores.dtype != np.float64 or available.dtype != np.bool_
            or not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1))):
        raise ValueError('github_serving_matrix_contract_mismatch')
    identities = sorted({str(row[key]) for row in students+advisors
                         for key in ('student_id','student_name','advisor_id','advisor_name') if row.get(key)})
    pipeline = FeaturePipeline.load(serving['transformer_dir'], known_identities=identities)
    taxonomy = load_taxonomy(serving['taxonomy_path'])
    tag_order = sorted((group,tag) for group,tags in taxonomy['groups'].items() for tag in tags)
    env = MatchingEnv(suite['train'], shuffle_students=True)
    contract = bundle['model_contract']
    if (record_hash(tag_order) != contract['taxonomy_feature_order_sha256']
            or env.reward_weights != contract['reward_weights']
            or POLICY_VERSION != contract['quota_policy_version']):
        raise ValueError('github_serving_feature_policy_mismatch')
    encoder = bundle['frozen_encoder']
    for key,name in (('transformer_json_sha256','transformer.json'),('transformer_idf_sha256','idf.npz')):
        if digest((Path(serving['transformer_dir'])/name).read_bytes()) != encoder[key]:
            raise ValueError('github_serving_encoder_hash_mismatch')
    if (digest(Path(serving['feature_contract_path']).read_bytes()) != contract['feature_contract_sha256']
            or selected.get('schema_version') != 'github-advisor-model-selection/1.0'
            or selected.get('test_evaluated') is not False or selected.get('production_promoted') is not False):
        raise ValueError('github_serving_feature_selection_mismatch')
    versions = {'phase4_run_id':bundle['bundle_run_id'], 'github_bundle_run_id':bundle['bundle_run_id'],
                'github_bundle_sha256':bundle_sha256,
                'github_manifest_sha256':serving['github_manifest_sha256'],
                'parent_feature_contract_sha256':contract['feature_contract_sha256'],
                'encoder_sha256':record_hash(encoder), 'frozen_encoder':{
                    key:encoder[key] for key in ('transformer_json_sha256','transformer_idf_sha256')},
                'selection_run_id':selected['run_id'], 'scope':'local_research_source_enriched',
                'identity_mapping':'owner_confirmed', 'models':{}}
    models = {}
    torch.set_num_threads(1)
    for algorithm in ('ppo','dqn'):
        candidate = selected['candidates'][algorithm]
        if (candidate['native_contract'] != contract
                or candidate['native_contract_sha256'] != record_hash(contract)
                or candidate['frozen_encoder_sha256'] != record_hash(encoder)
                or candidate['frozen_encoder'] != encoder or candidate['algorithm'] != algorithm
                or candidate.get('production_promoted') is not False):
            raise ValueError('github_selected_checkpoint_contract_mismatch')
        models[algorithm] = (MaskedPPOAgent.load(candidate['path'], env, expected_contract=contract)
                             if algorithm == 'ppo' else MaskedDQN.load(candidate['path'], expected_contract=contract))
        versions['models'][algorithm] = {key:candidate[key] for key in (
            'checkpoint_steps','seed','checkpoint_sha256','native_contract_sha256')}
        versions['models'][algorithm]['production_promoted'] = False
    service = RebuildService(pipeline=pipeline,advisors=advisors,taxonomy=taxonomy,versions=versions,
                             runtime_dir=runtime,scorable=available.any(axis=0),models=models,
                             model_contracts={key:contract for key in models})
    service.github_serving = serving
    return service


class GithubAssistant(AdvisorAssistant):
    """Keep official identity anchors; cite only independently approved additions."""
    def __init__(self, profiles, service, *, github_run, github_manifest_sha256,
                 quality_review_path, quality_review_sha256, versions=None):
        super().__init__(profiles,service,versions=versions or service.versions)
        run = Path(github_run).resolve()
        if digest((run/'manifest.json').read_bytes()) != github_manifest_sha256:
            raise ValueError('github_assistant_manifest_mismatch')
        verify_run(run)
        review_path=Path(quality_review_path)
        if digest(review_path.read_bytes()) != quality_review_sha256:
            raise ValueError('github_assistant_review_mismatch')
        review=_read(review_path)
        if review.get('status') != 'verified' or review.get('source_manifest_sha256') != github_manifest_sha256:
            raise ValueError('github_assistant_review_not_verified')
        def lines(name):
            return [json.loads(line) for line in (run/name).read_bytes().splitlines() if line.strip()]
        sources={row['source_id']:row for row in lines('sources.jsonl')}
        repositories={row['full_name']:row for row in lines('repositories.jsonl')}
        evidence={row['evidence_id']:row for row in lines('evidence.jsonl')}
        receipt=_read(run/'owner_receipt.json')
        if receipt.get('identity_mapping') != 'owner_confirmed':
            raise ValueError('github_assistant_owner_mapping_required')
        self.github_evidence = {}
        for unit in review['approved_units']:
            if unit.get('checks') != {'source':'pass','span':'pass','semantic':'pass'}:
                raise ValueError('github_assistant_unverified_claim')
            key=unit['advisor_id']
            if key not in self.profiles:
                raise ValueError('github_assistant_unknown_advisor')
            for evidence_id in unit['evidence_ids']:
                row=evidence[evidence_id]; source=sources[row['source_id']]; repo=repositories[row['repository']]
                if (any(row[field]!=unit[field] for field in ('advisor_id','group','tag'))
                        or repo.get('fork') or repo.get('is_template')
                        or digest(canonical({k:v for k,v in row.items() if k!='evidence_id'})) != evidence_id
                        or row['source_sha256'] != source['sha256'] or row['source_url'] != source['url']
                        or source.get('http_status') != 200
                        or not re.fullmatch('[a-f0-9]{40}',row.get('commit_sha') or '')):
                    raise ValueError('github_assistant_evidence_binding_mismatch')
                raw=(run/'raw'/f'{source["sha256"]}.bin').read_bytes()
                text=raw.decode('utf-8-sig')
                if source['kind']=='repository_listing':
                    match=re.fullmatch(r'repositories\[id=(\d+)\]\.(name|description|language)',row['locator'])
                    if not match:raise ValueError('github_assistant_metadata_locator_invalid')
                    entry=next(item for item in json.loads(text) if item['id']==int(match[1]) and item['full_name']==row['repository'])
                    text=entry[match[2]]
                if (text[row['start']:row['end']] != row['matched_text']
                        or text[row['excerpt_start']:row['excerpt_end']] != row['excerpt']):
                    raise ValueError('github_assistant_source_span_mismatch')
                self.github_evidence.setdefault(key,[]).append((row,source,text))

    def match_topic_to_advisors(self, topic, advisor_ids=None, top_k=5):
        """Include verified concept evidence even when frozen E4 has no lexical signal."""
        from src.serving.rebuild_assistant import _topic_query, _unsafe
        selected = self._selection(advisor_ids, top_k)
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 4000:
            raise ValueError('assistant_question_required_max_4000')
        if _unsafe(topic):
            return []
        topic = _topic_query(topic)
        rows = super().match_topic_to_advisors(topic, selected, 10)
        seen = {row['advisor_id'] for row in rows}
        for key in selected:
            if key in seen or key not in self.github_evidence:
                continue
            citation = self._citation(key, topic, require_concepts=True)
            if citation and citation.get('matched_concepts'):
                rows.append({'advisor_id': key, 'advisor_name': self.profiles[key]['advisor_name'],
                             'score': None, 'citation': citation, 'ranking_basis': 'verified_source_concept_only'})
        return sorted(rows, key=lambda row: (-(row['score'] if row['score'] is not None else -1), row['advisor_id']))[:top_k]

    def answer(self, question, **kwargs):
        result = super().answer(question, **kwargs)
        if any(row.get('ranking_basis') == 'verified_source_concept_only' for row in result['rankings']):
            result['answer'] += ' Các hồ sơ có nguồn khớp chủ đề nhưng chưa có điểm từ encoder được liệt kê bổ sung; không gán điểm giả cho những hồ sơ này.'
        return result

    def _citation(self, advisor_id, query='', *, require_concepts=False):
        from src.serving.rebuild_assistant import _topic_query
        query = _topic_query(query)
        concepts={(m['group'],m['tag']) for m in normalize_mentions(query,self.service.taxonomy)}
        raw_confidence=next(row for row in self.service.advisors if row['advisor_id']==advisor_id).get('expertise_confidence')
        try: confidence=float(raw_confidence) if raw_confidence not in ('',None) and not isinstance(raw_confidence,bool) else None
        except (ValueError,TypeError): confidence=None
        if confidence is not None and (not math.isfinite(confidence) or not 0<=confidence<=1): confidence=None
        candidates=[]
        for row,source,text in self.github_evidence.get(advisor_id,[]):
            if concepts and (row['group'],row['tag']) not in concepts:
                continue
            if require_concepts and not concepts:
                continue
            excerpt=row['excerpt']
            if not _safe_source(excerpt):continue
            words=list(re.finditer(r'\S+',excerpt)); position=row['start']-row['excerpt_start']
            # Include surrounding context when the literal concept ends a sentence.
            first=max(0,next((i for i,w in enumerate(words) if w.end()>position),0)-8)
            start=words[first].start();end=words[min(len(words),first+20)-1].end()
            repository_url=f'https://github.com/{row["repository"]}/tree/{row["commit_sha"]}'
            candidates.append({'title':self.profiles[advisor_id]['advisor_name'],
                'source_url':f'https://github.com/{row["repository"]}/blob/{row["commit_sha"]}/'+quote(row['path'],safe='/')
                    if row.get('path') else row['source_url'],
                'raw_source_url':row['source_url'],'repository_url':repository_url,
                'snippet':excerpt[start:end],'source_sha256':row['source_sha256'],
                'retrieved_at':source['retrieved_at'],'locator':row['locator'],
                'field':row.get('path') or row['locator'],'start':row['excerpt_start']+start,
                'end':row['excerpt_start']+end,'offset_basis':row.get('offset_basis'),
                'attribution':row['evidence_class'],'identity_mapping':'owner_confirmed',
                'evidence_confidence':confidence,'evidence_id':row['evidence_id'],
                'confidence_semantics':'Approved source/span/semantic units divided by candidate units; not proficiency or supervision probability.',
                'matched_concepts':[{'group':row['group'],'tag':row['tag']}],
                'scope':'Owner-confirmed identity; source concept only, not personal proficiency or supervision outcome.'})
        return candidates[0] if candidates else super()._citation(advisor_id,query,require_concepts=require_concepts)
