"""Contract test for scripts/operator/control-exec-api.py — the cockpit's
sanctioned R10274 mutation endpoint.

Proves the daemon faithfully realizes R10274 (the web can now EXECUTE controls)
WITHOUT breaking R10212 (the web still never arbitrarily mutates — selfdef/
perimeter are proxy-only, privileged controls are confirm/key-gated, and every
execute is a safe dry-run unless the process opted into live mode). The daemon is
a thin proxy over the merged `_action_exec.execute()` primitive, so this test
locks the daemon's HTTP contract, not the primitive's internals (those are in
tests/unit/test_action_exec.py).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON = REPO_ROOT / "scripts" / "operator" / "control-exec-api.py"
UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-control-exec-api.service"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn(port: int):
    env = {
        "CONTROL_EXEC_API_BIND": "127.0.0.1",
        "CONTROL_EXEC_API_PORT": str(port),
        # DELIBERATELY do NOT set SOVEREIGN_OS_ACTION_EXEC_LIVE — the test must
        # run in the safe dry-run default (never mutates the host).
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(["python3", str(DAEMON)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    out, err = proc.communicate(timeout=3)
    raise RuntimeError(f"control-exec-api failed to start: {err.decode()[-800:]}")


def _get(port: int, path: str):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(port: int, path: str, body, method: str = "POST"):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ── structural ─────────────────────────────────────────────────────────────

def test_daemon_present():
    assert DAEMON.is_file(), f"missing {DAEMON}"
    src = DAEMON.read_text()
    assert "We do not minimize anything." in src
    assert "_action_exec" in src and "R10274" in src and "R10212" in src


def test_systemd_unit_loopback_and_dry_run_default():
    assert UNIT.is_file(), f"missing {UNIT}"
    u = UNIT.read_text()
    assert "CONTROL_EXEC_API_BIND=127.0.0.1" in u
    assert "CONTROL_EXEC_API_BIND=0.0.0.0" not in u
    # LIVE must NOT be forced on in the shipped unit — it is an operator drop-in.
    active = [ln for ln in u.splitlines()
              if ln.strip().startswith("Environment=SOVEREIGN_OS_ACTION_EXEC_LIVE")]
    assert not active, "shipped unit must NOT enable live execution (operator drop-in only)"


# ── the write contract ──────────────────────────────────────────────────────

def test_registry_exposes_boundary_split():
    port = _free_port()
    proc = _spawn(port)
    try:
        status, body = _get(port, "/api/control/registry")
        assert status == 200
        assert body["live"] is False  # dry-run default
        ids = {c["id"]: c for c in body["controls"]}
        # R10212: selfdef/perimeter are proxy-only; sovereign-os-owned execute-local
        assert ids["selfdef"]["execute_local"] is False
        assert ids["perimeter"]["execute_local"] is False
        assert ids["flex-profile"]["execute_local"] is True
        assert ids["cpu-mode"]["execute_local"] is True
        assert "selfdef" in body["owned"]["proxy"] and "perimeter" in body["owned"]["proxy"]
        assert "flex-profile" in body["owned"]["local"]
    finally:
        proc.kill()


def test_execute_sovereign_owned_is_dry_run_200():
    port = _free_port()
    proc = _spawn(port)
    try:
        status, body = _post(port, "/api/control/execute", {
            "control_id": "flex-profile",
            "args": {"key": "gpu.utilization", "value": "0.9"},
        })
        assert status == 200, body
        assert body["ok"] is True and body["dry_run"] is True
        assert body["would_run"][:1] == ["sovereign-osctl"]  # nothing actually ran
    finally:
        proc.kill()


def test_execute_selfdef_owned_is_boundary_rejected_409():
    port = _free_port()
    proc = _spawn(port)
    try:
        status, body = _post(port, "/api/control/execute", {"control_id": "selfdef"})
        assert status == 409, body
        assert body.get("boundary") is True
        assert "R10212" in body["error"] and "proxy" in body["error"].lower()
    finally:
        proc.kill()


def test_execute_privileged_without_confirm_is_403():
    port = _free_port()
    proc = _spawn(port)
    try:
        status, body = _post(port, "/api/control/execute", {
            "control_id": "cpu-mode", "args": {"mode": "balanced"},
        })
        assert status == 403, body
        assert body["ok"] is False
    finally:
        proc.kill()


def test_execute_unknown_control_is_404():
    port = _free_port()
    proc = _spawn(port)
    try:
        status, body = _post(port, "/api/control/execute", {"control_id": "no-such-control"})
        assert status == 404, body
        assert "unknown control" in body["error"]
    finally:
        proc.kill()


def test_malformed_body_is_400():
    port = _free_port()
    proc = _spawn(port)
    try:
        assert _post(port, "/api/control/execute", b"not json")[0] == 400
        assert _post(port, "/api/control/execute", {"no": "control_id"})[0] == 400
    finally:
        proc.kill()


def test_wrong_path_and_method():
    port = _free_port()
    proc = _spawn(port)
    try:
        assert _post(port, "/api/control/other", {"control_id": "flex-profile"})[0] == 404
        assert _get(port, "/api/bogus")[0] == 404
        assert _post(port, "/api/control/execute", {"control_id": "flex-profile"},
                     method="PUT")[0] == 405
    finally:
        proc.kill()
