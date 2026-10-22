"""P4-bound cohort construction; simulated eligibility never becomes gold data."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

from src.data_pipeline.normalization import load_taxonomy
from src.data_pipeline.review_decisions import record_hash
from src.domain.rebuild_matching import AllocationProblem, equal_quotas
from src.features.rebuild_acceptance import load_approved_features
from src.features.rebuild_experiments import _load_snapshot


POLICY_VERSION='equal-division-canonical/1.0'


def validate_operational_policy(policy, student_ids, advisor_ids):
    """Require explicit semester assertions rather than public-profile inference.

    Existing assignments must be represented as fixed rows in the SAME complete
    cohort. Otherwise the equal-division denominator is not known safely.
    """
    selected=policy.get('selected_advisor_ids',[])
    if (not str(policy.get('semester_id','')).strip() or policy.get('eligibility_confirmed') is not True
            or not str(policy.get('reviewer','')).strip() or not str(policy.get('policy_evidence_ref','')).strip()
            or not isinstance(selected,list) or not selected or len(set(selected))!=len(selected)
            or set(selected)-set(advisor_ids)):
        raise ValueError('confirmed_semester_policy_required')
    if policy.get('student_ids')!=list(student_ids) or policy.get('advisor_ids')!=list(advisor_ids):
        raise ValueError('policy_identity_order_mismatch')
    eligible=np.asarray(policy.get('eligibility'))
    if eligible.dtype!=np.bool_ or eligible.shape!=(len(student_ids),len(advisor_ids)):
        raise ValueError('explicit_pair_eligibility_required')
    fixed=policy.get('fixed_assignments',{})
    if (not isinstance(fixed,dict) or set(fixed)-set(student_ids) or set(fixed.values())-set(selected)):
        raise ValueError('invalid_fixed_assignments')
    loads=policy.get('existing_loads',{})
    if (not isinstance(loads,dict) or set(loads)!=set(selected)
            or any(type(v) is not int or v<0 for v in loads.values())):
        raise ValueError('confirmed_existing_load_required')
    counts=Counter(fixed.values())
    if any(loads[a]!=counts[a] for a in selected):
        raise ValueError('existing_load_requires_matching_fixed_assignments')
    return {'eligible':eligible.copy(),'selected_advisor_ids':sorted(selected),
            'fixed_assignments':dict(fixed),'capacities':equal_quotas(len(student_ids),advisor_ids,selected),
            'policy_version':POLICY_VERSION,'policy_sha256':record_hash(policy)}


def assemble_research_suite(features, students, splits, taxonomy, *, cohort_size=45):
    if type(cohort_size) is not int or cohort_size<1:
        raise ValueError('invalid_training_cohort_size')
    index=features['index']; student_ids=index['student_ids']; advisor_ids=index['advisor_ids']
    if (len(set(student_ids))!=len(student_ids) or len(set(advisor_ids))!=len(advisor_ids)
            or {r['student_id'] for r in students}!=set(student_ids)
            or set(splits['assignments'])!=set(student_ids)
            or set(splits['assignments'].values())!={'train','validation','test'}):
        raise ValueError('cohort_identity_or_split_mismatch')
    ordered={r['student_id']:r for r in students}
    members={name:[i for i,key in enumerate(student_ids) if splits['assignments'][key]==name]
             for name in ('train','validation','test')}
    selected=[key for j,key in enumerate(advisor_ids) if features['available'][members['train'],j].all()]
    if not selected:
        raise ValueError('no_training_scorable_research_catalog')
    tags=sorted((group,tag) for group,entries in taxonomy['groups'].items() for tag in entries)
    vectors=np.zeros((len(student_ids),len(tags)),np.float32)
    known=np.zeros_like(vectors,dtype=bool)
    for i,key in enumerate(student_ids):
        row=ordered[key]
        for j,(group,tag) in enumerate(tags):
            if tag in str(row.get(group) or '').split(';'):
                vectors[i,j]=1; known[i,j]=True
    present=np.array([a in selected for a in advisor_ids],dtype=bool)
    def problem(indices,split_name,name):
        ids=tuple(student_ids[i] for i in indices)
        metadata={'scope':'research_only','cohort_id':name,'split':split_name,
            'feature_contract_sha256':features['gate']['feature_contract_sha256'],
            'phase4_run_id':features['gate']['run_id'],'policy_version':POLICY_VERSION,
            'eligibility_assumption':'All selected catalog pairs provisionally eligible in offline simulation only.',
            'selected_advisor_ids':selected,'vector_semantics':'Source term presence only; missing terms unknown, not personal proficiency.',
            'taxonomy_feature_order_sha256':record_hash(tags),
            'student_ids_sha256':record_hash(list(ids))}
        return AllocationProblem(scores=features['scores'][indices],available=features['available'][indices],
            student_ids=ids,advisor_ids=tuple(advisor_ids),capacities=equal_quotas(len(indices),advisor_ids,selected),
            eligible=np.ones((len(indices),len(advisor_ids)),bool),present=present,
            student_features=vectors[indices],student_feature_known=known[indices],metadata=metadata)
    training=members['train']; count=max(1,(len(training)+cohort_size-1)//cohort_size)
    train=[problem(list(chunk),'train',f'train-{j:03d}') for j,chunk in enumerate(np.array_split(training,count))]
    return {'train':train,'validation':problem(members['validation'],'validation','validation'),
            'test':problem(members['test'],'test','test'),
            'metadata':{'scope':'research_only','operational_allocation_authorized':False,
                'selected_advisor_ids':selected,'advisor_registry':advisor_ids,'policy_version':POLICY_VERSION,
                'taxonomy_feature_order':[list(tag) for tag in tags],
                'taxonomy_feature_order_sha256':record_hash(tags),'split_policy':'P4 frozen non-temporal groups',
                'training_cohort_count':len(train),'training_cohort_sizes':[len(p.student_ids) for p in train],
                'limitations':['No confirmed current semester roster/eligibility input.',
                    'Resampling these disjoint student cohorts is not independent semester/outcome evidence.']}}


def build_research_suite(output):
    output=Path(output).resolve()
    features=load_approved_features(output)
    students,_,snapshot=_load_snapshot(output)
    if snapshot!=features['contract']['snapshot']:
        raise ValueError('cohort_source_snapshot_changed')
    phase4=Path(features['gate']['run_dir'])
    splits=json.loads((phase4/'splits.json').read_text(encoding='utf-8'))
    suite=assemble_research_suite(features,students,splits,load_taxonomy())
    suite['metadata'].update(phase4_run_id=features['gate']['run_id'],
        feature_contract_sha256=features['gate']['feature_contract_sha256'],snapshot=snapshot)
    return suite
