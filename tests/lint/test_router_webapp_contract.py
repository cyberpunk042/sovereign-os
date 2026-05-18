"""R518 (E5++) — Router API + webapp surface contract lint.

Closes the router webapp:FUTURE waiver — the LAST remaining waiver
for the router module. Raises the router surface count from 7 → 8
shipped surfaces (core / cli / tui / api / service / dashboard / mcp
/ webapp). Third and last commit in the router tier-3 surface-
expansion arc (R516 TUI → R517 MCP → R518 API + webapp), completing
the same shape as the master-dashboard, auth-tier, edge-firewall,
network-edge, global-history, and trinity arcs.

This is the FIFTH §1g-named module to hit the full 8-surface §1g
ceiling with NO durable waivers (edge-firewall R506, network-edge
R509, global-history R512, trinity R515, router R518).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The webapp surface is a single-file monochrome SPA served by the R518
router-api daemon under /webapp/ from the SAME host:port binding as
the JSON endpoints. Operator-§1g UX rule: zero external dependencies,
no CDN fetches, no third-party fonts, no JS framework. Read-only
mirror of `sovereign-osctl router {status,rules,metrics} --json` —
router inspection has NO mutation verbs at any surface (operator §17
sacrosanct sovereignty boundary; the routing-tier selection is driven
by the SDD-011 5-rule ladder + the actual HTTP request shape sent to
sovereign-router.service at 127.0.0.1:8080, never by the inspection
daemon).
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
WEBAPP_HTML = REPO_ROOT / "webapp" / "router" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "router-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-router-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "ROUTER_API_BIND": "127.0.0.1",
        "ROUTER_API_PORT": str(port),
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
    raise RuntimeError("router-api failed to start within 6s")


# --- Webapp asset shape ---


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R518 router webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "router-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "R518" in body
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
    """The webapp must wire against the R518 read-only router
    endpoints; router inspection has no mutation verbs at any surface
    — operator §17."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/status", "/rules", "/metrics"):
        assert path in body, (
            f"webapp must wire against R518 endpoint {path!r}"
        )


def test_webapp_does_not_leak_mutation_patterns():
    """Router inspection has no mutation verbs at any surface —
    operator §17 sacrosanct boundary. The webapp must not invoke ANY
    mutation-shaped fetch() call."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for forbidden in (r'fetch\(\s*["\'][^"\']*/set',
                      r'fetch\(\s*["\'][^"\']*/apply',
                      r'fetch\(\s*["\'][^"\']*/configure',
                      r'fetch\(\s*["\'][^"\']*/install',
                      r'fetch\(\s*["\'][^"\']*/mutate',
                      r'fetch\(\s*["\'][^"\']*/switch',
                      r'fetch\(\s*["\'][^"\']*/start',
                      r'fetch\(\s*["\'][^"\']*/stop',
                      r'fetch\(\s*["\'][^"\']*/classify'):
        m = re.search(forbidden, body)
        assert m is None, (
            f"webapp leaks mutation pattern {forbidden!r} "
            f"(§17 sovereignty violation)"
        )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer


def test_webapp_surfaces_operator_section_17_disclaimer():
    """The R518 webapp MUST surface the operator §17 sovereignty
    boundary disclaimer visibly so any human viewing the SPA sees the
    same wire-contract message the API emits — the routing-tier
    selection happens at request-time inside sovereign-router.service
    at 127.0.0.1:8080, never inside the inspection surface."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "§17" in body, (
        "webapp must surface the operator §17 boundary in user-facing "
        "text, not just in source comments"
    )
    assert "sovereign-router.service" in body, (
        "webapp §17 disclaimer must name the canonical routing daemon "
        "(`sovereign-router.service`) so the operator sees where "
        "routing actually happens — same shape as the API daemon's "
        "405 message"
    )


