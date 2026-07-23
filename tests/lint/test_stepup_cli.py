"""SDD-509 §5 — the `sovereign-osctl stepup` manual CLI escape hatch.

The terminal mirror of the cockpit step-up surface, driving the SAME
lib/stepup.py store. Exercised via subprocess against a tmp step-up dir.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "scripts" / "operator" / "stepup-cli.py"
OSCTL = REPO / "scripts" / "sovereign-osctl"


def _run(stepup_dir: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True, text=True, timeout=15,
        env={"SOVEREIGN_OS_STEPUP_DIR": str(stepup_dir), "PATH": "/usr/bin:/bin"},
    )


def test_status_json_before_enrollment(tmp_path):
    r = _run(tmp_path, "status", "--json")
    assert r.returncode == 0, r.stderr
    st = json.loads(r.stdout)
    assert st["enrolled"] is False and st["break_glass_remaining"] == 0
    assert "curatable_controls" in st


def test_enroll_then_verify_and_tier(tmp_path):
    # enroll → prints the secret + recovery codes once
    r = _run(tmp_path, "enroll")
    assert r.returncode == 0, r.stderr
    secret = next(ln.split(": ", 1)[1].strip()
                  for ln in r.stdout.splitlines() if "TOTP secret" in ln)
    assert secret

    # a wrong code → non-zero, not elevated
    assert _run(tmp_path, "verify", "--factor", "totp", "--code", "000000").returncode == 1

    # a correct TOTP code → elevated
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "su_cli_t", REPO / "scripts" / "operator" / "lib" / "stepup.py")
    su = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(su)
    import time
    ok = _run(tmp_path, "verify", "--factor", "totp", "--code", su.totp_code(secret, time.time()))
    assert ok.returncode == 0 and "elevation minted" in ok.stdout

    # a second enroll refuses (would rotate the secret)
    assert _run(tmp_path, "enroll").returncode == 2

    # tier curation: selfdef is refused, a normal control is accepted + listed
    assert _run(tmp_path, "tier", "selfdef", "none").returncode == 2
    assert _run(tmp_path, "tier", "cpu-mode", "operator-present").returncode == 0
    lst = _run(tmp_path, "tier", "--list")
    assert lst.returncode == 0 and "cpu-mode" in lst.stdout and "operator-present" in lst.stdout


def test_osctl_dispatches_stepup():
    body = OSCTL.read_text(encoding="utf-8")
    assert "stepup)" in body and "scripts/operator/stepup-cli.py" in body
    # discoverable in the COMMANDS help block
    assert "stepup status" in body
