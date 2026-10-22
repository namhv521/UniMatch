"""Word evidence blocks and bounded archive expansion into private rebuild storage."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import threading
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
SUPPORTED_MEMBERS = {'.pdf', '.docx', '.rar', '.zip'}
PARSER_VERSION = 'document-sources-v1'
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


def _sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract_docx(path: Path, source_ref: dict, *, max_xml_bytes: int = 64 * 1024 * 1024) -> list[dict]:
    """Extract main-document paragraphs, including tables, with stable XML locations.

    Page numbers are deliberately absent: OOXML paragraph order does not prove
    rendered pagination. Headers/footers are not used as student-profile evidence.
    """
    path = Path(path)
    source_hash = _sha(path)
    if source_ref.get('source_sha256') and source_ref['source_sha256'] != source_hash:
        raise ValueError('source_hash_mismatch')
    source_identity = source_ref.get('source_id') or f"{source_ref.get('source_file', path.as_posix())}:{source_hash}"
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('word/document.xml')
        if info.file_size > max_xml_bytes:
            raise ValueError('document_xml_size_limit')
        with archive.open(info) as stream:
            data = stream.read(max_xml_bytes + 1)
    if len(data) > max_xml_bytes:
        raise ValueError('document_xml_size_limit')
    declaration_bytes = data.replace(b'\x00', b'').upper()
    if b'<!DOCTYPE' in declaration_bytes or b'<!ENTITY' in declaration_bytes:
        raise ValueError('xml_entities_not_allowed')
    document = ET.fromstring(data)
    blocks = []

    def visit(node: ET.Element, locator: str) -> None:
        if node.tag == f'{{{WORD_NS}}}p':
            parts = []
            for item in node.iter():
                if item.tag == f'{{{WORD_NS}}}t':
                    parts.append(item.text or '')
                elif item.tag == f'{{{WORD_NS}}}tab':
                    parts.append('\t')
                elif item.tag in {f'{{{WORD_NS}}}br', f'{{{WORD_NS}}}cr'}:
                    parts.append('\n')
            text = ''.join(parts).strip()
            if text:
                block_id = hashlib.sha256(f'{source_identity}:{source_hash}:{locator}:{text}'.encode('utf-8')).hexdigest()
                blocks.append({**source_ref, 'kind': 'block', 'block_id': block_id,
                               'text': text, 'locator': locator,
                               'source_file': source_ref.get('source_file', path.as_posix()),
                               'source_sha256': source_hash, 'extraction_method': 'docx_ooxml',
                               'parser_version': PARSER_VERSION, 'confidence': None})
            return
        counts = Counter()
        for child in node:
            tag = child.tag.rsplit('}', 1)[-1]
            counts[tag] += 1
            visit(child, f'{locator}/{tag}[{counts[tag]}]')

    visit(document, '/document[1]')
    if _sha(path) != source_hash:
        raise ValueError('source_changed_during_extraction')
    return blocks


def _member_path(name: str) -> tuple[PurePosixPath | None, str]:
    value = name.replace('\\', '/')
    normalized = unicodedata.normalize('NFKC', value)
    parts = normalized.rstrip('/').split('/')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if (not value or normalized.startswith('/') or any(not p or p in {'.', '..'} for p in parts)
            or any(any(c in p for c in ':*?\x00\r\n') or p.endswith((' ', '.'))
                   or p.split('.')[0].upper() in reserved for p in parts)):
        return None, ''
    return PurePosixPath(value.rstrip('/')), '/'.join(parts).casefold()


def _bounded_command(command: list[str], limit: int, timeout: int) -> bytes:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    expired = threading.Event()

    def expire() -> None:
        expired.set()
        process.kill()

    timer = threading.Timer(timeout, expire)
    timer.daemon = True
    timer.start()
    chunks, size = [], 0
    try:
        while chunk := process.stdout.read(65536):
            size += len(chunk)
            if size > limit:
                process.kill()
                raise ValueError('command_output_size_limit')
            chunks.append(chunk)
        code = process.wait()
        if expired.is_set():
            raise TimeoutError('archive_command_timeout')
        if code != 0:
            raise ValueError(f'archive_command_exit_{code}')
        return b''.join(chunks)
    finally:
        timer.cancel()
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


def _unrar() -> str:
    executable = shutil.which('unrar') or shutil.which('UnRAR.exe')
    fallback = Path('C:/Program Files/WinRAR/UnRAR.exe')
    if not executable and fallback.is_file():
        executable = str(fallback)
    if not executable:
        raise FileNotFoundError('unrar_not_available')
    return executable


def _rar_members(path: Path, timeout: int) -> tuple[list[dict], str]:
    executable = _unrar()
    data = _bounded_command([executable, 'lt', '-c-', '-p-', '-scu', '-@', '--', str(path)], 8 * 1024 * 1024, timeout)
    # Native Windows UnRAR -scu is UTF-16LE. Non-Windows builds use UTF-8.
    text = data.decode('utf-16-le' if os.name == 'nt' else 'utf-8')
    records, current = [], {}
    for line in text.splitlines() + ['']:
        if not line.strip():
            if 'Name' in current:
                records.append(current)
            current = {}
        elif ': ' in line:
            key, value = line.lstrip().split(': ', 1)
            current[key] = value
    version = next((line.strip() for line in text.splitlines() if line.startswith('UNRAR ')), 'UnRAR version unavailable')
    members = []
    for record in records:
        kind = record.get('Type', '')
        members.append({'name': record['Name'], 'size': int(record.get('Size', '0')),
                        'directory': kind == 'Directory',
                        'link': kind not in {'File', 'Directory'} or any('redirect' in k.lower() or 'target' in k.lower() for k in record),
                        'encrypted': 'encrypted' in record.get('Flags', '').lower(), 'native': record})
    return members, version


def expand_archive(path: Path, dest: Path, *, max_member_bytes: int = MAX_MEMBER_BYTES,
                   max_total_bytes: int = MAX_TOTAL_BYTES, max_members: int = 2000,
                   timeout: int = 30) -> list[dict]:
    """Manifest every member; extract documents/archives only, never native paths.

    Recursion belongs to the caller, which retains the original source and
    parent archive hash chain and applies a whole-run recursion/byte budget.
    """
    path, dest = Path(path).resolve(), Path(dest)
    if dest.is_symlink():
        raise ValueError('destination_symlink_not_allowed')
    dest = dest.resolve()
    if path == dest or path in dest.parents or dest in path.parents:
        raise ValueError('archive_and_destination_must_be_disjoint')
    dest.mkdir(parents=True, exist_ok=True)
    source_hash = _sha(path)
    archive = None
    try:
        if path.suffix.lower() == '.zip':
            archive = zipfile.ZipFile(path)
            members = [{'name': i.filename, 'size': i.file_size, 'directory': i.is_dir(),
                        'link': stat.S_ISLNK(i.external_attr >> 16), 'encrypted': bool(i.flag_bits & 1),
                        'native': i} for i in archive.infolist()]
            parser = 'python_zipfile'
            version = sys.version.split()[0]
        elif path.suffix.lower() == '.rar':
            members, version = _rar_members(path, timeout)
            parser = 'unrar'
        else:
            raise ValueError('unsupported_archive_format')
        keys = [_member_path(member['name'])[1] for member in members]
        counts = Counter(k for k in keys if k)
        total_declared = sum(member['size'] for member in members)
        rows, actual_total = [], 0
        for member, key in zip(members, keys):
            row = {'member_path': member['name'], 'status': 'quarantined', 'reason': '',
                   'member_sha256': None, 'size_bytes': member['size'], 'parser': parser,
                   'parser_version': version, 'archive_sha256': source_hash}
            rows.append(row)
            relative, _ = _member_path(member['name'])
            if relative is None:
                row['reason'] = 'unsafe_member_path'
            elif member['link']:
                row['reason'] = 'link_not_allowed'
            elif counts[key] > 1:
                row['reason'] = 'normalized_path_collision'
            elif len(members) > max_members:
                row['reason'] = 'archive_member_count_limit'
            elif total_declared > max_total_bytes:
                row['reason'] = 'archive_total_size_limit'
            elif member['encrypted']:
                row['reason'] = 'encrypted_member'
            elif member['directory']:
                row['status'] = 'directory'
            elif member['size'] > max_member_bytes:
                row['reason'] = 'member_size_limit'
            elif relative.suffix.lower() not in SUPPORTED_MEMBERS:
                row['reason'] = 'unsupported_format'
            else:
                target = dest.joinpath(*relative.parts)
                if dest not in target.resolve().parents or any(p.is_symlink() for p in [target, *target.parents] if p != dest.parent):
                    row['reason'] = 'unsafe_destination_path'
                    continue
                try:
                    if archive is not None:
                        with archive.open(member['native']) as stream:
                            content = stream.read(max_member_bytes + 1)
                    else:
                        content = _bounded_command([_unrar(), 'p', '-inul', '-p-', '-@', '--', str(path), member['name']], max_member_bytes, timeout)
                    actual_total += len(content)
                    if len(content) > max_member_bytes or actual_total > max_total_bytes:
                        raise ValueError('actual_byte_limit')
                    if len(content) != member['size']:
                        raise ValueError('member_size_mismatch')
                    digest = hashlib.sha256(content).hexdigest()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        if not target.is_file() or _sha(target) != digest:
                            row['reason'] = 'existing_file_conflict'
                            continue
                    else:
                        with target.open('xb') as stream:
                            stream.write(content)
                    row.update(status='extracted', member_sha256=digest, extracted_path=target.as_posix())
                except Exception as exc:
                    row.update(status='failed', reason=f'{type(exc).__name__}:{exc}' if isinstance(exc, ValueError) else type(exc).__name__)
        if _sha(path) != source_hash:
            raise ValueError('archive_changed_during_expansion')
        return rows
    finally:
        if archive is not None:
            archive.close()