def test_webapp_surfaces_sdd_011_rules_table():
    """The R518 webapp MUST render the SDD-011 routing rules visibly
    so operators see the full ladder — operator §1g rule: full ladder
    visible."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "SDD-011" in body, (
        "webapp must cite SDD-011 (the routing rules spec)"
    )
    assert "rules-tbody" in body or "rules-table" in body, (
        "webapp must render rules in a visible table"
    )


# --- API daemon shape ---


def test_api_daemon_present_and_executable():
    assert API_DAEMON.is_file(), (
        f"R518 router-api daemon missing: {API_DAEMON}"
    )
    assert API_DAEMON.stat().st_mode & 0o111, (
        "router-api.py must be executable"
    )


def test_systemd_unit_present_with_loopback_default():
    assert SYSTEMD_UNIT.is_file(), (
        f"R518 systemd unit missing: {SYSTEMD_UNIT}"
    )
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    assert "Environment=ROUTER_API_BIND=127.0.0.1" in body, (
        "systemd unit must default to loopback bind"
    )
    assert "Environment=ROUTER_API_PORT=8096" in body, (
        "systemd unit must default to port 8096 (operator-named "
        "router-api binding, sister to trinity-api port 8095)"
    )


def test_systemd_unit_carries_r171_hardening_keys():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in (
        "ProtectSystem=strict",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=true",
        "ProtectKernelTunables=true",
        "ProtectKernelModules=true",
        "ProtectControlGroups=true",
        "RestrictNamespaces=true",
        "RestrictRealtime=true",
        "LockPersonality=true",
        "RestrictSUIDSGID=true",
        "SystemCallFilter=@system-service",
    ):
        assert key in body, (
            f"R171 defense-in-depth: systemd unit missing {key!r}"
        )


# --- Live daemon contract ---


def test_api_daemon_serves_webapp_path():
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
            assert "router" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "router-webapp"
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


def test_api_daemon_version_advertises_full_eight_surface_ladder():
    """/version must reflect the post-R518 router surface state:
    8 surfaces including ALL of tui (R516), mcp (R517), api/service
    (R518), and webapp (R518). The shipped_in field must name R518
    explicitly."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        surfaces = data.get("surfaces", [])
        for required in ("core", "cli", "tui", "dashboard",
                         "api", "service", "mcp", "webapp"):
            assert required in surfaces, (
                f"/version must advertise {required!r} surface; "
                f"got {surfaces}"
            )
        assert len(surfaces) >= 8, (
            f"/version must surface the full 8-surface §1g ladder; "
            f"got {surfaces}"
        )
        assert "R518" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R518; got {data}"
        )
        assert data.get("webapp_path"), (
            f"/version must surface webapp_path; got {data}"
        )
        # The 3 inspection verbs must still be surfaced.
        for verb in ("status", "rules", "metrics"):
            assert verb in data.get("verbs", []), (
                f"/version verbs must include {verb!r}"
            )
        assert data.get("spec_ref") == "SDD-011"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_status_endpoint_shape():
    """GET /status must return the router status payload with the
    service/listen/backends sections — load-bearing wire contract
    for the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/status", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert data.get("module") == "router"
        assert data.get("spec_ref") == "SDD-011"
        assert data["service"]["name"] == "sovereign-router.service"
        assert data["listen"]["port"] == 8080
        assert set(data["backends"].keys()) == {
            "pulse", "logic-engine", "oracle-core"
        }
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_rules_endpoint_lists_five_rules():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/rules", timeout=3
        ) as r:
            data = json.loads(r.read())
        rules = data.get("rules", [])
        assert len(rules) == 5
        assert data.get("match_order") == "first match wins"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_metrics_endpoint_shape():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert data.get("module") == "router"
        assert "tier_counts" in data
        assert "metrics_dir" in data
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_rejects_mutation_methods_with_section_17_message():
    """Router inspection has no mutation verbs at any surface —
    operator §17 sacrosanct sovereignty boundary. POST/PUT/DELETE/PATCH
    must all return 405 with a body that names sovereign-router.service
    as the canonical routing locus."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                method=method, data=b"",
            )
            try:
                with urllib.request.urlopen(req, timeout=3) as r:
                    assert r.status == 405, (
                        f"{method} must return 405; got {r.status}"
                    )
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} must return 405; got {e.code}"
                )
                body = e.read().decode("utf-8")
                payload = json.loads(body)
                err = payload.get("error", "")
                assert "sovereign-router.service" in err, (
                    f"{method} 405 must name 'sovereign-router.service'"
                    f"; got {err!r}"
                )
                assert "§17" in err or "§ 17" in err or \
                    "section 17" in err.lower(), (
                    f"{method} 405 must cite §17 boundary; got {err!r}"
                )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_404_for_unknown_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/no-such-path"
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                assert r.status == 404
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        proc.kill()
        proc.wait(timeout=3)


# --- Surface-map ceiling ---


def test_router_surface_map_at_eight_surface_ceiling():
    """R518 extends router surface-map to 8 shipped surfaces — webapp
    MUST appear as shipped, NOT as a FUTURE waiver. This is router's
    STRUCTURAL CEILING — zero remaining waivers (FIFTH §1g-named
    module to reach this state after edge-firewall R506, network-edge
    R509, global-history R512, trinity R515)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "router", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage router failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 8, (
        f"router must be at 8 surfaces post-R518; got {entry}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None, (
        "router coverage matrix missing 'webapp' row"
    )
    assert webapp_row.get("state") == "shipped", (
        f"router webapp surface must be shipped; got {webapp_row}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"router must report at_structural_ceiling=True; got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"router must have ZERO FUTURE waivers post-R518; got {entry}"
    )
