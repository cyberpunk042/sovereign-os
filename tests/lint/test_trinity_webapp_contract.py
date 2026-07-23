"""R515 (E5++) — Trinity API + webapp surface contract lint.

Closes the trinity webapp:FUTURE waiver — the LAST remaining waiver
for the trinity module. Raises the trinity surface count from 7 → 8
shipped surfaces (core / cli / tui / dashboard / api / service / mcp
/ webapp). Third commit in the trinity tier-3 surface-expansion arc
(R513 TUI → R514 MCP → R515 API + webapp), completing the same shape
as the master-dashboard R498/R499/R500, auth-tier R501/R502/R503,
edge-firewall R504/R505/R506, network-edge R507/R508/R509, and
global-history R510/R511/R512 triples.

This is the FOURTH §1g-named module to hit the full 8-surface §1g
ceiling with NO durable waivers (edge-firewall R506, network-edge
R509, global-history R512, trinity R515).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

R515 also takes the nominal R290-R299 master-spec § 17 lineage `api`
+ `service` claims and makes them REAL — same pattern R510 used for
global-history when it replaced the prior service:not-applicable
waiver with a real systemd-managed daemon.

The webapp surface is a single-file monochrome SPA served by the R515
trinity-api daemon under /webapp/ from the SAME host:port binding as
the JSON endpoints. Operator-§1g UX rule: zero external dependencies,
no CDN fetches, no third-party fonts, no JS framework. Read-only
mirror of `sovereign-osctl trinity {status,pulse,weaver,auditor}
--json` — trinity has NO mutation verbs at any surface (operator §17
sacrosanct sovereignty boundary; the pinned-process state fabric is
mutated by `trinity profile switch <id>`, never by the inspection
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
WEBAPP_HTML = REPO_ROOT / "webapp" / "trinity" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "trinity-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-trinity-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "TRINITY_API_BIND": "127.0.0.1",
        "TRINITY_API_PORT": str(port),
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
    raise RuntimeError("trinity-api failed to start within 6s")


# --- Webapp asset shape ---


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), (
        f"R515 trinity webapp asset missing: {WEBAPP_HTML}"
    )


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "trinity-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "R515" in body
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
    """The webapp must wire against the R515 read-only trinity
    endpoints; trinity has no mutation verbs at any surface — operator
    §17."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for path in ("/version", "/tiers"):
        assert path in body, (
            f"webapp must wire against R515 endpoint {path!r}"
        )


def test_webapp_does_not_leak_mutation_patterns():
    """Trinity has no mutation verbs at any surface — operator §17
    sacrosanct boundary. The webapp must not invoke ANY mutation-
    shaped fetch() call."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for forbidden in (r'fetch\(\s*["\'][^"\']*/set(?!up)',
                      r'fetch\(\s*["\'][^"\']*/apply',
                      r'fetch\(\s*["\'][^"\']*/configure',
                      r'fetch\(\s*["\'][^"\']*/install',
                      r'fetch\(\s*["\'][^"\']*/mutate',
                      r'fetch\(\s*["\'][^"\']*/switch',
                      r'fetch\(\s*["\'][^"\']*/start',
                      r'fetch\(\s*["\'][^"\']*/stop'):
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
    """The R515 webapp MUST surface the operator §17 sovereignty
    boundary disclaimer visibly so any human viewing the SPA sees the
    same wire-contract message the API emits — the pinned-process
    state fabric is mutated by `trinity profile switch <id>`, never
    by this surface."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "§17" in body, (
        "webapp must surface the operator §17 boundary in user-facing "
        "text, not just in source comments"
    )
    assert "trinity profile switch" in body, (
        "webapp §17 disclaimer must name the canonical mutation path "
        "(`trinity profile switch <id>`) so the operator sees where "
        "mutation lives — same shape as the API daemon's 405 message"
    )


# --- API daemon shape ---


def test_api_daemon_present_and_executable():
    assert API_DAEMON.is_file(), (
        f"R515 trinity-api daemon missing: {API_DAEMON}"
    )
    assert API_DAEMON.stat().st_mode & 0o111, (
        "trinity-api.py must be executable"
    )


def test_systemd_unit_present_with_loopback_default():
    assert SYSTEMD_UNIT.is_file(), (
        f"R515 systemd unit missing: {SYSTEMD_UNIT}"
    )
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    assert "Environment=TRINITY_API_BIND=127.0.0.1" in body, (
        "systemd unit must default to loopback bind"
    )
    assert "Environment=TRINITY_API_PORT=8095" in body, (
        "systemd unit must default to port 8095 (operator-named "
        "trinity-api binding)"
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
            assert "trinity" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "trinity-webapp"
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
    """/version must reflect the post-R515 trinity surface state:
    8 surfaces including ALL of tui (R513), mcp (R514), api/service
    (R515 — making the master-spec § 17 lineage REAL), and webapp
    (R515). The shipped_in field must name R515 explicitly."""
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
        assert "R515" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention R515; got {data}"
        )
        assert data.get("webapp_path"), (
            f"/version must surface webapp_path; got {data}"
        )
        # The 3 trinity tiers must still be surfaced.
        for tier in ("pulse", "weaver", "auditor"):
            assert tier in data.get("tiers", []), (
                f"/version tiers must include {tier!r}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_tiers_endpoint_returns_three_tiers():
    """GET /tiers must return the trinity status payload with all 3
    tiers (pulse / weaver / auditor) — load-bearing wire contract for
    the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/tiers", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert data.get("module") == "trinity"
        assert set(data.get("tiers", {}).keys()) == {
            "pulse", "weaver", "auditor"
        }
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_per_tier_endpoints():
    """GET /tiers/pulse, /tiers/weaver, /tiers/auditor must each return
    the per-tier inspection payload."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for tier in ("pulse", "weaver", "auditor"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/tiers/{tier}", timeout=3
            ) as r:
                assert r.status == 200, tier
                data = json.loads(r.read())
            assert data.get("tier") == tier, (
                f"/tiers/{tier} must echo tier name; got {data}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_rejects_mutation_methods_with_section_17_message():
    """Trinity has no mutation verbs at any surface — operator §17
    sacrosanct sovereignty boundary. POST/PUT/DELETE/PATCH must all
    return 405 with a body that names `trinity profile switch` as the
    canonical mutation path."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/tiers/pulse",
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
                assert "trinity profile switch" in err, (
                    f"{method} 405 must name 'trinity profile switch'; "
                    f"got {err!r}"
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


def test_trinity_surface_map_at_eight_surface_ceiling():
    """R515 extends trinity surface-map to 8 shipped surfaces — webapp
    MUST appear as shipped, NOT as a FUTURE waiver. This is trinity's
    STRUCTURAL CEILING — zero remaining waivers (FOURTH §1g-named
    module to reach this state after edge-firewall R506, network-edge
    R509, and global-history R512)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "trinity", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage trinity failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 8, (
        f"trinity must be at 8 surfaces post-R515; got {entry}"
    )
    matrix = entry.get("matrix", [])
    webapp_row = next(
        (r for r in matrix if r.get("surface") == "webapp"), None
    )
    assert webapp_row is not None, (
        "trinity coverage matrix missing 'webapp' row"
    )
    assert webapp_row.get("state") == "shipped", (
        f"trinity webapp surface must be shipped; got {webapp_row}"
    )
    assert entry.get("at_structural_ceiling") is True, (
        f"trinity must report at_structural_ceiling=True; got {entry}"
    )
    assert entry.get("future_waiver_count", 0) == 0, (
        f"trinity must have ZERO FUTURE waivers post-R515; got {entry}"
    )
