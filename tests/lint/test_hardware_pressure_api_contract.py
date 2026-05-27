"""M060 D-09 (R10102-R10105) — hardware-pressure API + webapp surface contract.

Drives the D-09 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/hardware/pressure` (+ `/zfs/datasets` + `/stream`)
with no backend. This locks the full §1g 8-surface stack now wired:

  core    scripts/hardware/hardware-pressure.py   (PSI/CCD/GPU/ZFS/backpressure)
  cli     sovereign-osctl hardware-pressure <verb>
  api     scripts/operator/hardware-pressure-api.py  (read-only HTTP)
  webapp  webapp/d-09-hardware-pressure/index.html   (served by the api)
  service systemd/system/sovereign-hardware-pressure-api.service

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface — hardware pressure is observed, not set.
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
CORE = REPO_ROOT / "scripts" / "hardware" / "hardware-pressure.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "hardware-pressure-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-hardware-pressure-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-09-hardware-pressure" / "index.html"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "HARDWARE_PRESSURE_API_BIND": "127.0.0.1",
        "HARDWARE_PRESSURE_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("hardware-pressure-api failed to start within 6s")


# ---- structural -----------------------------------------------------------

def test_core_present_and_runs():
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "status", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    snap = json.loads(out.stdout)
    assert set(snap) >= {"psi", "ccd", "gpu", "zfs", "backpressure"}


def test_api_daemon_present():
    assert API_DAEMON.is_file(), f"api daemon missing: {API_DAEMON}"


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file(), f"service unit missing: {SYSTEMD_UNIT}"


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "HARDWARE_PRESSURE_API_BIND=" in ln:
            assert "HARDWARE_PRESSURE_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "HARDWARE_PRESSURE_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set HARDWARE_PRESSURE_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_hardware_pressure():
    body = OSCTL.read_text(encoding="utf-8")
    assert "hardware-pressure)" in body, "osctl missing hardware-pressure dispatch case"
    assert "scripts/hardware/hardware-pressure.py" in body


# ---- live endpoints (the exact d-09 fetch contract) -----------------------

def test_pressure_endpoint_matches_dashboard_contract():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/hardware/pressure", timeout=3) as r:
            assert r.status == 200
            d = json.loads(r.read())
        # The d-09 webapp reads exactly these shapes.
        assert set(d) >= {"psi", "ccd", "gpu", "zfs", "backpressure"}
        for res in ("cpu", "memory", "io"):
            assert res in d["psi"] and "some_10s" in d["psi"][res]
        assert "datasets" in d["zfs"] and isinstance(d["zfs"]["datasets"], list)
        assert "rules" in d["backpressure"]
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_zfs_datasets_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/hardware/zfs/datasets", timeout=3) as r:
            assert r.status == 200
            d = json.loads(r.read())
        assert "datasets" in d and isinstance(d["datasets"], list)
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-09 hardware pressure" in html
        assert "/api/hardware/pressure" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_readonly_post_rejected():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/hardware/pressure", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/version", timeout=3) as r:
            d = json.loads(r.read())
        assert d["module"] == "d-09-hardware-pressure"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3)
