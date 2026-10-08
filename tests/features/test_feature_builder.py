import numpy as np

from src.features.feature_builder import FeatureBuilder


def test_tfidf_is_fit_only_on_train_and_hash_is_reproducible():
    builder = FeatureBuilder()
    builder.fit(["python machine learning", "react web"], ["python data", "react frontend"])

    matrix_a, manifest_a = builder.compatibility(["holdout_secret python"], ["python data", "react frontend"])
    matrix_b, manifest_b = builder.compatibility(["holdout_secret python"], ["python data", "react frontend"])

    assert "holdout_secret" not in builder.vocabulary
    assert matrix_a.shape == (1, 2)
    assert np.array_equal(matrix_a, matrix_b)
    assert manifest_a == manifest_b
    assert len(manifest_a["matrix_sha256"]) == 64


def test_dense_embeddings_are_optional_and_dimension_checked():
    builder = FeatureBuilder().fit(["python"], ["python"])

    matrix, _ = builder.compatibility(
        ["python"],
        ["python"],
        student_dense=np.array([[1.0, 0.0]]),
        advisor_dense=np.array([[1.0, 0.0]]),
    )

    assert matrix[0, 0] == 1.0
