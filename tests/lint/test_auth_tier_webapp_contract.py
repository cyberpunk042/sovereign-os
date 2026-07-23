"""R503 (E11.M7++) — auth-tier webapp surface contract lint.

Closes the auth-tier webapp:FUTURE waiver — the LAST non-durable
waiver for the auth-tier module. Raises the auth-tier surface count
from 6 → 7 shipped surfaces (core / cli / dashboard / api / service /
mcp / webapp). Third commit in the auth-tier tier-3 surface-expansion
arc — completing the same shape as the master-dashboard R498/R499/R500
triple.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The webapp surface is a single-file monochrome SPA served by the R501
API daemon under /webapp/ from the SAME host:port binding as the JSON
endpoints. Operator-§1g UX rule: zero external dependencies, no CDN
fetches, no third-party fonts, no JS framework. Read-only mirror of
`sovereign-osctl auth-tier <verb>` — mutation verb `set` stays
CLI-only (operator §17 sacrosanct sovereignty boundary).
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "auth-tier" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "auth-tier-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "AUTH_TIER_API_BIND": "127.0.0.1",
        "AUTH_TIER_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("auth-tier-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R503 auth-tier webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "auth-tier-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "R503" in body
    assert 'name="x-sovereign-standing-rule"' in body
    assert "We do not minimize anything." in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    forbidden_hosts = [
        "https://cdn.", "http://cdn.", "https://cdnjs.",
        "https://unpkg.", "https://fonts.googleapis.",
        "https://fonts.gstatic.", "https://ajax.googleapis.",
        "https://code.jquery.", "https://stackpath.",
        "https://maxcdn.", "https://bootstrapcdn.",
        "https://use.fontawesome.", "//cdn.",
    ]
    for host in forbidden_hosts:
        assert host not in body, (
            f"webapp must NOT reference external host {host!r}"
        )
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), (
            f"webapp fetch() target {target!r} not same-origin"
        )
        assert "//" not in target


def test_webapp_advertises_read_only_endpoints():
    """The webapp must wire against the R501 read-only auth-tier
    endpoints; mutation verbs (/set) stay CLI-only — operator §17."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/tiers", "/registry", "/matrix"):
        assert path in body, (
            f"webapp must wire against R501 endpoint {path!r}"
        )
    # /set must NOT appear as a fetch() target.
    m = re.search(r'fetch\(\s*["\']/set(?!up)', body)
    assert m is None, (
        "webapp leaks mutation verb /set as fetch() target "
        "(§17 sovereignty violation)"
    )


def test_api_daemon_serves_webapp_path():
    """Live-spawn the R501 daemon and assert GET /webapp/ returns 200
    text/html with the §1g standing rule embedded."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            assert r.status == 200
            ctype = r.headers.get("Content-Type", "")
            assert "text/html" in ctype
            body = r.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "<!doctype html>" in body
            assert "auth-tier" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "auth-tier-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_webapp_aliases():
    """/webapp, /webapp/, /webapp/index.html all resolve to the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for path in ("/webapp", "/webapp/", "/webapp/index.html"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=3
            ) as r:
                assert r.status == 200
                assert "text/html" in r.headers.get("Content-Type", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", []), (
            f"/version must advertise 'webapp' surface; got {data}"
        )
        assert "R503" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R503; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_auth_tier_surface_map_extended_to_webapp():
    """R503 extends auth-tier surface-map to 7 shipped surfaces —
    webapp MUST appear as shipped, NOT as a FUTURE waiver."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "auth-tier", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage auth-tier failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 7, (
        f"auth-tier must be at >=7 surfaces post-R503; got {entry}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None
    assert webapp_row.get("state") == "shipped", (
        f"auth-tier webapp surface must be shipped; got {webapp_row}"
    )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer
