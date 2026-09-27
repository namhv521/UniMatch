"""Extract only PDF/DOCX members, flatten paths, retain archive/member provenance."""
import hashlib
import json
import subprocess
from pathlib import Path

from .extract_documents import build_manifest


def main():
    executable = Path('C:/Program Files/WinRAR/UnRAR.exe')
    if not executable.is_file():
        raise SystemExit('Local UnRAR is required for supplied RAR documents')
    root = Path('data/extracted/archives').resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = Path('data/extracted/documents/manifest.json')
    original = json.loads(manifest_path.read_text(encoding='utf-8'))
    records = [row for row in original if not row.get('archive_sha256')]
    report = []
    for archive in sorted(Path('data/1.pdfs').glob('*.rar')):
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        target = (root / digest).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Archive destination escaped authorized root')
        target.mkdir(exist_ok=True)
        result = subprocess.run([str(executable), 'e', '-idq', '-o-', '-p-', str(archive.resolve()),
                                 '*.pdf', '*.docx', str(target) + '/'], capture_output=True, timeout=120, check=False)
        extracted = build_manifest(target, Path('data/extracted/documents'))
        for row in extracted:
            row['archive_sha256'] = digest
            row['archive_file'] = archive.name
            row['source_file'] = archive.name + '/' + row['source_file']
        records.extend(extracted)
        report.append({'archive': archive.name, 'sha256': digest, 'exit_code': result.returncode,
                       'documents': len(extracted), 'nested_archives': 'not executed or extracted'})
    seen = {}
    for row in records:
        if row['status'] == 'extracted':
            if row['sha256'] in seen:
                row.update(status='duplicate', duplicate_of=seen[row['sha256']])
            else:
                seen[row['sha256']] = row['source_file']
    manifest_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'archive_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'archives': len(report), 'archive_documents': sum(row['documents'] for row in report),
                      'unique_extracted_documents': sum(row['status'] == 'extracted' for row in records)}, indent=2))


if __name__ == '__main__':
    main()
