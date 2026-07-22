"""SDD-509 Phase A — the step-up gate wired into the exec rail (opt-in).

Pins that `_action_exec` gates a `step-up`-tier control on a live elevation, but
ONLY once a factor is enrolled — an un-enrolled box behaves exactly as before
(non-breaking). Exercises the gate's decision helpers with a tmp step-up dir
rather than driving a real `sudo` subprocess.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AE = REPO / "scripts" / "operator" / "_action_exec.py"
STEPUP = REPO / "scripts" / "operator" / "lib" / "stepup.py"
REGISTRY = REPO / "config" / "control-systems.yaml"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_gate_is_opt_in_disabled_until_enrolled(tmp_path, monkeypatch):
    ae = _load(AE, "ae_optin")
    monkeypatch.setenv("SOVEREIGN_OS_STEPUP_DIR", str(tmp_path))
    # nothing enrolled → the gate is a no-op (rail behaves as before)
    assert ae._stepup_enabled() is False
    # a step-up control resolves to the step-up tier regardless...
    assert ae._stepup_tier({"id": "os-profile", "auth": "step-up"}) == "step-up"
    # ...but with the gate disabled, execute() never reaches the 401 path.


def test_gate_engages_once_enrolled_and_requires_elevation(tmp_path, monkeypatch):
    ae = _load(AE, "ae_engage")
    su = _load(STEPUP, "su_engage")
    monkeypatch.setenv("SOVEREIGN_OS_STEPUP_DIR", str(tmp_path))
    # enroll a TOTP factor → step-up now engages
    secret, uri = su.enroll(tmp_path)
    assert ae._stepup_enabled() is True
    assert ae._stepup_factors() == ["totp"]
    # no elevation yet → consume fails → execute() would return 401 step-up-required
    assert ae._stepup_consume("operator") is False
    # verify a TOTP code → mint an elevation → consume now succeeds ONCE
    import time
    code = su.totp_code(secret, time.time())
    assert su.verify_and_elevate(tmp_path, "operator", code) is True
    assert ae._stepup_consume("operator") is True
    assert ae._stepup_consume("operator") is False, "single-use"


def test_verify_and_elevate_rejects_bad_code_and_unenrolled(tmp_path):
    su = _load(STEPUP, "su_reject")
    # un-enrolled → None (nothing to verify against)
    assert su.verify_and_elevate(tmp_path, "operator", "000000") is None
    su.enroll(tmp_path)
    # enrolled but wrong code → False (no elevation minted)
    assert su.verify_and_elevate(tmp_path, "operator", "000000", now=1000.0) is False
    store = su.ElevationStore(tmp_path / "elevations.json")
    assert store.check("operator", "step-up", now=1000.0) is False


def test_registry_marks_the_high_privilege_controls_step_up():
    import yaml

    systems = {s["id"]: s for s in yaml.safe_load(REGISTRY.read_text())["systems"]}
    for cid in ("os-profile", "runtime-mode"):
        assert systems[cid].get("auth") == "step-up", f"{cid} must be step-up tier"


def test_action_exec_carries_the_gate():
    src = AE.read_text(encoding="utf-8")
    assert "step_up_required" in src, "the 401 step-up path must exist"
    assert "_stepup_enabled()" in src and "_stepup_consume(" in src
    # the gate must sit AFTER the dry-run return (a preview never burns a factor)
    dry = src.index('"dry_run": True')
    gate = src.index("step_up_required")
    assert dry < gate, "step-up gate must be after the dry-run return"
