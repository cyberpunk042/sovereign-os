"""2026-07-19 — notifykit + wikiops gates.

Every operator-verbatim rule from the standing directive
(docs/standing-directives/2026-07-19-notification-wiki-operability-mode.md)
gets an executable assertion:

  A. "for sms it will require a high priority, high urgency by default
     and it will be conifugrable"
  B. "for if with no SMS at all then the starting point is resent
     require urgent and high priority"
  C. "setting a global default override and only those set to static
     value modified remain as is"
  D. wiki mutations dispatch ONLY through the target wiki's own tool
     chain, dry-run by default (operator-confirmed resolution).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.notifykit import ChannelRegistry, Event, NotifyConfig  # noqa: E402
from tools.notifykit.config import BUILTIN_GATES, NO_SMS_RESEND_GATE  # noqa: E402

WIKIOPS = REPO_ROOT / "tools" / "wikiops.py"


def _cfg(doc: dict) -> NotifyConfig:
    return NotifyConfig.from_dict(doc)


# ── A: SMS default gate high/high, configurable ────────────────────────


def test_twilio_builtin_gate_is_high_high():
    assert BUILTIN_GATES["twilio"] == {
        "min_priority": "high", "min_urgency": "high"}


def test_twilio_gate_blocks_normal_and_passes_high_high():
    cfg = _cfg({"channels": {"sms": {"kind": "twilio", "enabled": True}}})
    gate = cfg.effective_gate("sms")
    assert not Event("t", "m", priority="normal", urgency="high").meets(**{
        "min_priority": gate["min_priority"], "min_urgency": gate["min_urgency"]})
    assert Event("t", "m", priority="high", urgency="high").meets(
        gate["min_priority"], gate["min_urgency"])


def test_twilio_gate_is_configurable():
    cfg = _cfg({"channels": {"sms": {
        "kind": "twilio", "enabled": True,
        "min_priority": "low", "min_urgency": "low"}}})
    assert cfg.effective_gate("sms") == {
        "min_priority": "low", "min_urgency": "low"}


# ── B: no-SMS → resend starting point urgent + high ────────────────────


def test_no_sms_resend_starting_point_urgent_high():
    assert NO_SMS_RESEND_GATE == {
        "min_priority": "high", "min_urgency": "urgent"}
    cfg = _cfg({"channels": {"mail": {"kind": "resend", "enabled": True}}})
    assert cfg.effective_gate("mail") == NO_SMS_RESEND_GATE


def test_with_sms_present_resend_baseline_applies():
    cfg = _cfg({"channels": {
        "mail": {"kind": "resend", "enabled": True},
        "sms": {"kind": "twilio", "enabled": True},
    }})
    assert cfg.effective_gate("mail") == BUILTIN_GATES["resend"]


def test_disabled_twilio_counts_as_no_sms_at_all():
    cfg = _cfg({"channels": {
        "mail": {"kind": "resend", "enabled": True},
        "sms": {"kind": "twilio", "enabled": False},
    }})
    assert cfg.effective_gate("mail") == NO_SMS_RESEND_GATE


def test_no_sms_starting_point_remains_operator_configurable():
    cfg = _cfg({"channels": {"mail": {
        "kind": "resend", "enabled": True, "min_urgency": "normal"}}})
    assert cfg.effective_gate("mail")["min_urgency"] == "normal"


# ── C: global override; static pins remain as-is ───────────────────────


def test_global_override_sweeps_non_static_values():
    cfg = _cfg({
        "global_override": {"min_priority": "max"},
        "channels": {
            "push": {"kind": "ntfy", "enabled": True, "min_priority": "low"},
        },
    })
    assert cfg.effective_gate("push")["min_priority"] == "max"


def test_static_pinned_value_remains_as_is_under_global_override():
    cfg = _cfg({
        "global_override": {"min_priority": "max", "min_urgency": "urgent"},
        "channels": {
            "push": {"kind": "ntfy", "enabled": True,
                     "min_priority": {"value": "low", "static": True},
                     "min_urgency": "low"},
        },
    })
    gate = cfg.effective_gate("push")
    assert gate["min_priority"] == "low"      # static pin survives
    assert gate["min_urgency"] == "urgent"    # non-static swept


# ── registry dispatch + receipts ───────────────────────────────────────


def test_registry_gates_and_delivers_with_receipts():
    cfg = _cfg({"channels": {
        "rec": {"kind": "mock", "enabled": True,
                "min_priority": "high", "min_urgency": "high"},
        "always": {"kind": "mock", "enabled": True},
        "off": {"kind": "mock", "enabled": False},
    }})
    reg = ChannelRegistry(cfg)
    receipts = reg.dispatch(Event("t", "m", priority="normal", urgency="normal"))
    by = {r.channel: r for r in receipts}
    assert by["rec"].skipped and "gated" in by["rec"].detail
    assert by["always"].ok and not by["always"].skipped
    assert by["off"].skipped and by["off"].detail == "disabled"
    receipts = reg.dispatch(Event("t", "m", priority="max", urgency="urgent"))
    assert not {r.channel: r for r in receipts}["rec"].skipped


def test_event_axis_validation():
    import pytest
    with pytest.raises(ValueError):
        Event("t", "m", priority="urgent")   # urgent is an URGENCY level
    assert Event("t", "m", priority="max").ntfy_priority == 5


# ── D: wikiops — own-tool-chain dispatch, dry-run default ──────────────


def _wikiops(*args: str, registry: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WIKIOPS), "--registry", str(registry), *args],
        capture_output=True, text=True,
    )


def _write_registry(tmp_path: Path) -> Path:
    reg = tmp_path / "wikis.toml"
    reg.write_text(
        'default = "hub"\n'
        '[wikis.hub]\nkind = "info-hub"\n'
        f'root = "{tmp_path}/hub"\npython = ".venv/bin/python"\n'
    )
    return reg


def test_wikiops_targets_and_default(tmp_path):
    reg = _write_registry(tmp_path)
    r = _wikiops("targets", "--json", registry=reg)
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert rows[0]["name"] == "hub" and rows[0]["default"] is True


def test_wikiops_mutating_op_is_dry_run_by_default(tmp_path):
    reg = _write_registry(tmp_path)
    r = _wikiops("run", "--op", "archive", "Some Page", registry=reg)
    assert r.returncode == 0, r.stderr
    assert "DRY-RUN" in r.stdout
    # dispatches through the WIKI'S OWN tool chain — gateway archive
    assert "-m tools.gateway archive" in r.stdout
    assert ".venv/bin/python" in r.stdout


def test_wikiops_ops_are_the_wikis_own_tools(tmp_path):
    from tools.wikiops import INFO_HUB_OPS
    modules = {spec["module"] for spec in INFO_HUB_OPS.values()}
    # only the info-hub's own validated tool modules — never file writes
    assert modules == {"tools.pipeline", "tools.gateway", "tools.view"}
    # deletion maps to the wiki's own archive verb
    assert INFO_HUB_OPS["archive"]["module"] == "tools.gateway"


def test_wikiops_unknown_op_and_missing_registry_rc2(tmp_path):
    reg = _write_registry(tmp_path)
    assert _wikiops("run", "--op", "nope", registry=reg).returncode == 2
    assert _wikiops(
        "targets", registry=tmp_path / "absent.toml").returncode == 2


def test_wikiops_apply_refuses_missing_root(tmp_path):
    reg = _write_registry(tmp_path)  # root dir not created
    r = _wikiops("run", "--op", "archive", "X", "--apply", registry=reg)
    assert r.returncode == 2
    assert "not present" in r.stderr
