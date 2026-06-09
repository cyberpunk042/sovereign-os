"""morning-brief ⇄ autohealth status schema binding (R352/R308).

morning-brief's `probe_autohealth` surfaces the host health verdict in the
operator's daily brief. The R308 `autohealth status --json` verb returns
the cached latest tick under a NESTED `last_tick` object — the `verdict` +
`severity_counts` live there, NOT at the top level. The probe used to read
top-level `severity`/`verdict`/`worst_severity`, which `status` never
emits, so the brief silently showed `severity=None` even when the host had
real findings. The L3 test couldn't catch it because it explicitly
tolerates `severity is None` ("may be None if probe unavailable").

This gate locks the producer→consumer binding both ways:
  1. autohealth status --json really nests verdict + severity_counts under
     last_tick (the producer schema the probe depends on).
  2. probe_autohealth, fed that exact shape, populates severity from
     last_tick.verdict (the consumer extraction works).
A rename on either side fails loudly instead of silently blanking the
brief's health signal.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIEF = REPO_ROOT / "scripts" / "intelligence" / "morning-brief.py"
AUTOHEALTH = REPO_ROOT / "scripts" / "diagnostics" / "autohealth.py"


def _load_brief():
    spec = importlib.util.spec_from_file_location("morning_brief_bind", BRIEF)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_autohealth_status_nests_verdict_under_last_tick(tmp_path):
    """The producer schema the probe binds to.

    `status` only surfaces a `last_tick` object once at least one tick has
    been recorded; on a fresh host its `last_tick` is null. So tick FIRST
    into an isolated temp state (overlay `state_path`), then read `status`
    from the same state — deterministic + no pollution of the host's real
    /var/lib/sovereign-os/autohealth.jsonl.
    """
    state = tmp_path / "autohealth.jsonl"
    overlay = tmp_path / "autohealth.toml"
    overlay.write_text(f'state_path = "{state}"\n', encoding="utf-8")

    tick = subprocess.run(
        [sys.executable, str(AUTOHEALTH), "tick", "--config", str(overlay),
         "--json"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert tick.returncode in (0, 1), (
        f"autohealth tick exited {tick.returncode}: {tick.stderr[:300]}"
    )

    cp = subprocess.run(
        [sys.executable, str(AUTOHEALTH), "status", "--config", str(overlay),
         "--json"],
        capture_output=True, text=True, timeout=30, cwd=REPO_ROOT,
    )
    assert cp.returncode in (0, 1), (
        f"autohealth status --json exited {cp.returncode}: {cp.stderr[:300]}"
    )
    doc = json.loads(cp.stdout)
    last = doc.get("last_tick")
    assert isinstance(last, dict), (
        "autohealth status --json (after a tick) no longer nests `last_tick` "
        "— the morning-brief probe reads the verdict from there."
    )
    assert "verdict" in last, (
        "autohealth status last_tick no longer carries `verdict`; the brief "
        "binds to last_tick.verdict for its health signal. Update the probe."
    )


def test_probe_autohealth_extracts_verdict_from_last_tick(monkeypatch):
    """The consumer extraction: fed a realistic status shape, the probe
    must populate severity from last_tick.verdict (not leave it None)."""
    mb = _load_brief()

    canned = {
        "ok": True,
        "rc": 1,
        "stdout_text": "",
        "stderr_text": "",
        "json": {
            "tick_count": 7,
            "last_tick": {
                "verdict": "attention-findings",
                "severity_counts": {
                    "critical": 0, "attention": 2, "informational": 3},
                "tick_at": "2026-06-08T21:00:00Z",
            },
        },
    }
    monkeypatch.setattr(mb, "_probe", lambda args, timeout: canned)
    out = mb.probe_autohealth(5)
    assert out["available"] is True
    assert out["severity"] == "attention-findings", (
        f"probe_autohealth failed to extract verdict from last_tick — "
        f"producer→consumer binding broken: {out}")
    assert out["severity_counts"] == {
        "critical": 0, "attention": 2, "informational": 3}, out
    assert out["tick"] == 7, f"tick should come from tick_count: {out}"


def test_probe_autohealth_graceful_when_unavailable(monkeypatch):
    """Defence: an unavailable probe leaves severity None, never raises."""
    mb = _load_brief()
    monkeypatch.setattr(
        mb, "_probe",
        lambda args, timeout: {"ok": False, "rc": -1, "stdout_text": "",
                               "stderr_text": "boom", "json": None},
    )
    out = mb.probe_autohealth(5)
    assert out["available"] is False and out["severity"] is None


def test_critical_findings_verdict_escalates_to_critical_signals(monkeypatch):
    """autohealth's verdict vocabulary is critical-findings /
    attention-findings / all-clear — NOT critical/high. build_brief must
    escalate a `critical-findings` verdict (or any critical in
    severity_counts) into critical_signals; attention-findings must NOT.
    Locks the vocabulary so a regression to `in ("critical","high")` —
    which silently never matches — fails here."""
    mb = _load_brief()
    monkeypatch.setattr(mb, "probe_next_action",
                        lambda limit, timeout: {"available": True, "items": []})
    monkeypatch.setattr(mb, "probe_module_state",
                        lambda limit, timeout: {"available": True, "items": [],
                                                "attention_count": 0})

    def crit(_timeout):
        return {"available": True, "rc": 1, "severity": "critical-findings",
                "severity_counts": {"critical": 1, "attention": 0,
                                    "informational": 0}, "tick": 9}

    monkeypatch.setattr(mb, "probe_autohealth", crit)
    cfg = {"include_autohealth": True, "include_guide_suggestion": False}
    brief = mb.build_brief(cfg)
    assert any("autohealth" in s for s in brief["critical_signals"]), (
        f"critical-findings did not escalate to critical_signals: "
        f"{brief['critical_signals']}")
    assert brief["critical_signals_count"] >= 1

    # attention-findings must NOT escalate.
    def attn(_timeout):
        return {"available": True, "rc": 1, "severity": "attention-findings",
                "severity_counts": {"critical": 0, "attention": 2,
                                    "informational": 1}, "tick": 9}

    monkeypatch.setattr(mb, "probe_autohealth", attn)
    brief2 = mb.build_brief(cfg)
    assert not any("autohealth" in s for s in brief2["critical_signals"]), (
        f"attention-findings wrongly escalated: {brief2['critical_signals']}")
