import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.data_pipeline.crawl.provenance import SnapshotStore
from src.data_pipeline.crawl.retry import retry_manual_queue


def main() -> None:
    root = Path(__file__).parents[1]
    count = retry_manual_queue(
        root / "data/manual_crawl_queue.csv",
        SnapshotStore(root / "data/raw/crawl_snapshots"),
    )
    print(f"retried={count}")


if __name__ == "__main__":
    main()
