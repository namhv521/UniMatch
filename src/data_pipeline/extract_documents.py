"""Extract local PDF/DOCX text with page-level provenance and resumable manifests."""
import argparse
import hashlib
import json
import unicodedata
from pathlib import Path


def canonical(text):
    return ' '.join(unicodedata.normalize('NFC', text).split()).casefold()


def validate_evidence(evidence, pages):
    sources = {row['page']: canonical(row['text']) for row in pages}
    for item in evidence:
        if item['page'] not in sources or not canonical(item['quote']):
            raise ValueError('Evidence has no source page or quote')
        if canonical(item['quote']) not in sources[item['page']]:
            raise ValueError('Evidence quote is absent from its claimed page')
    return True


def extract_pages(path):
    path = Path(path)
    if path.suffix.lower() == '.pdf':
        import fitz
        with fitz.open(path) as document:
            if document.needs_pass:
                raise ValueError('Encrypted document')
            return [{'page': index + 1, 'text': page.get_text(sort=True)}
                    for index, page in enumerate(document)]
    if path.suffix.lower() == '.docx':
        from xml.etree import ElementTree
        from zipfile import ZipFile
        # Extract text without loading unrelated/broken hyperlink/image relationships.
        with ZipFile(path) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 50_000_000:
                raise ValueError('DOCX document XML exceeds extraction size limit')
            root = ElementTree.fromstring(archive.read(info))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        blocks = [''.join(node.text or '' for node in paragraph.findall('.//w:t', ns))
                  for paragraph in root.findall('.//w:p', ns)]
        return [{'page': index + 1, 'text': text} for index, text in enumerate(blocks)]
    raise ValueError('Unsupported format; archives require explicit extraction audit')


def build_manifest(source, target):
    source, target = Path(source), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    seen = {}
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = {'source_file': path.name, 'sha256': digest, 'bytes': path.stat().st_size,
               'format': path.suffix.lower(), 'status': 'unsupported'}
        if digest in seen:
            row.update(status='duplicate', duplicate_of=seen[digest])
        elif path.suffix.lower() in ('.pdf', '.docx'):
            cache = target / f'{digest}.json'
            try:
                if cache.exists():
                    artifact = json.loads(cache.read_text(encoding='utf-8'))
                else:
                    pages = extract_pages(path)
                    artifact = {'sha256': digest, 'source_file': path.name,
                                'location_unit': 'page' if path.suffix.lower() == '.pdf' else 'text_block',
                                'pages': pages}
                    cache.write_text(json.dumps(artifact, ensure_ascii=False), encoding='utf-8')
                characters = sum(len(p['text'].strip()) for p in artifact['pages'])
                row.update(status='extracted' if characters >= 100 else 'needs_ocr',
                           characters=characters, pages=len(artifact['pages']), cache=str(cache))
            except Exception as exc:  # noqa: BLE001 - record per-document parser failures and continue the batch
                row.update(status='error', error_type=type(exc).__name__)
        seen[digest] = path.name
        manifest.append(row)
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('data/1.pdfs'))
    parser.add_argument('--output', type=Path, default=Path('data/extracted/documents'))
    args = parser.parse_args()
    from collections import Counter
    manifest = build_manifest(args.source, args.output)
    print(json.dumps(dict(Counter(row['status'] for row in manifest)), indent=2))


if __name__ == '__main__':
    main()
