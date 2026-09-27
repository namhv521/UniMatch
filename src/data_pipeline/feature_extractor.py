"""Fit on training text only; use the same frozen transform everywhere else."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FeatureExtractor:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=10000)

    def fit(self, train_texts):
        self.vectorizer.fit(train_texts)
        return self

    def compatibility(self, student_texts, advisor_texts):
        students = self.vectorizer.transform(student_texts)
        advisors = self.vectorizer.transform(advisor_texts)
        return np.clip(cosine_similarity(students, advisors), 0, 1)
