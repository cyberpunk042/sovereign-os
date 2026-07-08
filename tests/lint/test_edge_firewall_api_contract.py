"""R504 (E11.M9++) — edge-firewall read-only REST API surface contract lint.

Closes the edge-firewall api waiver AND the service "candidates ARE
services" waiver. Raises the edge-firewall surface count from 4 → 6
shipped surfaces (core / cli / tui / dashboard / api / service).
First commit in the edge-firewall tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The API surface mirrors the data the CLI exposes via
`sovereign-osctl edge-firewall <verb>` — state / candidates /
recommend / install-plan as read-only endpoints. Mutation verb
`install` and interactive `wizard` stay CLI-only (operator §17
sovereignty boundary — actual firewall changes require explicit
--apply --confirm-install gating on the CLI).
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "edge-firewall-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-edge-firewall-api.service"
)
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
        # Short-circuit OPNsense detection in test — avoids the multi-second
        # TCP-probe path that caused CI-only TimeoutError on /state +
        # /recommend endpoints. Honored by scripts/operator/network-
        # topology.py:detect_opnsense_state().
        "SOVEREIGN_OS_OPNSENSE_DISABLE": "1",
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


def test_api_daemon_present():
    assert API_DAEMON.is_file()


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file()


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [
        ln for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    found_bind = False
    for ln in active:
        if "EDGE_FIREWALL_API_BIND=" in ln:
            assert "EDGE_FIREWALL_API_BIND=127.0.0.1" in ln, (
                f"active systemd line must bind 127.0.0.1: {ln}"
            )
            found_bind = True
        assert "EDGE_FIREWALL_API_BIND=0.0.0.0" not in ln
    assert found_bind


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true",
                "PrivateTmp=true", "ProtectHome=true",
                "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, (
            f"R171 hardening key missing: {key}"
        )


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert data["module"] == "edge-firewall-api"
        assert "R504" in data["shipped_in"]
        assert "api" in data["surfaces"]
        assert data["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_state_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/state", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "local" in data
        assert "upstream" in data
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_candidates_endpoint():
    """4-class §1g ladder (nftables-baseline / fail2ban / crowdsec /
    suricata) MUST be present."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/candidates", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert data["count"] >= 4
        ids = [c["id"] for c in data["candidates"]]
        for needed in ("nftables-baseline", "fail2ban",
                       "crowdsec", "suricata"):
            assert needed in ids, (
                f"4-class ladder missing {needed!r}; got {ids}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_recommend_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/recommend", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "upstream_tier" in data
        assert "recommendations" in data
        assert "count" in data
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_install_plan_400_without_candidate():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/install-plan", timeout=3
            )
            assert False, "/install-plan without ?candidate= must 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read())
            assert "known" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_install_plan_404_unknown_candidate():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        url = (
            f"http://127.0.0.1:{port}/install-plan?"
            f"candidate={urllib.parse.quote('not-a-real-candidate')}"
        )
        try:
            urllib.request.urlopen(url, timeout=3)
            assert False, "must 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
            assert "known" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_install_plan_returns_apply_disclaimer():
    """The install-plan payload MUST include a wire_contract note
    that explicitly says actual mutation requires the CLI — operator
    §17 sovereignty boundary surfaced in the wire data, not just in
    the source comments."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/install-plan?"
            f"candidate=fail2ban", timeout=3
        ) as r:
            plan = json.loads(r.read())
        assert plan["candidate"] == "fail2ban"
        assert "install_steps" in plan
        assert "rollback_steps" in plan
        assert "next_action" in plan
        assert "wire_contract" in plan
        assert "operator §17" in plan["wire_contract"]
        assert "CLI" in plan["next_action"]
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_unknown_endpoint_404():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/no-such-endpoint", timeout=3
            )
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
            body = json.loads(e.read())
            assert "available" in body
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_mutation_methods_405():
    """Operator §17 — mutation verbs `install` and interactive
    `wizard` stay CLI-only."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/state",
                method=method, data=b"",
            )
            try:
                urllib.request.urlopen(req, timeout=3)
                assert False, f"{method} must 405"
            except urllib.error.HTTPError as e:
                assert e.code == 405
                body = json.loads(e.read())
                assert "operator §17" in body.get("error", "")
                assert "install" in body.get("error", "")
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
            assert r.headers.get("X-Sovereign-Module") == \
                "edge-firewall-api"
            ver = r.headers.get("X-Sovereign-Version", "")
            assert ver.startswith("1.")
            assert "R5" in ver
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_edge_firewall_surface_map_extended():
    """R504 extends edge-firewall surface-map to 6 shipped surfaces —
    api AND service MUST appear as shipped."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "edge-firewall", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 6, (
        f"edge-firewall must be at >=6 surfaces post-R504; got {entry}"
    )
    matrix = entry.get("matrix", [])
    api_row = next(
        (r for r in matrix if r.get("surface") == "api"), None
    )
    assert api_row is not None
    assert api_row.get("state") == "shipped"
    service_row = next(
        (r for r in matrix if r.get("surface") == "service"), None
    )
    assert service_row is not None
    assert service_row.get("state") == "shipped"
