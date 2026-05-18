"""R506 (E11.M9++) — edge-firewall webapp surface contract lint.

Closes the edge-firewall webapp:FUTURE waiver — the LAST non-durable
waiver for the edge-firewall module. Raises the edge-firewall surface
count from 7 → 8 shipped surfaces (core / cli / tui / dashboard / api
/ service / mcp / webapp). Third commit in the edge-firewall tier-3
surface-expansion arc — completing the same shape as the master-
dashboard R498/R499/R500 and auth-tier R501/R502/R503 triples.

This is the FIRST §1g-named module to hit the full 8-surface §1g
ceiling with NO durable waivers (master-dashboard kept a durable
self-referential dashboard waiver; auth-tier kept a durable
not-applicable tui waiver).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The webapp surface is a single-file monochrome SPA served by the R504
API daemon under /webapp/ from the SAME host:port binding as the JSON
endpoints. Operator-§1g UX rule: zero external dependencies, no CDN
fetches, no third-party fonts, no JS framework. Read-only mirror of
`sovereign-osctl edge-firewall <verb>` — mutation verb `install` and
interactive `wizard` stay CLI-only (operator §17 sacrosanct
sovereignty boundary; actual firewall mutation requires --apply
--confirm-install on the CLI).
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
WEBAPP_HTML = REPO_ROOT / "webapp" / "edge-firewall" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "edge-firewall-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "EDGE_FIREWALL_API_BIND": "127.0.0.1",
        "EDGE_FIREWALL_API_PORT": str(port),
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
    raise RuntimeError("edge-firewall-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R506 edge-firewall webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "edge-firewall-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "R506" in body
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
        # Concatenation forms like fetch("/install-plan?candidate=" + id)
        # also fall under this regex — the leading slash is what matters.
        assert target.startswith("/"), (
            f"webapp fetch() target {target!r} not same-origin"
        )
        assert "//" not in target


def test_webapp_advertises_read_only_endpoints():
    """The webapp must wire against the R504 read-only edge-firewall
    endpoints; mutation verbs stay CLI-only — operator §17."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/state", "/candidates", "/recommend",
                 "/install-plan"):
        assert path in body, (
            f"webapp must wire against R504 endpoint {path!r}"
        )
    # Mutation verbs must NOT appear as fetch() targets — install-plan
    # is read-only (it's a PLAN, not an apply), but /install (no -plan)
    # would be a mutation leak.
    for forbidden in (r'fetch\(\s*["\']/install["\']',
                      r'fetch\(\s*["\']/install\?',
                      r'fetch\(\s*["\']/wizard'):
        m = re.search(forbidden, body)
        assert m is None, (
            f"webapp leaks mutation pattern {forbidden!r} "
            f"(§17 sovereignty violation)"
        )


def test_api_daemon_serves_webapp_path():
    """Live-spawn the R504 daemon and assert GET /webapp/ returns 200
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
            assert "edge-firewall" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "edge-firewall-webapp"
            assert r.headers.get("X-Frame-Options") == "DENY"
            assert r.headers.get("X-Content-Type-Options") == "nosniff"
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
        assert "mcp" in data.get("surfaces", []), (
            f"/version must advertise 'mcp' surface; got {data}"
        )
        assert "R506" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R506; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_edge_firewall_surface_map_at_eight_surface_ceiling():
    """R506 extends edge-firewall surface-map to 8 shipped surfaces —
    webapp MUST appear as shipped, NOT as a FUTURE waiver. This is
    edge-firewall's STRUCTURAL CEILING — zero remaining waivers."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "edge-firewall", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage edge-firewall failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 8, (
        f"edge-firewall must be at 8 surfaces post-R506; got {entry}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None
    assert webapp_row.get("state") == "shipped", (
        f"edge-firewall webapp surface must be shipped; got {webapp_row}"
    )
    # at_structural_ceiling true with ZERO waivers — the rare full-§1g
    # state.
    assert entry.get("at_structural_ceiling") is True, (
        f"edge-firewall must report at_structural_ceiling=True; "
        f"got {entry}"
    )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer


def test_webapp_surfaces_operator_section_17_disclaimer():
    """The R506 webapp MUST surface the operator §17 sovereignty
    boundary disclaimer visibly — both in the page sub-header and in
    the install-plan disclaimer panel — so any human viewing the SPA
    sees the same wire-contract message the API emits."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "§17" in body, (
        "webapp must surface the operator §17 boundary in user-facing "
        "text, not just in source comments"
    )
    # The install-plan panel renders the wire_contract field — the
    # word `operator §17` is injected at runtime from the JSON
    # response, but the static asset MUST also call out the boundary
    # so an operator viewing the page with the daemon offline still
    # sees the rule.
    assert "CLI-only" in body or "stay CLI-only" in body or \
        "CLI only" in body
