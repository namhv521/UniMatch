"""Portable serving release rejects tampering and unsafe archive members."""
import hashlib
import io
import json
import tarfile

import pytest


def archive(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, payload in files.items():
            item = tarfile.TarInfo(name); item.size = len(payload)
            tar.addfile(item, io.BytesIO(payload))
    return output.getvalue()


def test_release_unpack_verifies_bytes_before_writing(tmp_path):
    from backend.app.production_release import unpack_release
    payload = b'{}'
    manifest = json.dumps({'schema': 'unimatch-serving/1', 'files': {'catalog.json': hashlib.sha256(payload).hexdigest()}}).encode()
    body = archive({'release.json': manifest, 'catalog.json': payload})
    folder = unpack_release(body, hashlib.sha256(body).hexdigest(), tmp_path)
    assert (folder/'catalog.json').read_bytes() == payload
    with pytest.raises(ValueError, match='release_hash_mismatch'):
        unpack_release(body+b'x', hashlib.sha256(body).hexdigest(), tmp_path)


def test_release_unpack_rejects_traversal(tmp_path):
    from backend.app.production_release import unpack_release
    body = archive({'../escape': b'x'})
    with pytest.raises(ValueError, match='release_archive_invalid'):
        unpack_release(body, hashlib.sha256(body).hexdigest(), tmp_path)
    assert not (tmp_path.parent/'escape').exists()
