"""Conservative normalization preserves Vietnamese accents and technology names."""
import re
import unicodedata

STOP_WORDS = frozenset({'và', 'là', 'của', 'cho', 'với', 'các', 'những', 'một'})


def clean_text(text, *, segment=False):
    if not isinstance(text, str):
        raise ValueError('Text must be a string; missing values need explicit handling')  # noqa: TRY004 - public validation contract
    text = unicodedata.normalize('NFC', text).lower()
    tokens = re.findall(r'[\w.+#]+', text)
    normalized = ' '.join(token for token in tokens if token not in STOP_WORDS)
    if segment:
        from pyvi import ViTokenizer
        return ViTokenizer.tokenize(normalized)
    return normalized
