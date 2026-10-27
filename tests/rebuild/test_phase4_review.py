import hashlib
import json

import pytest


def test_blinded_advisory_mapping_requires_complete_exact_source_evidence(tmp_path):
    from src.evaluation.rebuild_review import map_advisory_labels
    binding = {'student_id': 'fixture-student', 'advisor_id': 'fixture-advisor',
               'student_record_sha256': 'a'*64, 'advisor_record_sha256': 'b'*64, 'snapshot_sha256': 'c'*64}
    from src.data_pipeline.review_decisions import record_hash
    key = record_hash(binding)
    pair = {'pair_id': key, 'student_title': 'Cloud data systems', 'student_abstract': '',
            'advisor_profile': 'Cloud systems and data engineering'}
    (tmp_path / 'blinded_pairs.jsonl').write_text(json.dumps(pair)+'\n')
    (tmp_path / 'pair_bindings.json').write_text(json.dumps({key: binding}))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = tmp_path / 'packet_manifest.json'
    manifest.write_text(json.dumps({'blinded_pairs_sha256': digest(tmp_path/'blinded_pairs.jsonl'),
                                    'pair_bindings_sha256': digest(tmp_path/'pair_bindings.json')}))
    proposal = {'pair_id': key, 'grade': 2, 'reviewer': 'agent:fixture', 'attribution': 'agent_advisory',
                'packet_manifest_sha256': digest(manifest), 'reason': 'Explicit shared topic in technical fixture.',
                'student_evidence': ['Cloud data systems'], 'advisor_evidence': ['Cloud systems']}
    rows = map_advisory_labels(tmp_path, [proposal])
    assert rows[0]['student_id'] == 'fixture-student' and rows[0]['grade'] == 2
    proposal['advisor_evidence'] = ['Invented source text']
    with pytest.raises(ValueError, match='unsupported_advisory_evidence'):
        map_advisory_labels(tmp_path, [proposal])
    with pytest.raises(ValueError, match='review_pair_coverage_mismatch'):
        map_advisory_labels(tmp_path, [])


def test_crosscheck_preserves_disagreement_as_unknown_without_promoting_authority():
    from src.evaluation.rebuild_review import combine_advisory_reviews
    primary = [{'pair_id':'a', 'grade':3, 'reviewer':'agent:first', 'attribution':'agent_advisory', 'reason':'Specific claim'},
               {'pair_id':'b', 'grade':1, 'reviewer':'agent:first', 'attribution':'agent_advisory', 'reason':'Broad claim'}]
    second = [{'pair_id':'a', 'grade':2, 'reviewer':'agent:second', 'attribution':'agent_advisory', 'reason':'Domain only'},
              {'pair_id':'b', 'grade':1, 'reviewer':'agent:second', 'attribution':'agent_advisory', 'reason':'Broad match'}]
    combined, audit = combine_advisory_reviews(primary, second)
    assert combined[0]['grade'] == 'uncertain' and combined[1]['grade'] == 1
    assert primary[0]['grade'] == 3
    assert combined[0]['attribution'] == 'agent_advisory'
    assert audit['exact_agreement'] == .5 and audit['sampled_pairs'] == 2
    assert audit['mean_absolute_grade_difference'] == .5
    with pytest.raises(ValueError, match='independent_reviewer_required'):
        combine_advisory_reviews(primary, primary[:1])
    with pytest.raises(ValueError, match='unknown_crosscheck_pair'):
        combine_advisory_reviews(primary, [{**second[0], 'pair_id':'outside'}])
