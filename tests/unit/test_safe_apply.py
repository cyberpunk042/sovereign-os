"""R328 (E9.M12) — safe_apply helper library unit tests.

Layer 0/1 unit tests for the safe_apply helper module. No
subprocess spawning, no global state mutation outside tempfiles.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

import safe_apply  # noqa: E402


def test_evaluate_triple_gate_all_off():
    """No flags + no env → gates_ok=False."""
    os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
    gates, ok = safe_apply.evaluate_triple_gate(
        apply_flag=False, confirm_flag=False,
    )
    assert ok is False
    assert gates["--apply"] is False
    assert gates["--confirm-apply"] is False
    assert gates["SOVEREIGN_OS_CONFIRM_DESTROY=YES"] is False


def test_evaluate_triple_gate_all_on():
    """All 3 gates → gates_ok=True."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
    try:
        gates, ok = safe_apply.evaluate_triple_gate(
            apply_flag=True, confirm_flag=True,
        )
        assert ok is True
        assert all(gates.values())
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)


def test_evaluate_triple_gate_only_two():
    """2/3 gates → gates_ok=False."""
    os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
    gates, ok = safe_apply.evaluate_triple_gate(
        apply_flag=True, confirm_flag=True,
    )
    assert ok is False
    assert gates["--apply"] is True
    assert gates["--confirm-apply"] is True
    assert gates["SOVEREIGN_OS_CONFIRM_DESTROY=YES"] is False


def test_evaluate_triple_gate_custom_labels():
    """Custom env-var name + confirm-flag label."""
    os.environ["MY_CUSTOM_GATE"] = "DO-IT"
    try:
        gates, ok = safe_apply.evaluate_triple_gate(
            apply_flag=True, confirm_flag=True,
            env_var_name="MY_CUSTOM_GATE",
            env_var_value="DO-IT",
            confirm_flag_label="--confirm-throttle",
        )
        assert ok is True
        assert "--confirm-throttle" in gates
        assert "MY_CUSTOM_GATE=DO-IT" in gates
    finally:
        os.environ.pop("MY_CUSTOM_GATE", None)


def test_check_maintenance_window_none():
    """No window required → allowed=True, not checked."""
    r = safe_apply.check_maintenance_window(None)
    assert r["allowed"] is True
    assert r["checked"] is False


def test_check_maintenance_window_force():
    """--force override → allowed=True, not checked."""
    r = safe_apply.check_maintenance_window("any-window", force=True)
    assert r["allowed"] is True
    assert r["checked"] is False
    assert "force" in r["reason"]


def test_check_maintenance_window_unknown():
    """Unknown window → not allowed, structured reason."""
    r = safe_apply.check_maintenance_window("definitely-not-a-real-window-xyz")
    assert r["allowed"] is False
    assert r["checked"] is True
    assert "not declared" in r["reason"]


def test_run_apply_safe_dry_run_when_gates_missing():
    """No gates → would_write=False, wrote=False, write_fn NOT called."""
    os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
    called = {"n": 0}

    def write_fn():
        called["n"] += 1

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        r = safe_apply.run_apply_safe(
            verb="unit-test", round_origin="R328",
            apply_flag=False, confirm_flag=False,
            write_fn=write_fn,
            audit_path_override=audit_path,
        )
        assert r["gates_satisfied"] is False
        assert r["wrote"] is False
        assert r["would_write"] is False
        assert called["n"] == 0
    finally:
        Path(audit_path).unlink()


def test_run_apply_safe_writes_when_all_gates_on():
    """All 3 gates + write_fn → wrote=True, write_fn called once."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
    called = {"n": 0}

    def write_fn():
        called["n"] += 1

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        r = safe_apply.run_apply_safe(
            verb="unit-test-write", round_origin="R328",
            apply_flag=True, confirm_flag=True,
            write_fn=write_fn,
            audit_path_override=audit_path,
        )
        assert r["gates_satisfied"] is True
        assert r["wrote"] is True
        assert called["n"] == 1
        assert r["audit_row"]["wrote"] is True
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
        Path(audit_path).unlink()


def test_run_apply_safe_write_fn_error_caught():
    """write_fn raises → wrote=False, write_error captured, rc=2."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"

    def bad_write():
        raise OSError("synthetic write failure")

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        r = safe_apply.run_apply_safe(
            verb="unit-test-error", round_origin="R328",
            apply_flag=True, confirm_flag=True,
            write_fn=bad_write,
            audit_path_override=audit_path,
        )
        assert r["gates_satisfied"] is True
        assert r["wrote"] is False
        assert r["write_error"] is not None
        assert "synthetic" in r["write_error"]
        assert r["rc"] == 2
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
        Path(audit_path).unlink()


def test_run_apply_safe_audit_row_written():
    """Verify audit row lands in the JSONL file with full schema."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        safe_apply.run_apply_safe(
            verb="audit-verify",
            round_origin="R328",
            apply_flag=True, confirm_flag=True,
            write_fn=lambda: None,
            what_was_written={"k": "v"},
            target_path="/tmp/whatever",
            audit_path_override=audit_path,
        )
        # Read back the audit row.
        body = Path(audit_path).read_text()
        rows = [json.loads(line) for line in body.splitlines() if line.strip()]
        assert len(rows) == 1
        row = rows[0]
        assert row["verb"] == "audit-verify"
        assert row["round_origin"] == "R328"
        assert row["wrote"] is True
        assert row["gates_satisfied"] is True
        assert row["what_was_written"] == {"k": "v"}
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
        Path(audit_path).unlink()


def test_run_apply_safe_window_not_active_blocks_write():
    """Unknown window → allowed=False → write blocked even with gates ok."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
    called = {"n": 0}

    def write_fn():
        called["n"] += 1

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        r = safe_apply.run_apply_safe(
            verb="window-blocked", round_origin="R328",
            apply_flag=True, confirm_flag=True,
            write_fn=write_fn,
            maintenance_window="definitely-not-real-window-xyz",
            audit_path_override=audit_path,
        )
        # Gates ok but window not allowed → no write.
        assert r["gates_satisfied"] is True
        assert r["window_check"]["allowed"] is False
        assert r["wrote"] is False
        assert called["n"] == 0
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
        Path(audit_path).unlink()


def test_run_apply_safe_window_force_overrides():
    """force=True bypasses window check."""
    os.environ["SOVEREIGN_OS_CONFIRM_DESTROY"] = "YES"
    called = {"n": 0}
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
        audit_path = fh.name
    try:
        r = safe_apply.run_apply_safe(
            verb="force-window", round_origin="R328",
            apply_flag=True, confirm_flag=True,
            write_fn=lambda: called.__setitem__("n", called["n"] + 1),
            maintenance_window="definitely-not-real-window-xyz",
            force=True,
            audit_path_override=audit_path,
        )
        assert r["window_check"]["allowed"] is True
        assert r["wrote"] is True
        assert called["n"] == 1
    finally:
        os.environ.pop("SOVEREIGN_OS_CONFIRM_DESTROY", None)
        Path(audit_path).unlink()
