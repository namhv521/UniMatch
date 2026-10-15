from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_production_compose_terminates_https_before_same_origin_app() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.production.yml").read_text(encoding="utf-8"))
    proxy = compose["services"]["proxy"]
    dashboard = compose["services"]["dashboard"]

    assert proxy["image"].startswith("caddy:2")
    assert {"80:80", "443:443", "443:443/udp"} <= set(proxy["ports"])
    assert dashboard["environment"]["KLTN_COOKIE_SECURE"] == "true"
    assert dashboard["environment"]["KLTN_ALLOWED_ORIGIN"].startswith("https://${KLTN_DOMAIN:")

    caddyfile = (ROOT / "deployment/Caddyfile").read_text(encoding="utf-8")
    assert "{$KLTN_DOMAIN}" in caddyfile
    assert "reverse_proxy dashboard:8000" in caddyfile
