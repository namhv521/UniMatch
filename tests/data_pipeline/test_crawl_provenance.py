import csv
import hashlib
import json
from pathlib import Path

from src.data_pipeline.crawl.provenance import SnapshotStore
from src.data_pipeline.crawl.retry import retry_manual_queue


def test_snapshot_is_content_addressed_and_fetch_event_is_append_only(tmp_path):
    store = SnapshotStore(tmp_path, run_id="run-1")
    content = b"cached public profile"
    event = store.record(
        source_id="fit_lecturers",
        url="https://fit.neu.edu.vn/lecturer/example",
        content=content,
        outcome="success",
        http_status=200,
        content_type="text/html",
    )

    snapshot = tmp_path / "run-1" / "snapshots" / f"{hashlib.sha256(content).hexdigest()}.bin"
    assert snapshot.read_bytes() == content
    assert json.loads((tmp_path / "run-1" / "fetch_events.jsonl").read_text()) == event


def test_manual_retry_uses_user_url_preserves_history_and_resolves(tmp_path):
    queue = tmp_path / "manual_crawl_queue.csv"
    fields = [
        "queue_id", "advisor_id", "name_raw", "name_normalized", "attempted_urls",
        "last_attempt_at", "status", "failure_reason", "why_no_related_page",
        "suggested_search_queries", "user_provided_url", "assigned_at", "resolved_at",
    ]
    with queue.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "queue_id": "queue-1",
                "advisor_id": "advisor-1",
                "name_raw": "Advisor One",
                "name_normalized": "advisor one",
                "attempted_urls": '["https://old.example"]',
                "status": "manual_required",
                "user_provided_url": "https://new.example",
            }
        )

    retried = retry_manual_queue(
        queue,
        SnapshotStore(tmp_path / "raw", run_id="retry-1"),
        fetcher=lambda url: (200, "text/html", b"profile"),
    )

    assert retried == 1
    row = next(csv.DictReader(queue.open(encoding="utf-8")))
    assert row["status"] == "resolved"
    assert json.loads(row["attempted_urls"]) == ["https://old.example", "https://new.example"]
    assert row["resolved_at"]
