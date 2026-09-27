from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from .provenance import SnapshotStore


FetchResult = tuple[int, str, bytes]
Fetcher = Callable[[str], FetchResult]


def fetch_public_url(url: str) -> FetchResult:
    request = Request(url, headers={"User-Agent": "KLTN-research-crawler/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.status, response.headers.get_content_type(), response.read()


def retry_manual_queue(queue_path: Path, store: SnapshotStore, fetcher: Fetcher = fetch_public_url) -> int:
    with queue_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    retried = 0
    for row in rows:
        url = row.get("user_provided_url", "").strip()
        if not url or row.get("status") == "resolved":
            continue
        attempted = json.loads(row.get("attempted_urls") or "[]")
        attempted.append(url)
        now = datetime.now(UTC).isoformat()
        try:
            status, content_type, content = fetcher(url)
            success = 200 <= status < 300 and bool(content)
            store.record(
                source_id="user_provided",
                url=url,
                content=content,
                outcome="success" if success else "still_failed",
                http_status=status,
                content_type=content_type,
                error_code=None if success else "http_error",
            )
            row["status"] = "resolved" if success else "still_failed"
            row["failure_reason"] = "" if success else f"HTTP {status}"
            row["resolved_at"] = now if success else ""
        except Exception as exc:
            store.record(
                source_id="user_provided",
                url=url,
                content=b"",
                outcome="network_error",
                http_status=None,
                content_type=None,
                error_code=type(exc).__name__,
            )
            row["status"] = "still_failed"
            row["failure_reason"] = type(exc).__name__
        row["attempted_urls"] = json.dumps(attempted, ensure_ascii=False)
        row["last_attempt_at"] = now
        retried += 1
    with queue_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return retried
