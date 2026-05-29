"""MS022 sovereign-osctl ms022-doctor verb — contract test.

Locks the new operator-discoverable triage verb shipped to round
out the MS022 vertical's CLI surface. Drift-protection:

  - the verb dispatch arm exists in scripts/sovereign-osctl
  - --help advertises the verb + its flags
  - the underlying ms022-doctor.py script loads + carries the
    right check shape (5 checks, severity enum, JSON output)
  - the doctor's classifier states match the proxy's states
    (so the doctor's classification of `state` values doesn't
    drift from what the proxy emits)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
DOCTOR = REPO_ROOT / "scripts" / "diagnostics" / "ms022-doctor.py"
PROXY = REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py"


def _load_doctor():
    spec = importlib.util.spec_from_file_location("ms022_doctor", DOCTOR)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ms022_doctor"] = mod
    spec.loader.exec_module(mod)
    return mod


def _osctl_help() -> str:
    proc = subprocess.run(
        [str(OSCTL), "--help"], capture_output=True, text=True, check=False,
    )
    return proc.stdout + proc.stderr


def test_doctor_script_present():
    assert DOCTOR.is_file(), f"missing doctor script: {DOCTOR}"


def test_doctor_module_loads():
    mod = _load_doctor()
    for fn in (
        "check_proxy_daemon_health",
        "check_proxy_state",
        "check_proxy_envelope_shape",
        "check_systemd_unit",
        "check_master_banner_proxied",
        "main",
    ):
        assert hasattr(mod, fn), f"doctor module missing {fn!r}"


def test_doctor_severity_enum_matches_cli_mirror_doctor_convention():
    """The 3-tier severity enum (0/1/2) matches the selfdef-side
    cli-mirror-doctor pattern so operators don't get two competing
    severity vocabularies."""
    mod = _load_doctor()
    assert mod.SEV_PASS == 0
    assert mod.SEV_WARN == 1
    assert mod.SEV_FAIL == 2
    assert mod.SEV_JSON == {0: "pass", 1: "warn", 2: "fail"}


def test_doctor_runs_five_checks():
    """The doctor MUST run all 5 checks. Drift = silent observability gap."""
    mod = _load_doctor()
    # Stub every check to return a predictable severity-pass result.
    def _stub_pass(name: str):
        return lambda: {
            "name": name, "severity": 0, "detail": "stubbed", "fix": "",
        }
    with patch.object(mod, "check_proxy_daemon_health",
                       _stub_pass("proxy-daemon")), \
         patch.object(mod, "check_proxy_state",
                       _stub_pass("proxy-state")), \
         patch.object(mod, "check_proxy_envelope_shape",
                       _stub_pass("proxy-envelope")), \
         patch.object(mod, "check_systemd_unit",
                       _stub_pass("systemd-unit")), \
         patch.object(mod, "check_master_banner_proxied",
                       _stub_pass("master-banner")):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main(["--json"])
        assert rc == 0
        body = json.loads(buf.getvalue())
        names = {c["name"] for c in body["checks"]}
        assert names == {
            "proxy-daemon", "proxy-state", "proxy-envelope",
            "systemd-unit", "master-banner",
        }, f"doctor must run all 5 checks; got {names!r}"


def test_doctor_json_envelope_carries_canonical_keys():
    """The --json output shape is the contract for monitoring
    integrations. Lock it."""
    mod = _load_doctor()
    def _stub_pass(name):
        return lambda: {"name": name, "severity": 0, "detail": "ok", "fix": ""}
    with patch.object(mod, "check_proxy_daemon_health", _stub_pass("proxy-daemon")), \
         patch.object(mod, "check_proxy_state", _stub_pass("proxy-state")), \
         patch.object(mod, "check_proxy_envelope_shape", _stub_pass("proxy-envelope")), \
         patch.object(mod, "check_systemd_unit", _stub_pass("systemd-unit")), \
         patch.object(mod, "check_master_banner_proxied", _stub_pass("master-banner")):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            mod.main(["--json"])
        body = json.loads(buf.getvalue())
        assert body["domain"] == "MS022"
        assert body["worst_severity"] == "pass"
        for c in body["checks"]:
            assert {"name", "severity", "detail", "fix"} == set(c)


def test_doctor_strict_mode_exits_1_on_warn():
    """--strict exits 1 when ANY check is non-pass (default is the
    worst-severity exit-code class — strict tightens to exit-1 on
    yellow so CI pipelines fail-fast)."""
    mod = _load_doctor()
    def _stub_warn():
        return {"name": "proxy-state", "severity": 1, "detail": "warn",
                "fix": "do thing"}
    def _stub_pass(name):
        return lambda: {"name": name, "severity": 0, "detail": "ok", "fix": ""}
    with patch.object(mod, "check_proxy_daemon_health", _stub_pass("proxy-daemon")), \
         patch.object(mod, "check_proxy_state", _stub_warn), \
         patch.object(mod, "check_proxy_envelope_shape", _stub_pass("proxy-envelope")), \
         patch.object(mod, "check_systemd_unit", _stub_pass("systemd-unit")), \
         patch.object(mod, "check_master_banner_proxied", _stub_pass("master-banner")):
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mod.main(["--strict"])
        assert rc == 1, f"--strict should exit 1 on warn; got {rc}"


def test_doctor_fail_exits_2_without_strict():
    """Worst-severity FAIL maps to exit 2 even without --strict."""
    mod = _load_doctor()
    def _stub_fail():
        return {"name": "proxy-daemon", "severity": 2, "detail": "down",
                "fix": "start it"}
    def _stub_pass(name):
        return lambda: {"name": name, "severity": 0, "detail": "ok", "fix": ""}
    with patch.object(mod, "check_proxy_daemon_health", _stub_fail), \
         patch.object(mod, "check_proxy_state", _stub_pass("proxy-state")), \
         patch.object(mod, "check_proxy_envelope_shape", _stub_pass("proxy-envelope")), \
         patch.object(mod, "check_systemd_unit", _stub_pass("systemd-unit")), \
         patch.object(mod, "check_master_banner_proxied", _stub_pass("master-banner")):
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            rc = mod.main([])
        assert rc == 2


def test_doctor_proxy_url_default_matches_systemd_unit():
    """The doctor's default PROXY_URL must match the port the
    systemd unit binds. Drift = the doctor probes the wrong port
    after a default-port change."""
    mod = _load_doctor()
    unit = (REPO_ROOT / "systemd" / "system" /
            "sovereign-ms022-sse-quota-api.service").read_text()
    # Find MS022_SSE_QUOTA_API_PORT= value
    for line in unit.splitlines():
        if "MS022_SSE_QUOTA_API_PORT=" in line:
            unit_port = int(line.split("=")[-1])
            break
    else:
        raise AssertionError("systemd unit missing port environment")
    assert f":{unit_port}" in mod.PROXY_URL, (
        f"doctor PROXY_URL {mod.PROXY_URL!r} doesn't include the unit port "
        f"{unit_port}"
    )


def test_doctor_proxy_state_check_handles_all_classifier_states():
    """The doctor's proxy-state check classifies each of the 4
    states the proxy emits (ok / approaching / saturated /
    unreachable). Drift between the proxy's enum and the doctor's
    handler = silent miscategorization."""
    mod = _load_doctor()
    proxy_spec = importlib.util.spec_from_file_location("ms022_proxy", PROXY)
    proxy_mod = importlib.util.module_from_spec(proxy_spec)
    sys.modules["ms022_proxy"] = proxy_mod
    proxy_spec.loader.exec_module(proxy_mod)
    proxy_states = set(proxy_mod._version_payload()["states"])
    for state in proxy_states:
        with patch.object(mod, "_fetch_json", return_value={"state": state}):
            result = mod.check_proxy_state()
        assert result["name"] == "proxy-state"
        assert result["severity"] in (0, 1, 2), (
            f"doctor produced unknown severity for proxy state {state!r}: "
            f"{result['severity']!r}"
        )


def test_sovereign_osctl_dispatches_ms022_doctor():
    """The osctl dispatch arm must call the doctor script. Drift
    here = the named verb ships but doesn't route anywhere."""
    body = OSCTL.read_text()
    assert "  ms022-doctor)" in body, (
        "sovereign-osctl missing ms022-doctor dispatch arm"
    )
    assert "scripts/diagnostics/ms022-doctor.py" in body, (
        "ms022-doctor arm must invoke the doctor script"
    )


def test_sovereign_osctl_help_lists_ms022_doctor():
    """The verb MUST appear in --help so operators discover it."""
    help_text = _osctl_help()
    assert "ms022-doctor" in help_text, (
        "sovereign-osctl --help missing ms022-doctor verb — operators "
        "won't discover it"
    )
    # Help block carries severity-exit-code explanation + R10212 note.
    idx = help_text.find("ms022-doctor")
    section = help_text[idx : idx + 600]
    assert "GREEN" in section or "YELLOW" in section or "RED" in section, (
        f"help text for ms022-doctor must explain the GREEN/YELLOW/RED "
        f"exit-code class so operators write CI scripts correctly; "
        f"got:\n{section}"
    )
    assert "R10212" in section, (
        "help text for ms022-doctor must reference R10212 (read-only "
        "doctrine) so operators know the verb never mutates"
    )
