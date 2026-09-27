from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class SnapshotStore:
    def __init__(self, root: Path, run_id: str | None = None) -> None:
        self.run_id = run_id or str(uuid4())
        self.run_root = root / self.run_id
        self.snapshots = self.run_root / "snapshots"
        self.events = self.run_root / "fetch_events.jsonl"
        self.snapshots.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        source_id: str,
        url: str,
        content: bytes,
        outcome: str,
        http_status: int | None,
        content_type: str | None,
        error_code: str | None = None,
    ) -> dict[str, object]:
        content_hash = hashlib.sha256(content).hexdigest()
        snapshot = self.snapshots / f"{content_hash}.bin"
        if not snapshot.exists():
            snapshot.write_bytes(content)
        event: dict[str, object] = {
            "fetch_id": str(uuid4()),
            "run_id": self.run_id,
            "source_id": source_id,
            "url": url,
            "requested_at": datetime.now(UTC).isoformat(),
            "http_status": http_status,
            "content_type": content_type,
            "content_sha256": content_hash,
            "parser_version": "1.0.0",
            "outcome": outcome,
            "error_code": error_code,
        }
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event
