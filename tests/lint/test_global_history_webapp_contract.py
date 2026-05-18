"""R512 (E11.M5++) — global-history webapp surface contract lint.

Closes the global-history webapp:FUTURE waiver — the LAST remaining
waiver for the global-history module. Raises the global-history surface
count from 7 → 8 shipped surfaces (core / cli / tui / dashboard / api /
service / mcp / webapp). Third commit in the global-history tier-3
surface-expansion arc — completing the same shape as the master-
dashboard R498/R499/R500, auth-tier R501/R502/R503, edge-firewall
R504/R505/R506, and network-edge R507/R508/R509 triples.

This is the THIRD §1g-named module to hit the full 8-surface §1g
ceiling with NO durable waivers (edge-firewall was the first in R506,
network-edge was the second in R509, global-history is the third).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The webapp surface is a single-file monochrome SPA served by the R510
API daemon under /webapp/ from the SAME host:port binding as the JSON
endpoints. Operator-§1g UX rule: zero external dependencies, no CDN
fetches, no third-party fonts, no JS framework. Read-only mirror of
`sovereign-osctl global-history <verb>` — global-history has NO
mutation verbs at any surface (operator §17 sacrosanct sovereignty
boundary; the 6 underlying source logs — apt / dpkg / shell / osctl /
events / modules — are mutated by their owning processes, outside the
sovereign-os boundary).
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
WEBAPP_HTML = REPO_ROOT / "webapp" / "global-history" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "global-history-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "GLOBAL_HISTORY_API_BIND": "127.0.0.1",
        "GLOBAL_HISTORY_API_PORT": str(port),
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
    raise RuntimeError("global-history-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R512 global-history webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "global-history-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "R512" in body
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
    """The webapp must wire against the R510 read-only global-history
    endpoints; global-history has no mutation verbs at any surface —
    operator §17."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/sources", "/summary", "/recent"):
        assert path in body, (
            f"webapp must wire against R510 endpoint {path!r}"
        )


def test_webapp_does_not_leak_mutation_patterns():
    """global-history has no mutation verbs at any surface — operator
    §17 sacrosanct boundary. The webapp must not invoke ANY mutation-
    shaped fetch() call (no /set, /apply, /configure, /install,
    /mutate, /write, /delete, /clear)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for forbidden in (r'fetch\(\s*["\'][^"\']*/set',
                      r'fetch\(\s*["\'][^"\']*/apply',
                      r'fetch\(\s*["\'][^"\']*/configure',
                      r'fetch\(\s*["\'][^"\']*/install',
                      r'fetch\(\s*["\'][^"\']*/mutate',
                      r'fetch\(\s*["\'][^"\']*/write',
                      r'fetch\(\s*["\'][^"\']*/delete',
                      r'fetch\(\s*["\'][^"\']*/clear'):
        m = re.search(forbidden, body)
        assert m is None, (
            f"webapp leaks mutation pattern {forbidden!r} "
            f"(§17 sovereignty violation)"
        )


def test_api_daemon_serves_webapp_path():
    """Live-spawn the R510 daemon and assert GET /webapp/ returns 200
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
            assert "global-history" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "global-history-webapp"
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


def test_api_daemon_version_advertises_webapp_and_mcp_surfaces():
    """/version must reflect the post-R512 global-history surface state:
    8 surfaces including BOTH `webapp` (R512) and `mcp` (R511); the
    shipped_in field must name R512 explicitly."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        surfaces = data.get("surfaces", [])
        assert "webapp" in surfaces, (
            f"/version must advertise 'webapp' surface; got {data}"
        )
        assert "mcp" in surfaces, (
            f"/version must advertise 'mcp' surface; got {data}"
        )
        assert len(surfaces) >= 8, (
            f"/version must surface the full 8-surface §1g ladder; "
            f"got {surfaces}"
        )
        assert "R512" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R512; got {data}"
        )
        assert data.get("webapp_path"), (
            f"/version must surface webapp_path; got {data}"
        )
        # The 6 KNOWN_SOURCES MUST still be surfaced (R510 contract).
        for src in ("apt", "dpkg", "shell", "osctl", "events", "modules"):
            assert src in data["known_sources"], (
                f"/version known_sources must include {src!r}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_global_history_surface_map_at_eight_surface_ceiling():
    """R512 extends global-history surface-map to 8 shipped surfaces —
    webapp MUST appear as shipped, NOT as a FUTURE waiver. This is
    global-history's STRUCTURAL CEILING — zero remaining waivers
    (THIRD §1g-named module to reach this state after edge-firewall
    R506 and network-edge R509)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "global-history", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage global-history failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 8, (
        f"global-history must be at 8 surfaces post-R512; got {entry}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None, (
        "global-history coverage matrix missing 'webapp' row"
    )
    assert webapp_row.get("state") == "shipped", (
        f"global-history webapp surface must be shipped; got {webapp_row}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"global-history must report at_structural_ceiling=True; "
        f"got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"global-history must have ZERO FUTURE waivers post-R512; "
        f"got {entry}"
    )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer


def test_webapp_surfaces_operator_section_17_disclaimer():
    """The R512 webapp MUST surface the operator §17 sovereignty
    boundary disclaimer visibly so any human viewing the SPA sees the
    same wire-contract message the API emits — the 6 source logs are
    mutated by their owning processes, never by this surface."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "§17" in body, (
        "webapp must surface the operator §17 boundary in user-facing "
        "text, not just in source comments"
    )
    # The disclaimer must name at least one underlying source so the
    # operator sees what is/isn't this daemon's mutation domain — same
    # shape as the API daemon's 405 message.
    assert any(s in body for s in
               ("apt", "dpkg", "shell", "osctl", "events", "modules")), (
        "webapp §17 disclaimer must name at least one of the 6 source "
        "logs (apt / dpkg / shell / osctl / events / modules)"
    )
