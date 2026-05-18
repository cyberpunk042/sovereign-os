"""R498 (E11.M2++) — master-dashboard read-only REST API contract lint.

Closes the master-dashboard api:FUTURE waiver. Adds the `api` surface to
the §1g 8-surface ladder for master-dashboard, raising it from 4 → 5
shipped surfaces (core / cli / tui / service / api).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

This surface mirrors the data the operator-facing CLI exposes via
`sovereign-osctl master-dashboard <verb>`. Mutation verbs stay
CLI-only — operator §17 sacrosanct sovereignty boundary.
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SCRIPT = REPO_ROOT / "scripts" / "operator" / "master-dashboard-api.py"
SERVICE_UNIT = (
    REPO_ROOT / "systemd" / "system"
    / "sovereign-master-dashboard-api.service"
)


def test_api_script_exists():
    assert API_SCRIPT.is_file(), f"missing API daemon: {API_SCRIPT}"


def test_api_script_is_executable():
    assert API_SCRIPT.stat().st_mode & 0o111, (
        f"API daemon not executable: {API_SCRIPT}"
    )


def test_api_dry_run_validates():
    """`master-dashboard-api.py dry-run` MUST exit 0 with the endpoint
    enumeration so the operator can confirm shape without bind."""
    result = subprocess.run(
        ["python3", str(API_SCRIPT), "dry-run"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"dry-run failed: {result.stderr[:300]}"
    )
    assert "DRY-RUN" in result.stdout
    assert "/routes" in result.stdout
    assert "/collisions" in result.stdout
    assert "/health" in result.stdout
    assert "/version" in result.stdout
    assert "/discover" in result.stdout


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_daemon():
    port = _free_port()
    env = {
        "MASTER_DASHBOARD_API_BIND": "127.0.0.1",
        "MASTER_DASHBOARD_API_PORT": str(port),
        "PATH": "/usr/bin:/bin",
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-metrics-test",
    }
    proc = subprocess.Popen(
        ["python3", str(API_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    # Wait up to 2s for the bind
    deadline = time.time() + 2.0
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return proc, port
        except OSError:
            time.sleep(0.05)
    proc.terminate()
    raise RuntimeError("master-dashboard-api did not bind in time")


def _get_json(port: int, path: str, method: str = "GET") -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, json.loads(body) if body else {}


def test_api_endpoint_version():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/version")
        assert status == 200
        assert data.get("module") == "master-dashboard-api"
        assert data.get("version", "").startswith("1.")
        assert data.get("standing_rule") == "We do not minimize anything."
        assert "api" in data.get("surfaces", [])
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_endpoint_healthz():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/healthz")
        assert status == 200
        assert data.get("status") == "ok"
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_endpoint_routes():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/routes")
        assert status == 200
        assert "routes" in data
        assert isinstance(data["routes"], list)
        assert data["count"] == len(data["routes"])
        slugs = {r["slug"] for r in data["routes"]}
        # Trinity tiers + router are sacrosanct identity — MUST be present.
        for required in ("trinity-pulse", "trinity-logic-engine",
                         "trinity-oracle-core", "router"):
            assert required in slugs, (
                f"/routes missing sacrosanct slug: {required!r}"
            )
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_endpoint_collisions():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/collisions")
        assert status == 200
        assert "has_collisions" in data
        # Built-in routes MUST not collide.
        assert data["has_collisions"] is False, (
            f"built-in DASHBOARD_ROUTES has collisions: {data}"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_endpoint_health():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/health")
        assert status == 200
        assert "probes" in data
        assert data["count"] == len(data["probes"])
        # Each probe MUST have the contract fields.
        for p in data["probes"]:
            assert "slug" in p
            assert "port" in p
            assert "reachable" in p
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_endpoint_404():
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/nope")
        assert status == 404
        assert "error" in data
        assert "available" in data
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_api_post_rejected_405():
    """Mutation verbs stay CLI-only — operator §17 sovereignty boundary."""
    proc, port = _start_daemon()
    try:
        status, data = _get_json(port, "/routes", method="POST")
        assert status == 405
        assert "read-only" in data.get("error", "")
        assert "operator §17 sovereignty boundary" in data.get("error", "")
    finally:
        proc.terminate()
        proc.wait(timeout=2.0)


def test_systemd_unit_exists():
    assert SERVICE_UNIT.is_file(), (
        f"missing systemd unit: {SERVICE_UNIT}"
    )


def test_systemd_unit_loopback_default():
    """Operator §1g exposure decision stays the operator's — the unit
    MUST bind loopback by default, never 0.0.0.0. Comment lines (#)
    showing operators how to opt in to a wider bind are fine; the
    ACTIVE directive must be loopback."""
    body = SERVICE_UNIT.read_text(encoding="utf-8")
    assert "Environment=MASTER_DASHBOARD_API_BIND=127.0.0.1" in body, (
        "systemd unit must bind loopback by default"
    )
    # Only flag uncommented wildcard binds — operator documentation
    # comments showing how to opt in are explicitly allowed.
    active_lines = [
        ln for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    for ln in active_lines:
        assert "MASTER_DASHBOARD_API_BIND=0.0.0.0" not in ln, (
            f"systemd unit has active wildcard bind: {ln!r}"
        )


def test_systemd_unit_defense_in_depth():
    """R171 defense-in-depth keys MUST appear in the API unit (Layer 1
    lint enforced)."""
    body = SERVICE_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true",
                "PrivateTmp=true", "ReadWritePaths="):
        assert key in body, (
            f"systemd unit missing defense-in-depth key: {key!r}"
        )


def test_master_dashboard_surface_map_extended_to_api():
    """R498 extends master-dashboard surface-map to 5 shipped surfaces —
    api MUST appear as shipped, NOT as a FUTURE waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "master-dashboard", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage master-dashboard failed: "
        f"{result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 5, (
        f"master-dashboard must be at >=5 surfaces post-R498; "
        f"got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    api_row = next(
        (r for r in matrix if r.get("surface") == "api"), None
    )
    assert api_row is not None, (
        "master-dashboard coverage matrix missing 'api' row"
    )
    assert api_row.get("state") == "shipped", (
        f"master-dashboard api surface must be shipped; got {api_row}"
    )
