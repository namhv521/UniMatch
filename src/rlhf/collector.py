from __future__ import annotations
import json
from pathlib import Path
from .preferences import PreferenceRecord

def load_preferences(path: Path) -> list[PreferenceRecord]:
    path = Path(path)
    if not path.exists(): return []
    return [PreferenceRecord.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

def append_preference(path: Path, record: PreferenceRecord) -> None:
    path = Path(path)
    records = load_preferences(path)
    if record.record_id in {item.record_id for item in records}:
        raise ValueError("duplicate preference record ID")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
