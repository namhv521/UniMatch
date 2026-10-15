import hashlib
import sys
from types import SimpleNamespace

import pytest

from backend.app.artifacts import artifact_target, restore_artifacts


@pytest.mark.parametrize("path", ["../.env", "/tmp/file.json", "data/curated/../../../.env", "data\\curated\\x.json", "outputs/runtime/sessions.json", "data/curated/x.py"])
def test_artifacts_reject_non_serving_paths(tmp_path, path):
    with pytest.raises(ValueError):
        artifact_target(tmp_path, path)


def test_corrupt_bundle_never_writes_files(tmp_path, monkeypatch):
    rows = [("data/curated/a.json", hashlib.sha256(b"good").hexdigest(), b"good"),
            ("data/curated/b.json", "0" * 64, b"corrupt")]
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, *_): return SimpleNamespace(fetchall=lambda: rows)
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda *a, **k: Connection()))
    with pytest.raises(RuntimeError, match="integrity"):
        restore_artifacts(tmp_path, "unused", "v1")
    assert not list(tmp_path.rglob("*.json"))
