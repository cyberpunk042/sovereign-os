"""SDD-509 Phase C — the step-up surface on the control-exec daemon.

The read-only status (GET /api/control/stepup) that the config pane + step-up
modal prefill from, and the auth sub-actions that ride the ONE write endpoint
(POST /api/control/execute with a `stepup` body key): verify a factor, request
an out-of-band OTP, enroll. Spawned against a tmp step-up dir (never the host).
"""
from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON = REPO_ROOT / "scripts" / "operator" / "control-exec-api.py"
STEPUP = REPO_ROOT / "scripts" / "operator" / "lib" / "stepup.py"


def _stepup_mod():
    spec = importlib.util.spec_from_file_location("stepup_apitest", STEPUP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn(port: int, stepup_dir: Path):
    env = {
        "CONTROL_EXEC_API_BIND": "127.0.0.1",
        "CONTROL_EXEC_API_PORT": str(port),
        "SOVEREIGN_OS_STEPUP_DIR": str(stepup_dir),
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


def _post(port: int, path: str, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_status_reflects_enrollment_and_step_up_controls(tmp_path):
    port = _free_port()
    proc = _spawn(port, tmp_path)
    try:
        status, body = _get(port, "/api/control/stepup")
        assert status == 200, body
        assert body["enrolled"] is False and body["factors"] == []
        assert body["break_glass_remaining"] == 0
        # os-profile + runtime-mode carry auth: step-up in the registry
        assert "os-profile" in body["step_up_controls"]
        assert "runtime-mode" in body["step_up_controls"]
    finally:
        proc.kill()


def test_enroll_then_verify_flow(tmp_path):
    port = _free_port()
    proc = _spawn(port, tmp_path)
    su = _stepup_mod()
    try:
        # enroll on a fresh box → secret + otpauth + 10 recovery codes, ONCE
        status, body = _post(port, "/api/control/execute", {"stepup": {"action": "enroll"}})
        assert status == 200 and body["ok"] is True, body
        secret = body["secret"]
        assert secret and body["provisioning_uri"].startswith("otpauth://")
        assert len(body["recovery_codes"]) == 10

        # status now shows enrolled + the totp/breakglass factors
        _, st = _get(port, "/api/control/stepup")
        assert st["enrolled"] is True
        assert "totp" in st["factors"] and "breakglass" in st["factors"]
        assert st["break_glass_remaining"] == 10

        # a wrong TOTP code → 401, not elevated
        status, body = _post(port, "/api/control/execute",
                             {"stepup": {"action": "verify", "factor": "totp", "code": "000000"}})
        assert status == 401 and body["elevated"] is False

        # a correct TOTP code → 200 elevated (mints an elevation for cockpit-web)
        code = su.totp_code(secret, time.time())
        status, body = _post(port, "/api/control/execute",
                             {"stepup": {"action": "verify", "factor": "totp", "code": code}})
        assert status == 200 and body["elevated"] is True, body
    finally:
        proc.kill()


def test_reenroll_requires_a_live_elevation(tmp_path):
    port = _free_port()
    proc = _spawn(port, tmp_path)
    su = _stepup_mod()
    try:
        # first enrollment is open (fresh box)
        _, first = _post(port, "/api/control/execute", {"stepup": {"action": "enroll"}})
        secret = first["secret"]
        # a SECOND enroll with no elevation → 401 step_up_required
        status, body = _post(port, "/api/control/execute", {"stepup": {"action": "enroll"}})
        assert status == 401 and body["step_up_required"] is True, body
        # verify a factor → elevation, then re-enroll succeeds ONCE (consumes it)
        code = su.totp_code(secret, time.time())
        _post(port, "/api/control/execute",
              {"stepup": {"action": "verify", "factor": "totp", "code": code}})
        status, body = _post(port, "/api/control/execute", {"stepup": {"action": "enroll"}})
        assert status == 200 and body["ok"] is True and body["reenrolled"] is True, body
        # the elevation was single-use — a third enroll is gated again
        assert _post(port, "/api/control/execute",
                     {"stepup": {"action": "enroll"}})[0] == 401
    finally:
        proc.kill()


def test_request_otp_is_inert_without_notifykit(tmp_path):
    port = _free_port()
    proc = _spawn(port, tmp_path)
    try:
        # no configured Twilio/Resend channel → the phone/email factor can't
        # deliver; the daemon reports it cleanly (503) instead of crashing.
        status, body = _post(port, "/api/control/execute",
                             {"stepup": {"action": "request_otp", "factor": "sms"}})
        assert status == 503 and body["ok"] is False, body
        # a bogus factor is a clean 400
        assert _post(port, "/api/control/execute",
                     {"stepup": {"action": "request_otp", "factor": "smoke-signal"}})[0] == 400
        # an unknown stepup action is a clean 400
        assert _post(port, "/api/control/execute",
                     {"stepup": {"action": "teleport"}})[0] == 400
    finally:
        proc.kill()


def test_tier_curation_is_gated_and_takes_effect(tmp_path):
    port = _free_port()
    proc = _spawn(port, tmp_path)
    try:
        # before enrollment the gate is off → curation is open (bootstrap)
        status, body = _post(port, "/api/control/execute",
                             {"stepup": {"action": "set_tier", "control_id": "cpu-mode",
                                         "tier": "step-up"}})
        assert status == 200 and body["ok"] is True, body
        # it shows up as overridden onto step-up in the status
        _, st = _get(port, "/api/control/stepup")
        cur = {c["id"]: c for c in st["curatable_controls"]}
        assert cur["cpu-mode"]["tier"] == "step-up" and cur["cpu-mode"]["overridden"] is True

        # once enrolled, curation requires a live elevation
        _post(port, "/api/control/execute", {"stepup": {"action": "enroll"}})
        status, body = _post(port, "/api/control/execute",
                             {"stepup": {"action": "clear_tier", "control_id": "cpu-mode"}})
        assert status == 401 and body["step_up_required"] is True, body

        # selfdef can never be curated (always proxy-only)
        assert _post(port, "/api/control/execute",
                     {"stepup": {"action": "set_tier", "control_id": "selfdef",
                                 "tier": "none"}})[0] == 400
    finally:
        proc.kill()


def test_execute_path_still_works_alongside_stepup(tmp_path):
    """The control-execution path is unchanged by the stepup body dispatch."""
    port = _free_port()
    proc = _spawn(port, tmp_path)
    try:
        status, body = _post(port, "/api/control/execute", {
            "control_id": "flex-profile",
            "args": {"key": "gpu.utilization", "value": "0.9"},
        })
        assert status == 200 and body["dry_run"] is True, body
        # a body with neither control_id nor stepup is a 400
        assert _post(port, "/api/control/execute", {"nonsense": 1})[0] == 400
    finally:
        proc.kill()
