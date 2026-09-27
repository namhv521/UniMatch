import unicodedata


def test_unicode_normalization_and_technical_terms():
    from src.nlp.vietnamese_cleaner import clean_text
    assert clean_text(unicodedata.normalize('NFD', '  HỌC máy\n và AI  ')) == 'học máy ai'
    assert clean_text('C++ C# .NET') == 'c++ c# .net'
    assert clean_text('') == ''
def test_optional_vietnamese_segmentation_preserves_content():
    from src.nlp.vietnamese_cleaner import clean_text
    result = clean_text('Trường đại học bách khoa Hà Nội', segment=True)
    assert '_' in result
    assert result.replace('_', ' ') == 'trường đại học bách khoa hà nội'

