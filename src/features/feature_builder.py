from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Self

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .text_features import create_vectorizer


def validate_advisor_source(root: str | Path, *, required: bool = True) -> None:
    """Verify that curated advisor profiles match the frozen quality report."""
    root = Path(root)
    advisor_path = root / "data/curated/advisors.json"
    quality_path = root / "data/curated/quality_report_v2.json"
    if not quality_path.is_file():
        if required:
            raise ValueError("advisor source quality report is missing")
        return
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        expected = quality["input_files"]["data/curated/advisors.json"]
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("advisor source hash is missing from quality report") from exc
    if not advisor_path.is_file():
        raise ValueError("advisor source file is missing")
    if hashlib.sha256(advisor_path.read_bytes()).hexdigest() != expected:
        raise ValueError("advisor source hash does not match quality report")


def _hash_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class FeatureBuilder:
    def __init__(self) -> None:
        self.vectorizer = create_vectorizer()
        self._train_sha256: str | None = None

    @property
    def vocabulary(self) -> dict[str, int]:
        return dict(self.vectorizer.vocabulary_)

    def fit(self, train_texts: list[str], advisor_texts: list[str]) -> Self:
        if not train_texts or not advisor_texts:
            raise ValueError("train and advisor texts are required")
        corpus = [*train_texts, *advisor_texts]
        self.vectorizer.fit(corpus)
        self._train_sha256 = _hash_json(corpus)
        return self

    def compatibility(
        self,
        student_texts: list[str],
        advisor_texts: list[str],
        *,
        student_dense: np.ndarray | None = None,
        advisor_dense: np.ndarray | None = None,
    ) -> tuple[np.ndarray, dict[str, object]]:
        if self._train_sha256 is None:
            raise RuntimeError("fit must be called before compatibility")
        text_scores = cosine_similarity(
            self.vectorizer.transform(student_texts),
            self.vectorizer.transform(advisor_texts),
        )
        method = "tfidf"
        scores = text_scores
        if student_dense is not None or advisor_dense is not None:
            if student_dense is None or advisor_dense is None:
                raise ValueError("both dense matrices are required")
            if student_dense.shape[0] != len(student_texts) or advisor_dense.shape[0] != len(advisor_texts):
                raise ValueError("dense row counts must match entities")
            if student_dense.shape[1] != advisor_dense.shape[1]:
                raise ValueError("dense dimensions must match")
            scores = (text_scores + cosine_similarity(student_dense, advisor_dense)) / 2
            method = "tfidf+dense"
        scores = np.asarray(scores, dtype=np.float64)
        manifest = {
            "schema_version": "1.0",
            "method": method,
            "train_corpus_sha256": self._train_sha256,
            "vocabulary_sha256": _hash_json(self.vocabulary),
            "matrix_shape": list(scores.shape),
            "matrix_sha256": hashlib.sha256(scores.tobytes(order="C")).hexdigest(),
        }
        return scores, manifest
