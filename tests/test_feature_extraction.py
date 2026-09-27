def test_tfidf_never_learns_holdout_vocabulary():
    from src.data_pipeline.feature_extractor import FeatureExtractor
    extractor = FeatureExtractor().fit(['machine learning', 'website application'])
    before = dict(extractor.vectorizer.vocabulary_)
    matrix = extractor.compatibility(['unknownsecret machine'], ['learning', 'website'])
    assert matrix.shape == (1, 2)
    assert extractor.vectorizer.vocabulary_ == before
    assert 'unknownsecret' not in before
    assert matrix.min() >= 0 and matrix.max() <= 1
