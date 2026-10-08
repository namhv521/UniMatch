from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import urllib.request


def request(opener, base: str, path: str, *, payload: dict | None = None, timeout: float = 15) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers.update({"Content-Type": "application/json", "Origin": base})
    with opener.open(urllib.request.Request(base + path, data=data, headers=headers), timeout=timeout) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a running KLTN API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    email = os.getenv("KLTN_LOGIN_EMAIL")
    password = os.getenv("KLTN_LOGIN_PASSWORD")
    if not email or not password:
        raise SystemExit("KLTN_LOGIN_EMAIL and KLTN_LOGIN_PASSWORD are required")
    base = args.base_url.rstrip("/")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    health = request(opener, base, "/api/v1/health")
    request(opener, base, "/api/v1/auth/login", payload={"email": email, "password": password})
    catalog = request(opener, base, "/api/v1/catalog")
    simulation = request(
        opener,
        base,
        "/api/v1/simulate",
        payload={"mode": "semantic", "algorithm": "greedy", "dataset": "sample-3x2", "seed": 42},
    )
    summary = {
        "operational": health.get("data_loaded") is True,
        "catalog": catalog.get("status") == "success",
        "assignments": len(simulation.get("data", {}).get("assignments", [])),
    }
    print(json.dumps(summary))
    if not summary['operational'] or not summary['catalog'] or summary['assignments'] != 3:
        raise SystemExit('API smoke assertions failed')


if __name__ == "__main__":
    main()
