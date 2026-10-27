import importlib.util
from pathlib import Path

import numpy as np
import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'src/features/rebuild_features.py'
    spec = importlib.util.spec_from_file_location('phase4_features', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def students():
    return [{'student_id':'S12345678','student_name':'Canary Person', 'thesis_title':'Python language models',
             'thesis_abstract':'Neural language processing', 'topic_tags':'nlp', 'programming_languages':'python',
             'skill_confidence':'1'},
            {'student_id':'S87654321','student_name':'Other Person','thesis_title':'Web database systems',
             'thesis_abstract':'Relational database design','topic_tags':'databases','databases':'mysql',
             'skill_confidence':'1'}]


def advisors():
    return [{'advisor_id':'A1','advisor_name':'Faculty Canary','research_description':'Python language processing',
             'expertise_topic_tags':'nlp','programming_languages':'python','expertise_confidence':'0.8'},
            {'advisor_id':'A2','advisor_name':'Second Faculty','research_description':'Web database systems',
             'expertise_topic_tags':'databases','databases':'mysql','expertise_confidence':'1'}]


def test_train_only_vocabulary_and_frozen_idf():
    m = module(); pipe = m.FeaturePipeline().fit(students(), advisors())
    before = {k: v.idf_.copy() for k,v in pipe.vectorizers.items() if v is not None}
    holdout = [{**students()[0], 'thesis_title':'unseenholdouttoken'}]
    pipe.transform_score(holdout, advisors())
    for key, vectorizer in pipe.vectorizers.items():
        if vectorizer is not None:
            assert 'unseenholdouttoken' not in vectorizer.vocabulary_
            np.testing.assert_array_equal(before[key], vectorizer.idf_)


def test_identity_contacts_boilerplate_are_removed_from_text_and_features():
    m = module()
    text = 'Sinh viên: Canary Person\nMSSV: S12345678\nPython language canary@example.org +84 912 345 678 https://source.test/paper'
    cleaned, counts = m.preprocess_text(text, ['Canary Person','S12345678'])
    for term in ['canary','s12345678','example','912','source.test','sinh viên','mssv']:
        assert term not in cleaned.lower()
    assert 'Python language' in cleaned and sum(counts.values()) > 0
    rows = students(); rows[0]['thesis_title'] += ' Canary Person S12345678'
    pipe = m.FeaturePipeline().fit(rows, advisors())
    vocabulary = set(pipe.vectorizers['E1'].vocabulary_)
    assert not vocabulary & {'canary','person','s12345678','faculty'}


def test_missing_evidence_is_masked_and_no_proficiency_is_fabricated():
    m = module(); pipe = m.FeaturePipeline().fit(students(), advisors())
    unknown = [{**students()[0], 'skill_confidence':'', 'skill_proficiency_json':''}]
    result = pipe.transform_score(unknown, advisors())
    assert not result['available']['E3'].any()
    assert result['available']['E2'].all()
    assert result['components']['publications_available'] is False
    assert result['components']['proficiency_used'] is False
    assert unknown[0]['skill_proficiency_json'] == ''


def test_column_reordering_and_identity_mutations_do_not_change_scores():
    m = module(); pipe = m.FeaturePipeline().fit(students(), advisors())
    original = pipe.transform_score(students(), advisors())
    changed = [{**row,'student_name':'New Identity', 'student_id':'UNUSED'} for row in students()]
    reverse = pipe.transform_score(changed, list(reversed(advisors())))
    for key in original['scores']:
        np.testing.assert_allclose(original['scores'][key], reverse['scores'][key][:,::-1])
        assert np.isfinite(original['scores'][key]).all()
        assert ((original['scores'][key]>=0)&(original['scores'][key]<=1)).all()


def test_roundtrip_train_serve_parity_and_corrupted_artifact_fails(tmp_path):
    m = module(); pipe = m.FeaturePipeline().fit(students(), advisors())
    expected = pipe.transform_score(students(), advisors())
    pipe.save(tmp_path)
    identities = pipe.identities
    loaded = m.FeaturePipeline.load(tmp_path, known_identities=identities)
    actual = loaded.transform_score(students(), advisors())
    for key in expected['scores']: np.testing.assert_allclose(expected['scores'][key],actual['scores'][key])
    assert not list(tmp_path.glob('*.pkl'))
    (tmp_path/'idf.npz').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='artifact_hash'): m.FeaturePipeline.load(tmp_path,known_identities=identities)


def test_empty_vocabulary_and_unconfirmed_preferences_stay_unavailable():
    m=module(); pipe=m.FeaturePipeline().fit([{'thesis_title':''}],advisors())
    result=pipe.transform_score([{'preferred_advisor_ids':'A1','preferences_confirmed':False}],advisors())
    for key in ('E0','E1','E2','E3','E4'): assert not result['available'][key].any()
    assert not result['components']['preferences_available'].any()


