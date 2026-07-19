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


# ── 2026-07-19 follow-on: settings overlay + trigger frontmatter props ──
# (docs/standing-directives/2026-07-19-notification-settings-overlay-panel.md)


def test_trigger_important_true_maps_to_priority_high():
    cfg = _cfg({
        "channels": {"rec": {"kind": "mock", "enabled": True}},
        "triggers": {"wikiops": {"important": True, "reviewer": "op"}},
    })
    reg = ChannelRegistry(cfg)
    reg.dispatch(Event("t", "m", source="wikiops"))
    sent = reg.channels["rec"].sent[-1]
    assert sent.priority == "high"          # important:true → ntfy 4
    assert sent.props["reviewer"] == "op"   # unknown props ride along
    # explicit event values win over trigger defaults
    reg.dispatch(Event("t", "m", source="wikiops", priority="low"))
    assert reg.channels["rec"].sent[-1].priority == "low"


def test_overlay_json_merges_over_base(tmp_path, monkeypatch):
    base = tmp_path / "base.toml"
    base.write_text(
        '[channels.ntfy]\nkind = "ntfy"\nenabled = false\n'
        'min_priority = "low"\n')
    ov = tmp_path / "ov.json"
    ov.write_text(json.dumps({
        "channels": {"ntfy": {"enabled": True, "min_priority": "high",
                              "static": ["min_priority"]}},
        "global_override": {"min_priority": "max"},
        "triggers": {"wikiops": {"important": True}},
    }))
    cfg = NotifyConfig.load(base, ov)
    assert cfg.channels["ntfy"].enabled is True
    # overlay set the value AND pinned it static → global override loses
    assert cfg.effective_gate("ntfy")["min_priority"] == "high"
    assert cfg.triggers["wikiops"]["important"] is True


def test_cli_set_override_trigger_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_NOTIFYKIT_CONFIG",
                       str(tmp_path / "absent.toml"))
    monkeypatch.setenv("SOVEREIGN_OS_NOTIFYKIT_OVERRIDES",
                       str(tmp_path / "ov.json"))
    from tools.notifykit import cli
    assert cli.main(["set", "twilio", "enabled", "on"]) == 0
    assert cli.main(["set", "ntfy", "min_priority_static", "low"]) == 0
    assert cli.main(["global-override", "min_priority", "max"]) == 0
    assert cli.main(["trigger", "wikiops", "important", "true"]) == 0
    assert cli.main(["set", "ntfy", "min_priority", "nope"]) == 2
    assert cli.main(["set", "ntfy", "bogus_key", "x"]) == 2
    ov = json.loads((tmp_path / "ov.json").read_text())
    assert ov["channels"]["twilio"]["enabled"] is True
    assert ov["channels"]["ntfy"]["static"] == ["min_priority"]
    assert ov["triggers"]["wikiops"]["important"] is True
    cfg = cli._load_config()
    assert cfg.effective_gate("ntfy")["min_priority"] == "low"  # pin beats max


def test_app_shell_carries_the_shared_notification_overlay():
    shell = (REPO_ROOT / "webapp" / "_shared" /
             "app-shell-snippet.html").read_text(encoding="utf-8")
    # settings-pane row (top-right header pane) + the shared overlay
    assert 'id="so-notif-open"' in shell
    assert 'id="so-notif-modal"' in shell
    # the whole settings range: channels + gates + static + override + trigger
    for marker in ("data-nen=", "data-nprio=", "data-nurg=", "data-nstatic=",
                   "so-notif-ov-apply", "so-notif-tr-apply"):
        assert marker in shell, f"overlay missing {marker}"
    # exec rail uses the three registered controls
    for cid in ("notify-channel", "notify-override", "notify-trigger"):
        assert cid in shell, f"overlay does not exec {cid}"


def test_exec_registry_resolves_the_overlay_calls():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_action_exec", REPO_ROOT / "scripts" / "operator" / "_action_exec.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    reg = m.load_registry()
    cases = [
        ("notify-channel",
         {"channel": "twilio", "verb": "min_urgency_static", "value": "high"},
         "sovereign-osctl notifykit set twilio min_urgency_static high"),
        ("notify-override", {"verb": "clear", "value": "all"},
         "sovereign-osctl notifykit global-override clear all"),
        ("notify-trigger",
         {"name": "wikiops", "prop": "important", "value": "true"},
         "sovereign-osctl notifykit trigger wikiops important true"),
    ]
    for cid, args, expect in cases:
        argv, err = m.resolve_argv(reg[cid], args)
        assert argv, f"{cid}: {err}"
        assert " ".join(argv) == expect


# ── 2026-07-19 methodology-respect pass ("do we have the right setup for
#    the AI supertool to respect the methodology ?" → "lets address those") ──


def _write_engine(tmp_path: Path) -> None:
    eng = tmp_path / "hub" / "wiki" / "config"
    eng.mkdir(parents=True, exist_ok=True)
    (eng / "methodology.yaml").write_text(
        "stages:\n"
        "  document:\n"
        "    allowed_outputs: [wiki-page]\n"
        "    forbidden_outputs: [code-file]\n"
        "  scaffold:\n"
        "    allowed_outputs: [type-definition, config-file]\n"
        "    forbidden_outputs: [implementation, wiki-page]\n"
    )


def test_stage_allowed_proceeds_to_dry_run(tmp_path):
    reg = _write_registry(tmp_path)
    _write_engine(tmp_path)
    r = _wikiops("run", "--op", "scaffold", "--stage", "document",
                 "concept", "A Page", registry=reg)
    assert r.returncode == 0, r.stderr
    assert "DRY-RUN" in r.stdout
    assert "allowed in stage document" in r.stdout


