"""R501 (E11.M7++) — auth-tier read-only REST API surface contract lint.

Closes the auth-tier api:FUTURE waiver. Raises the auth-tier surface
count from 3 → 5 shipped surfaces (core / cli / dashboard / api /
service). First commit in the auth-tier tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

The API surface mirrors the data the CLI exposes via
`sovereign-osctl auth-tier <verb>` — list-tiers / registry / show /
matrix as read-only endpoints. Mutation verb `set` stays CLI-only
(operator §17 sovereignty boundary).
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "auth-tier-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-auth-tier-api.service"
)
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


def test_api_daemon_present():
    assert API_DAEMON.is_file(), (
        f"R501 auth-tier-api daemon missing: {API_DAEMON}"
    )


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file(), (
        f"R501 sovereign-auth-tier-api.service unit missing: "
        f"{SYSTEMD_UNIT}"
    )


def test_systemd_unit_loopback_default():
    """Loopback-by-default — operator-§1g exposure decision is theirs."""
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [
        ln for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    found_bind = False
    for ln in active:
        if "AUTH_TIER_API_BIND=" in ln:
            assert "AUTH_TIER_API_BIND=127.0.0.1" in ln, (
                f"active systemd line must bind 127.0.0.1: {ln}"
            )
            found_bind = True
        assert "AUTH_TIER_API_BIND=0.0.0.0" not in ln, (
            f"active systemd line must NOT wildcard-bind: {ln}"
        )
    assert found_bind, (
        "systemd unit must set AUTH_TIER_API_BIND=127.0.0.1"
    )


def test_systemd_unit_defense_in_depth():
    """R171 defense-in-depth keys MUST be present (Layer 1 hardening)."""
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    required = [
        "ProtectSystem=strict",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=true",
        "RestrictAddressFamilies=",
        "SystemCallFilter=",
    ]
    for key in required:
        assert key in body, (
            f"R171 hardening key missing in systemd unit: {key}"
        )


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert data["module"] == "auth-tier-api"
        assert "R501" in data["shipped_in"]
        assert "api" in data["surfaces"]
        assert data["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_tiers_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/tiers", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert data["count"] >= 6, (
            f"6-tier §1g ladder expected; got {data}"
        )
        names = [t["tier"] for t in data["tiers"]]
        for needed in ("no-auth", "basic", "advanced",
                       "social", "enterprise", "network-level"):
            assert needed in names, (
                f"6-tier ladder missing tier {needed!r}; got {names}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_registry_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/registry", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert "dashboards" in data
        assert "config_path" in data
        assert "count" in data
        assert isinstance(data["count"], int)
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_matrix_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/matrix", timeout=3
        ) as r:
            assert r.status == 200
            data = json.loads(r.read())
        assert "matrix" in data
        assert "count" in data
        assert "upgrades_pending" in data
        assert isinstance(data["matrix"], list)
        for row in data["matrix"]:
            assert "dashboard" in row
            assert "current" in row
            assert "recommended" in row
            assert "upgrade_levels" in row
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_show_endpoint_400_without_dashboard():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/show"
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            assert False, "/show without dashboard must 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400, f"expected 400, got {e.code}"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_show_endpoint_404_on_unknown_dashboard():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        url = (
            f"http://127.0.0.1:{port}/show?"
            f"dashboard={urllib.parse.quote('zz-unknown-dashboard')}"
        )
        try:
            urllib.request.urlopen(url, timeout=3)
            assert False, "/show with unknown dashboard must 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
            assert "known" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_unknown_endpoint_404():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/no-such-endpoint",
                timeout=3,
            )
            assert False, "unknown endpoint must 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
            assert "available" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_mutation_methods_405():
    """Operator §17 — mutation verb `set` stays CLI-only. The REST
    API daemon MUST reject POST/PUT/DELETE/PATCH with 405."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/registry",
                method=method,
                data=b"",
            )
            try:
                urllib.request.urlopen(req, timeout=3)
                assert False, f"{method} must be rejected with 405"
            except urllib.error.HTTPError as e:
                assert e.code == 405, (
                    f"{method} expected 405, got {e.code}"
                )
                body = json.loads(e.read())
                assert "operator §17" in body.get("error", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_response_headers_carry_sovereign_identity():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            assert r.headers.get("X-Sovereign-Module") == "auth-tier-api"
            ver = r.headers.get("X-Sovereign-Version", "")
            # R501 introduced the daemon; later rounds extend it
            # (R503 webapp). The version string MUST carry the active
            # R-tag — anything from R501 onward is acceptable.
            assert ver.startswith("1."), (
                f"X-Sovereign-Version must be SemVer 1.x; got {ver!r}"
            )
            assert "R5" in ver, (
                f"X-Sovereign-Version must reference an R5xx round; "
                f"got {ver!r}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_auth_tier_surface_map_extended_to_api():
    """R501 extends auth-tier surface-map to 5 shipped surfaces — api
    AND service MUST appear as shipped (not as FUTURE waivers)."""
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
    assert entry.get("surface_count", 0) >= 5, (
        f"auth-tier must be at >=5 surfaces post-R501; got {entry}"
    )
    matrix = entry.get("matrix", [])
    api_row = next(
        (r for r in matrix if r.get("surface") == "api"), None
    )
    assert api_row is not None, (
        "auth-tier coverage matrix missing 'api' row"
    )
    assert api_row.get("state") == "shipped", (
        f"auth-tier api surface must be shipped; got {api_row}"
    )
    service_row = next(
        (r for r in matrix if r.get("surface") == "service"), None
    )
    assert service_row is not None
    assert service_row.get("state") == "shipped", (
        f"auth-tier service surface must be shipped; got {service_row}"
    )
