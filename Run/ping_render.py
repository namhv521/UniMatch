"""Send periodic HTTP health checks to the UniMatch Render service."""

import argparse
import json
from datetime import datetime
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_URL = "https://unimatch-portal.onrender.com/health"


def check_health(request):
    with urlopen(request, timeout=90) as response:
        status = response.status
        content_type = response.headers.get_content_type()
        if status != 200 or content_type != "application/json":
            return False, f"HTTP {status}, {content_type}; expected readiness JSON"
        try:
            snapshot = json.loads(response.read(8192))
        except (ValueError, UnicodeError):
            return False, "HTTP 200, invalid readiness JSON"
    if not isinstance(snapshot, dict) or snapshot.get("status") != "ready":
        return False, "HTTP 200, API not ready"
    return True, "HTTP 200, API ready"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Health endpoint URL.")
    parser.add_argument("--interval-seconds", type=int, default=600,
                        help="Seconds between checks (default: 600).")
    parser.add_argument("--once", action="store_true", help="Check once and exit.")
    args = parser.parse_args()
    if args.interval_seconds < 1:
        parser.error("--interval-seconds must be at least 1")

    request = Request(args.url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    print(f"Checking {args.url}", flush=True)

    try:
        while True:
            started = monotonic()
            try:
                ok, message = check_health(request)
            except (URLError, TimeoutError) as error:
                ok = False
                message = str(error)

            timestamp = datetime.now().isoformat(timespec="seconds")
            print(f"[{timestamp}] {'OK' if ok else 'ERROR'} {message} ({monotonic() - started:.1f}s)", flush=True)
            if args.once:
                return 0 if ok else 1
            sleep(max(0, args.interval_seconds - (monotonic() - started)))
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
