#!/usr/bin/env python3
"""tests/unit/test_ms003_writer_signing.py — MS003 wiring proof (SDD-990).

End-to-end evidence that the SDD-989 signing primitive is wired into the
decision-writers: with an operator ed25519 key provisioned, a writer's PERSISTED
record (the durable ledger line, not just the API echo) carries a real
`ms003:ed25519:` signature that `ms003.verify()` accepts, and tampering the
record breaks verification; without a key the writer falls back to the historical
`unsigned-pending-MS003` placeholder — byte-identical to pre-MS003 behaviour.

Two representatives span the families + both import styles the writers use:
`memory-decide` (intelligence, in-process) and `approval-decide` (lifecycle,
subprocess). The signing helper is uniform across all eight writers, so these
exercise the mechanism the others share. Real-crypto cases skip cleanly when the
system `openssl` cannot do ed25519.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MS003 = REPO / "scripts" / "lib" / "ms003.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ms003 = _load("ms003_wtr", MS003)


def _openssl_has_ed25519() -> bool:
    try:
        return subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519"],
                              capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


needs_ed25519 = pytest.mark.skipif(
    not _openssl_has_ed25519(), reason="openssl lacks ed25519")


def _provision_key(tmp_path, monkeypatch) -> bytes:
    """Mint an operator key at a temp path + return its raw 32-byte public key."""
    key = tmp_path / "ms003.key"
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(key))
    assert ms003._gen_key() == 0
    pub = ms003._pub_raw_from_key(key)
    assert pub is not None and len(pub) == 32
    return pub


def _seed_memory_decide(tmp_path, monkeypatch):
    md = _load("md_uut", REPO / "scripts" / "intelligence" / "memory-decide.py")
    st = tmp_path / "memory.json"
    st.write_text(json.dumps({"pending": [
        {"id": "mc-001", "op": "promote", "mtype": "semantic"}]}))
    monkeypatch.setattr(md, "MEMORY_STATE", st)
    monkeypatch.setattr(md._core, "MEMORY_STATE", st)
    monkeypatch.setattr(md, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(md, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return md


# ── memory-decide (intelligence family, in-process) ───────────────────────────

@needs_ed25519
def test_memory_decide_persisted_record_verifies(tmp_path, monkeypatch):
    md = _seed_memory_decide(tmp_path, monkeypatch)
    pub = _provision_key(tmp_path, monkeypatch)

    r = md.decide("mc-001", "approve", confirm=True)
    assert r["ok"] is True
    # the API result is really signed + verifies
    assert ms003.is_signed(r["signature"])
    assert ms003.verify(r, r["signature"], pub) is True
    # the DURABLE ledger decision is really signed + verifies
    led = json.loads(md.LEDGER.read_text().strip())
    assert ms003.is_signed(led["signature"])
    assert ms003.verify(led, led["signature"], pub) is True
    # tampering the persisted record breaks verification
    assert ms003.verify({**led, "id": "TAMPERED"}, led["signature"], pub) is False


def test_memory_decide_keyless_is_placeholder(tmp_path, monkeypatch):
    md = _seed_memory_decide(tmp_path, monkeypatch)
    monkeypatch.setenv("SOVEREIGN_OS_MS003_KEY", str(tmp_path / "absent.key"))

    r = md.decide("mc-001", "approve", confirm=True)
    assert r["signature"] == "unsigned-pending-MS003"
    led = json.loads(md.LEDGER.read_text().strip())
    assert led["signature"] == "unsigned-pending-MS003"


# ── approval-decide (lifecycle family, subprocess) ────────────────────────────

def _approval_env(tmp_path, with_key: bool) -> dict:
    env = {**os.environ,
           "SOVEREIGN_OS_APPROVALS": str(tmp_path / "approvals.json"),
           "SOVEREIGN_OS_APPROVAL_LEDGER": str(tmp_path / "ledger.jsonl"),
           "SOVEREIGN_OS_SPAN_STORE": str(tmp_path / "spans.jsonl")}
    env["SOVEREIGN_OS_MS003_KEY"] = str(
        tmp_path / ("ms003.key" if with_key else "absent.key"))
    return env


def _run_approval(env, args) -> dict:
    core = REPO / "scripts" / "lifecycle" / "approval-decide.py"
    r = subprocess.run([sys.executable, str(core), *args],
                       capture_output=True, text=True, env=env)
    return json.loads(r.stdout)


@needs_ed25519
def test_approval_decide_persisted_record_verifies(tmp_path, monkeypatch):
    pub = _provision_key(tmp_path, monkeypatch)
    env = _approval_env(tmp_path, with_key=True)
    rid = _run_approval(env, ["request", "--title", "t",
                              "--severity", "high", "--gate", "SG1"])["id"]
    d = _run_approval(env, ["approve", rid, "--confirm", "--rationale", "reviewed"])
    assert d["ok"] is True and d["status"] == "signed"
    assert ms003.is_signed(d["signature"])
    assert ms003.verify(d, d["signature"], pub) is True
    # the durable ledger decision verifies too
    led = json.loads((tmp_path / "ledger.jsonl").read_text().strip())
    assert ms003.is_signed(led["signature"])
    assert ms003.verify(led, led["signature"], pub) is True


def test_approval_decide_keyless_is_placeholder(tmp_path):
    env = _approval_env(tmp_path, with_key=False)
    rid = _run_approval(env, ["request", "--title", "t",
                              "--severity", "high", "--gate", "SG1"])["id"]
    d = _run_approval(env, ["approve", rid, "--confirm"])
    assert d["signature"] == "unsigned-pending-MS003"
    led = json.loads((tmp_path / "ledger.jsonl").read_text().strip())
    assert led["signature"] == "unsigned-pending-MS003"
