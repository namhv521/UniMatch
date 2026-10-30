"""Technical fixtures for source-bound two-advisor updates; no invented real skills."""
import copy
import hashlib
import json

import pytest

from src.data_pipeline.normalization import load_taxonomy
from src.features.github_enrichment import merge_advisors, load_training_bundle


THANG = 'fit_992239a385b6475451e8'
VIET = 'fit_5a04416402925947eef7'


@pytest.fixture
def inputs():
    base = [{'advisor_id': key, 'advisor_name': 'Technical '+key[-3:],
             'source_url': 'https://fit.neu.edu.vn/lecturer/technical-fixture',
             'source_sha256': 'a'*64, 'research_description': '', 'review_status': 'approved',
             'expertise_proficiency_json': '', 'capacity_max': '', 'active_for_semester': ''}
            for key in (THANG, VIET, 'unchanged')]
    supplements = [{'advisor_id': key, 'github_username': username,
                    'identity_mapping': 'owner_confirmed', 'personal_proficiency': None,
                    'tags': {'programming_languages': ['python'], 'topic_tags': ['nlp']},
                    'research_description': 'Do not trust this unreviewed summary',
                    'evidence_refs': [key+'-ev']}
                   for key, username in ((THANG, 'nhthang9x'), (VIET, 'vietnh1009'))]
    evidence = [{'evidence_id': key+'-ev', 'advisor_id': key,
                 'group': 'programming_languages', 'tag': 'python',
                 'excerpt': 'import Python', 'matched_text': 'Python',
                 'start': 7, 'end': 13, 'source_sha256': 'b'*64,
                 'source_url': 'https://raw.githubusercontent.com/technical/repo/'+'c'*40+'/main.py',
                 'evidence_class': 'code_import', 'commit_sha': 'c'*40, 'locator': 'main.py:chars:7:13'}
                for key in (THANG, VIET)]
    review = {'status': 'verified', 'source_manifest_sha256': 'd'*64,
              'approved_units': [{'advisor_id': key, 'group': 'programming_languages', 'tag': 'python',
                                  'evidence_ids': [key+'-ev'],
                                  'checks': {'source': 'pass', 'span': 'pass', 'semantic': 'pass'}}
                                 for key in (THANG, VIET)]}
    return base, supplements, evidence, review


def merge(inputs):
    return merge_advisors(*inputs, taxonomy=load_taxonomy(), github_manifest_sha256='d'*64,
                          quality_review_sha256='e'*64)


def test_only_reviewed_evidence_changes_exact_two_profiles_preserving_primary_identity_and_unknowns(inputs):
    original = copy.deepcopy(inputs[0])
    result = merge(inputs)
    assert inputs[0] == original and result[2] == original[2]
    for before, after in zip(original[:2], result[:2]):
        for field in ('advisor_id', 'advisor_name', 'source_url', 'source_sha256',
                      'expertise_proficiency_json', 'capacity_max', 'active_for_semester'):
            assert before[field] == after[field]
        assert after['programming_languages'] == 'python'
        assert not after.get('expertise_topic_tags')
        assert after['research_description'] == 'import Python'
        assert float(after['expertise_confidence']) == .5
        envelope = json.loads(after['expertise_evidence_refs'])
        assert envelope['source_manifest_sha256'] == 'd'*64
        assert len(envelope['refs']) == 1


@pytest.mark.parametrize('mutation', ['foreign_id', 'wrong_tag', 'unreviewed', 'proficiency', 'wrong_manifest'])
def test_unbound_or_invented_enrichment_fails_closed(inputs, mutation):
    base, supplements, evidence, review = inputs
    if mutation == 'foreign_id': supplements[0]['advisor_id'] = 'foreign'
    if mutation == 'wrong_tag': evidence[0]['tag'] = 'java'
    if mutation == 'unreviewed': review['approved_units'][0]['checks']['semantic'] = 'pending'
    if mutation == 'proficiency': supplements[0]['personal_proficiency'] = {'python': 5}
    if mutation == 'wrong_manifest': review['source_manifest_sha256'] = 'f'*64
    with pytest.raises(ValueError): merge(inputs)


def test_loading_requires_manifest_bound_bundle_and_rejects_tamper(tmp_path):
    bundle = tmp_path/'training_bundle.json'
    value = {'schema_version': 'github-advisor-training-bundle/1.0', 'source_artifacts': []}
    bundle.write_text(json.dumps(value), encoding='utf-8')
    manifest = {'gate': {'status': 'verified'}, 'artifacts': [
        {'path': bundle.name, 'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest()}]}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    assert load_training_bundle(bundle)['schema_version'] == value['schema_version']
    bundle.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError): load_training_bundle(bundle)