def test_stage_forbidden_refuses_with_remediation(tmp_path):
    reg = _write_registry(tmp_path)
    _write_engine(tmp_path)
    r = _wikiops("run", "--op", "scaffold", "--stage", "scaffold",
                 "concept", "A Page", registry=reg)
    assert r.returncode == 2
    assert "FORBIDDEN" in r.stderr and "REMEDIATION" in r.stderr


def test_no_stage_prints_unchecked_advisory(tmp_path):
    reg = _write_registry(tmp_path)
    r = _wikiops("run", "--op", "scaffold", "concept", "A Page", registry=reg)
    assert r.returncode == 0
    assert "stage UNCHECKED" in r.stdout


def test_stage_neutral_op_passes_any_stage(tmp_path):
    reg = _write_registry(tmp_path)
    _write_engine(tmp_path)
    r = _wikiops("run", "--op", "post", "--stage", "scaffold", registry=reg)
    assert r.returncode == 0
    assert "stage-neutral" in r.stdout


def test_missing_engine_warns_but_proceeds(tmp_path):
    reg = _write_registry(tmp_path)  # no engine written
    r = _wikiops("run", "--op", "scaffold", "--stage", "document",
                 "concept", "X", registry=reg)
    assert r.returncode == 0
    assert "engine not found" in r.stdout


def _write_gated_registry(tmp_path: Path, policy: str) -> Path:
    reg = tmp_path / "wikis.toml"
    reg.write_text(
        'default = "hub"\n'
        '[wikis.hub]\nkind = "info-hub"\n'
        f'root = "{tmp_path}/hub"\npython = ".venv/bin/python"\n'
        f'gate_policy = "{policy}"\n'
    )
    return reg


def test_pending_gate_blocks_apply_under_block_policy(tmp_path, monkeypatch):
    reg = _write_gated_registry(tmp_path, "block")
    approvals = tmp_path / "approvals.json"
    approvals.write_text(json.dumps({"gates": {"SG2": "pending",
                                               "SG1": "signed"}}))
    env = dict(**__import__("os").environ,
               SOVEREIGN_OS_APPROVALS=str(approvals))
    r = subprocess.run(
        [sys.executable, str(WIKIOPS), "--registry", str(reg),
         "run", "--op", "archive", "X", "--apply"],
        capture_output=True, text=True, env=env)
    assert r.returncode == 2
    assert "SG2 PENDING" in r.stderr and "E0634" in r.stderr


def test_pending_gate_warns_under_default_policy(tmp_path):
    reg = _write_registry(tmp_path)  # default gate_policy=warn; root absent
    approvals = tmp_path / "approvals.json"
    approvals.write_text(json.dumps({"gates": {"SG3": "pending"}}))
    env = dict(**__import__("os").environ,
               SOVEREIGN_OS_APPROVALS=str(approvals))
    r = subprocess.run(
        [sys.executable, str(WIKIOPS), "--registry", str(reg),
         "run", "--op", "archive", "X", "--apply"],
        capture_output=True, text=True, env=env)
    # warns (stdout) then proceeds to the root check (absent → rc=2 there)
    assert "SG3 PENDING" in r.stdout
    assert "not present" in r.stderr


def test_gate_decision_emits_stage_gate_trigger(tmp_path):
    """approval-decide approve → notifykit event with source=stage-gate,
    important:true trigger lifting priority to high — through the file
    channel (credential-free)."""
    sink = tmp_path / "sink.jsonl"
    nkcfg = tmp_path / "notifykit.toml"
    nkcfg.write_text(
        "[channels.file]\nkind = \"file\"\nenabled = true\n"
        f"path = \"{sink}\"\n"
        "[triggers.stage-gate]\nimportant = true\n")
    approvals = tmp_path / "approvals.json"
    env = dict(**__import__("os").environ,
               SOVEREIGN_OS_APPROVALS=str(approvals),
               SOVEREIGN_OS_APPROVAL_LEDGER=str(tmp_path / "ledger.jsonl"),
               SOVEREIGN_OS_SPAN_STORE=str(tmp_path / "spans.jsonl"),
               SOVEREIGN_OS_NOTIFYKIT_CONFIG=str(nkcfg))
    env.pop("SOVEREIGN_OS_DRY_RUN", None)
    decide = REPO_ROOT / "scripts" / "lifecycle" / "approval-decide.py"
    r1 = subprocess.run([sys.executable, str(decide), "request",
                         "--title", "gate test"],
                        capture_output=True, text=True, env=env)
    assert r1.returncode == 0, r1.stderr
    rid = json.loads(r1.stdout)["id"]
    r2 = subprocess.run([sys.executable, str(decide), "approve", rid,
                         "--confirm"],
                        capture_output=True, text=True, env=env)
    assert r2.returncode == 0, r2.stderr
    rows = [json.loads(line) for line in sink.read_text().splitlines()]
    assert rows, "no notifykit event reached the file channel"
    assert rows[-1]["source"] == "stage-gate"
    assert rows[-1]["priority"] == "high"   # important:true trigger applied


def test_brain_files_route_the_methodology_surfaces():
    for name in ("CLAUDE.md", "AGENTS.md"):
        body = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert "standing-directives" in body, f"{name}: no directives route"
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for marker in ("E0634", "permission-modes", "wikiops", "notifykit",
                   "operator-env-files", "approvals gates"):
        assert marker in agents, f"AGENTS.md missing {marker}"
    claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in claude
