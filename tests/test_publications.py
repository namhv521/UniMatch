def test_normalized_name_does_not_merge_distinct_people():
    from src.data_pipeline.merge_publications import identity_name, link_declarant
    profiles = [{'advisor_id': 'a', 'advisor_name': 'PGS.TS. Nguyễn Văn An'},
                {'advisor_id': 'b', 'advisor_name': 'TS. Nguyễn Văn Anh'}]
    assert identity_name('Nguyễn Văn An (003.037.123)') == 'nguyễn văn an'
    assert link_declarant('Nguyễn Văn An (003.037.123)', profiles) == 'a'
    assert link_declarant('Nguyễn Văn', profiles) is None
    assert link_declarant('Nguyễn Văn An', profiles + profiles[:1]) is None
