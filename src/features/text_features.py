from sklearn.feature_extraction.text import TfidfVectorizer


def create_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1, norm="l2")
