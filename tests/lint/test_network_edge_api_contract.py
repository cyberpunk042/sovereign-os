"""R507 (E11.M8++) — network-edge read-only REST API surface contract lint.

Closes the network-edge api waiver AND the service "query surface,
no daemon" waiver. Raises the network-edge surface count from 4 → 6
shipped surfaces (core / cli / tui / dashboard / api / service).
First commit in the network-edge tier-3 surface-expansion arc.

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The API surface mirrors the data the CLI exposes via
`sovereign-osctl network-edge <verb>` — detect / interfaces /
nat-chain / opnsense status / opnsense capabilities as read-only
endpoints. network-edge has no mutation verbs at any surface
(operator §17 sovereignty boundary — OPNsense config changes are
operator-driven via OPNsense UI/API directly, outside the
sovereign-os boundary).
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "network-edge-api.py"
SYSTEMD_UNIT = (
    REPO_ROOT / "systemd" / "system" / "sovereign-network-edge-api.service"
)
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "NETWORK_EDGE_API_BIND": "127.0.0.1",
        "NETWORK_EDGE_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        # Short-circuit OPNsense detection in test — avoids the multi-second
        # TCP-probe path that caused CI-only TimeoutError on /detect +
        # /opnsense/status + /opnsense/capabilities endpoints. Honored by
        # scripts/operator/network-topology.py:detect_opnsense_state().
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
    raise RuntimeError("network-edge-api failed to start within 6s")


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
        if "NETWORK_EDGE_API_BIND=" in ln:
            assert "NETWORK_EDGE_API_BIND=127.0.0.1" in ln, (
                f"active systemd line must bind 127.0.0.1: {ln}"
            )
            found_bind = True
        assert "NETWORK_EDGE_API_BIND=0.0.0.0" not in ln
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
        assert data["module"] == "network-edge-api"
        assert "R507" in data["shipped_in"]
        assert "api" in data["surfaces"]
        assert "service" in data["surfaces"]
        assert data["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_detect_endpoint():
    """The full detect bundle MUST carry every CLI-exposed top-level
    key — operator §1g: the wire payload mirrors the CLI verbatim,
    we do not minimize anything."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/detect", timeout=5
        ) as r:
            data = json.loads(r.read())
        for needed in ("interfaces_count", "interfaces",
                       "default_gateway", "nat_chain", "vpn_bridge",
                       "opnsense", "capabilities",
                       "operator_named_edge_hardware"):
            assert needed in data, (
                f"/detect payload missing {needed!r}: keys={list(data)}"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_interfaces_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/interfaces", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "count" in data
        assert "interfaces" in data
        assert isinstance(data["interfaces"], list)
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_nat_chain_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/nat-chain", timeout=3
        ) as r:
            data = json.loads(r.read())
        # nat_chain payload always carries an `available` boolean
        # (even when detection fails).
        assert "available" in data, (
            f"/nat-chain must include 'available' field; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_opnsense_status_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/opnsense/status", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "tier" in data, (
            f"/opnsense/status must include 'tier'; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_opnsense_capabilities_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/opnsense/capabilities", timeout=3
        ) as r:
            data = json.loads(r.read())
        for needed in ("tier", "unlocked", "unlocked_count",
                       "next_to_unlock"):
            assert needed in data, (
                f"/opnsense/capabilities missing {needed!r}: {data}"
            )
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
    """network-edge has no mutation verbs at any surface — operator
    §17 sovereignty boundary. POST/PUT/DELETE/PATCH MUST 405 with the
    sovereignty-boundary disclaimer message."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/detect",
                method=method, data=b"",
            )
            try:
                urllib.request.urlopen(req, timeout=3)
                assert False, f"{method} must 405"
            except urllib.error.HTTPError as e:
                assert e.code == 405
                body = json.loads(e.read())
                assert "operator §17" in body.get("error", "")
                assert "OPNsense" in body.get("error", "")
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
                "network-edge-api"
            ver = r.headers.get("X-Sovereign-Version", "")
            assert ver.startswith("1.")
            assert "R5" in ver
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_network_edge_surface_map_extended():
    """R507 extends network-edge surface-map to 6 shipped surfaces —
    api AND service MUST appear as shipped (the prior `service: not
    applicable` waiver is replaced by the actual systemd daemon
    shipped in this round)."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "network-edge", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    assert entry.get("surface_count", 0) >= 6, (
        f"network-edge must be at >=6 surfaces post-R507; got {entry}"
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