def test_evidence_weighting_and_convex_hybrid_renormalize_known_components():
    m=module(); rows=students(); faculty=advisors()
    pipe=m.FeaturePipeline({'hybrid_weights':{'E1':0,'E2':0.5,'E3':0.5}}).fit(rows,faculty)
    result=pipe.transform_score(rows,faculty)
    assert result['scores']['E3'][0,0] == pytest.approx(np.sqrt(0.8))
    assert result['scores']['E4'][0,0] == pytest.approx((1+np.sqrt(0.8))/2)
    missing=[{**rows[0],'skill_confidence':''}]
    unknown=pipe.transform_score(missing,faculty)
    assert unknown['scores']['E4'][0,0] == 1
    assert unknown['components']['hybrid_denominator'][0,0] == 0.5
    no_tags=[{**rows[0],'programming_languages':'','topic_tags':''}]
    unavailable=pipe.transform_score(no_tags,faculty)
    assert not unavailable['available']['E3'].any() and not unavailable['available']['E4'].any()


def test_only_explicitly_confirmed_preference_can_contribute():
    m=module(); pipe=m.FeaturePipeline({'preference_weight':1}).fit(students(),advisors())
    row={**students()[0],'preferred_advisor_ids':'A2'}
    unconfirmed=pipe.transform_score([row],advisors())
    assert not unconfirmed['available']['E4'].any()
    confirmed=pipe.transform_score([{**row,'preferences_confirmed':True}],advisors())
    np.testing.assert_array_equal(confirmed['scores']['E4'],[[0,1]])


def test_raw_publications_contacts_and_provenance_never_enter_vocabulary():
    m=module(); rows=students(); faculty=advisors()
    for row in rows+faculty:
        row.update(profile_text='privateprofilecanary',publications='authorcanary',source_file='filenamecanary',
                   contacts_attribution_only='contactcanary',gpa='gradecanary',gender='gendercanary')
    pipe=m.FeaturePipeline().fit(rows,faculty)
    for vectorizer in pipe.vectorizers.values():
        assert not set(vectorizer.vocabulary_) & {'privateprofilecanary','authorcanary','filenamecanary','contactcanary','gradecanary','gendercanary'}


@pytest.mark.parametrize('quality',[True,False,float('nan'),float('inf'),'NaN','Infinity'])
def test_bool_and_nonfinite_quality_are_rejected(quality):
    m=module(); pipe=m.FeaturePipeline().fit(students(),advisors())
    with pytest.raises(ValueError,match='invalid_evidence_quality'):
        pipe.transform_score([{**students()[0],'skill_confidence':quality}],advisors())


def test_non_numeric_or_boolean_hybrid_weights_are_rejected():
    m=module()
    for value in (True,'1',float('nan')):
        with pytest.raises(ValueError,match='hybrid_weights'):
            m.FeaturePipeline({'hybrid_weights':{'E1':value,'E2':0,'E3':0}})
    with pytest.raises(ValueError,match='preference_weight'):
        m.FeaturePipeline({'preference_weight':True})


def test_sparse_profile_diagnostics_are_derived_from_availability():
    m=module(); pipe=m.FeaturePipeline().fit(students(),advisors())
    result=pipe.transform_score(students(),[{}])
    for key in result['scores']:
        diagnostic=result['components']['availability_diagnostics'][key]
        assert diagnostic['unavailable_pairs'] == 2
        assert diagnostic['advisors_without_available_students'] == 1
        assert diagnostic['students_without_available_candidates'] == 2


def test_pair_explanation_reconstructs_text_and_weighted_tag_scores():
    m = module(); rows, faculty = students(), advisors()
    pipe = m.FeaturePipeline().fit(rows, faculty)
    scores = pipe.transform_score(rows, faculty)
    explanation = pipe.explain_pair(rows[0], faculty[0])
    for key in ('E0', 'E1'):
        assert sum(item['contribution'] for item in explanation[key]['shared_terms']) == pytest.approx(scores['scores'][key][0,0])
    assert explanation['E3']['score'] == pytest.approx(scores['scores']['E3'][0,0])
    assert explanation['E3']['evidence_quality_factor'] == pytest.approx(np.sqrt(.8))
    assert explanation['E4']['score'] == pytest.approx(sum(explanation['E4']['contributions'].values()))
    assert explanation['E4']['score'] == pytest.approx(scores['scores']['E4'][0,0])
    missing = pipe.explain_pair({}, {})
    assert missing['E3']['score'] is None and missing['E4']['score'] is None
