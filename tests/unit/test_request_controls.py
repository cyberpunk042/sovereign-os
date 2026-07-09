"""SDD-104 — the two request-producer controls (`approvals-request`,
`memory-request`) route correctly through the sanctioned R10274 exec-rail.

Verifies the rail's `_action_exec.resolve_argv` builds the exact producer argv
from a control's `change_cli` + args, that a bad enum is a 400 validation-reject,
that both are UNprivileged low-stakes intent-enqueues (no operator-key/confirm
gate), that a dry-run mutates nothing (`would_run`), and that neither is
`SELFDEF_OWNED` (R10212 boundary). No producer logic is exercised — this pins the
registry↔rail contract that makes the D-06/D-07 request buttons work.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ACTION_EXEC = REPO / "scripts" / "operator" / "_action_exec.py"


def _load():
    spec = importlib.util.spec_from_file_location("_action_exec_req", ACTION_EXEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load()
REG = A.load_registry()


# ── registry shape ─────────────────────────────────────────────────────────────

def test_both_controls_registered_unprivileged_scoped():
    for cid, panel in (("approvals-request", "d-06-pending-approvals"),
                       ("memory-request", "d-07-memory-changes")):
        c = REG.get(cid)
        assert c is not None, f"{cid} missing from control-systems.yaml"
        assert c["privileged"] is False, f"{cid} must be an unprivileged intent-enqueue"
        assert c["kind"] == "lifecycle" and c["scope"] == "scoped"
        assert panel in c["applies_to"], f"{cid} must apply to {panel}"


def test_neither_is_selfdef_owned():
    assert "approvals-request" not in A.SELFDEF_OWNED
    assert "memory-request" not in A.SELFDEF_OWNED


# ── resolve_argv builds the exact producer argv ─────────────────────────────────

def test_approvals_request_resolves_argv():
    argv, err = A.resolve_argv(
        REG["approvals-request"],
        {"gate": "SG3", "verb": "high", "title": "cloud-spend"})
    assert err is None
    assert argv == ["sovereign-osctl", "approvals", "request",
                    "--gate", "SG3", "--severity", "high", "--title", "cloud-spend"]


def test_memory_request_resolves_argv():
    argv, err = A.resolve_argv(
        REG["memory-request"], {"verb": "promote", "mtype": "semantic"})
    assert err is None
    assert argv == ["sovereign-osctl", "memory-changes", "request",
                    "promote", "--mtype", "semantic"]


def test_approvals_request_uppercase_sg_gate_survives_the_rail():
    """The SG-keys are uppercase; the rail enum is lowercase-only, so gate is a
    FREE placeholder — uppercase must pass `_SAFE_VALUE` unchanged (else a
    web-created request would carry a mangled, non-signable gate)."""
    for g in ("SG1", "SG2", "SG3", "SG4", "SG5"):
        argv, err = A.resolve_argv(
            REG["approvals-request"], {"gate": g, "verb": "medium", "title": "operator-request"})
        assert err is None and g in argv


# ── bad enum → validation reject ────────────────────────────────────────────────

def test_bad_severity_enum_rejected():
    _, err = A.resolve_argv(
        REG["approvals-request"], {"gate": "SG3", "verb": "urgent", "title": "x"})
    assert err and "verb" in err


def test_bad_memory_op_enum_rejected():
    _, err = A.resolve_argv(REG["memory-request"], {"verb": "delete", "mtype": "semantic"})
    assert err and "verb" in err


def test_free_value_forbids_shell_metacharacters():
    """`_SAFE_VALUE` bans whitespace/`/` — a free title/scope carrying a path or a
    space is rejected (the R10212 arg allowlist; must not be widened)."""
    _, err = A.resolve_argv(
        REG["approvals-request"], {"gate": "SG3", "verb": "high", "title": "cloud spend"})
    assert err and "title" in err
    _, err2 = A.resolve_argv(REG["memory-request"], {"verb": "promote", "mtype": "../etc"})
    assert err2 and "mtype" in err2


# ── execute() dry-run: unprivileged, mutates nothing ────────────────────────────

def test_execute_dry_run_unprivileged_no_confirm():
    r = A.execute("approvals-request",
                  {"gate": "SG3", "verb": "high", "title": "cloud-spend"}, dry_run=True)
    assert r["ok"] and r["code"] == 200 and r["dry_run"] is True
    # unprivileged → no operator-key / confirm gate; would_run == argv (no sudo wrap)
    assert r["would_run"] == r["argv"]
    assert "confirm_required" not in r

    r2 = A.execute("memory-request", {"verb": "promote", "mtype": "semantic"}, dry_run=True)
    assert r2["ok"] and r2["dry_run"] is True and r2["would_run"] == r2["argv"]


def test_execute_bad_arg_is_400():
    r = A.execute("approvals-request",
                  {"gate": "SG3", "verb": "urgent", "title": "x"}, dry_run=True)
    assert not r["ok"] and r["code"] == 400
