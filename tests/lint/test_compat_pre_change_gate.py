"""2026-07-19 — compat integration pass: the pre-change gate + scope v2.

Follow-on to the compat module (operator directive, verbatim: "suggest
or even force something else off in order to enable one thing"). Gates:

  1. `compat.pre_change()` overlays a proposed change on best-effort
     current state and returns findings; force findings set `gating`;
  2. the exec rail (`_action_exec.execute()`) REFUSES a force finding
     with reason + remediation (409), honors the audited
     `compat_override`, attaches warn findings without blocking, and
     degrades OPEN when the gate is off or unavailable;
  3. `compat.option_preview()` produces the per-option payload the
     cockpit uses to grey incompatible options (GET /api/control/compat
     on the control-exec-api);
  4. scope v2 — the provisioning universe: profiles/mixins join the bit
     universe, one image-build profile at a time (implicit pick-one),
     and each profile's own declared mixins become implicit `requires`.

Every subprocess run pins SOVEREIGN_OS_COMPAT_STATE=off +
SOVEREIGN_OS_COMPAT_CURRENT so results never depend on the host's real
/etc/sovereign-os state (hermetic on CI and on the operator's box).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT_TOOL = REPO_ROOT / "scripts" / "operator" / "compat.py"
ACTION_EXEC = REPO_ROOT / "scripts" / "operator" / "_action_exec.py"
EXEC_API = REPO_ROOT / "scripts" / "operator" / "control-exec-api.py"
APP_SHELL = REPO_ROOT / "webapp" / "_shared" / "app-shell-snippet.html"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _hermetic_env(current: str = "") -> dict[str, str]:
    env = dict(os.environ)
    env["SOVEREIGN_OS_COMPAT_STATE"] = "off"
    env["SOVEREIGN_OS_COMPAT_CURRENT"] = current
    env.pop("SOVEREIGN_OS_COMPAT_GATE", None)
    env.pop("SOVEREIGN_OS_ACTION_EXEC_LIVE", None)
    return env


def _exec_cli(*args: str, env: dict[str, str]) -> dict:
    r = subprocess.run(
        [sys.executable, str(ACTION_EXEC), *args],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── 1. pre_change() ─────────────────────────────────────────────────────────

def test_pre_change_force_gates(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "openclaw-backend=anthropic")
    compat = _load("compat_gate_t1", COMPAT_TOOL)
    res = compat.pre_change({"cost-policy": "halt-cloud"})
    assert res["available"] and res["gating"]
    force = [f for f in res["findings"] if f["severity"] == "force"]
    assert force and force[0]["rule_id"].startswith("C001")
    assert force[0]["reason"] and force[0]["remediation"]
    # the current state made it into the evaluation
    assert res["current"] == {"openclaw-backend": "anthropic"}


def test_pre_change_clean_and_warn(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "")
    compat = _load("compat_gate_t2", COMPAT_TOOL)
    clean = compat.pre_change({"cpu-mode": "balanced"})
    assert clean["available"] and not clean["gating"] and not clean["findings"]
    warn = compat.pre_change({"dspark-speculative-decoding": "on"})
    assert warn["available"] and not warn["gating"]
    assert any(f["rule_id"].startswith("C002") for f in warn["findings"])


def test_pre_change_degrades_open_on_missing_registry(monkeypatch):
    compat = _load("compat_gate_t3", COMPAT_TOOL)
    monkeypatch.setattr(compat, "COMPAT_PATH",
                        REPO_ROOT / "config" / "no-such-compat.yaml")
    res = compat.pre_change({"cpu-mode": "balanced"})
    assert res["available"] is False and "error" in res


# ── 2. the exec-rail gate ───────────────────────────────────────────────────

def test_execute_refuses_force_with_reason_and_remediation():
    env = _hermetic_env("openclaw-backend=anthropic")
    d = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud", env=env)
    assert d["code"] == 409 and d["ok"] is False
    assert d["compat"]["gating"] and d["error"].startswith("compat gate: C001")
    assert d["remediation"] and "compat_override" in d["override"]


def test_execute_compat_override_is_honored():
    env = _hermetic_env("openclaw-backend=anthropic")
    env["SOVEREIGN_OS_MOK_KEY"] = "test-presence"
    d = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud",
                  "--arg", "compat_override=true", "--confirm", env=env)
    assert d["code"] == 200 and d["dry_run"] is True
    # the findings still ride the result for the audit trail
    assert d["compat"]["gating"] and d["compat"]["findings"]


def test_execute_warn_findings_ride_without_blocking():
    env = _hermetic_env("")
    env["SOVEREIGN_OS_MOK_KEY"] = "test-presence"
    d = _exec_cli("--control", "dspark-speculative-decoding",
                  "--arg", "verb=enable", "--confirm", env=env)
    assert d["code"] == 200 and d["dry_run"] is True
    findings = d["compat"]["findings"]
    assert findings and not d["compat"]["gating"]
    assert any(f["rule_id"].startswith("C002") for f in findings)


def test_execute_gate_off_switch():
    env = _hermetic_env("openclaw-backend=anthropic")
    env["SOVEREIGN_OS_COMPAT_GATE"] = "off"
    env["SOVEREIGN_OS_MOK_KEY"] = "test-presence"
    d = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud",
                  "--confirm", env=env)
    assert d["code"] == 200 and "compat" not in d


# ── 3. the cockpit preview payload ──────────────────────────────────────────

def test_option_preview_shape(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "openclaw-backend=anthropic")
    compat = _load("compat_gate_t4", COMPAT_TOOL)
    p = compat.option_preview("cost-policy")
    assert p["available"] and p["control_id"] == "cost-policy"
    rows = {r["option"]: r for r in p["options"]}
    assert rows["halt-cloud"]["gating"] is True
    assert rows["resume-cloud"]["gating"] is False
    assert compat.option_preview("no-such-control") is None


def test_exec_api_and_app_shell_carry_the_preview_surface():
    api = EXEC_API.read_text(encoding="utf-8")
    assert "/api/control/compat" in api and "option_preview" in api
    shell = APP_SHELL.read_text(encoding="utf-8")
    assert "soCompatMark" in shell and "/api/control/compat" in shell


# ── 4. scope v2 — the provisioning universe ─────────────────────────────────

def test_provisioning_profile_implies_its_declared_mixins(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "")
    compat = _load("compat_gate_t5", COMPAT_TOOL)
    prov = compat.load_provisioning()
    assert "sain-01" in prov["profiles"] and prov["mixins"]
    res = compat.pre_change({"provisioning-profile": "sain-01"})
    assert res["available"] and not res["gating"]
    implicit = [f for f in res["findings"]
                if f["rule_id"] == "(implicit) profile-mixins:sain-01"]
    assert implicit and implicit[0]["severity"] == "warn"
    # naming the profile's own declared mixins satisfies the relation —
    # but pre_change takes one option per system, so drive the universe
    # directly for the multi-mixin word
    controls, rules = compat.load_controls(), compat.load_rules()
    universe = compat.Universe(controls, rules, prov)
    compiled = compat.compile_rules(universe, rules)
    word = universe.bit({"system": compat.PROV_PROFILE, "option": "sain-01"})
    for m in prov["profiles"]["sain-01"]:
        word |= universe.bit({"system": compat.PROV_MIXIN, "option": m})
    f = compat.evaluate(universe, compiled, word)
    assert not any("profile-mixins" in x["rule_id"] for x in f)


def test_provisioning_profiles_are_pick_one():
    compat = _load("compat_gate_t6", COMPAT_TOOL)
    prov = compat.load_provisioning()
    controls, rules = compat.load_controls(), compat.load_rules()
    universe = compat.Universe(controls, rules, prov)
    assert compat.PROV_PROFILE in universe.one_of_groups
    word = universe.bit({"system": compat.PROV_PROFILE, "option": "sain-01"})
    word |= universe.bit({"system": compat.PROV_PROFILE, "option": "minimal"})
    f = compat.evaluate(universe, compat.compile_rules(universe, rules), word)
    assert any(x["rule_id"] == f"(implicit) pick-one:{compat.PROV_PROFILE}"
               and x["severity"] == "force" for x in f)


# ── the two new rule families stay grounded ─────────────────────────────────

def test_c006_oracle_hybrid_vs_vram_tiers(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "inference-tier=oracle")
    compat = _load("compat_gate_t7", COMPAT_TOOL)
    res = compat.pre_change({"oracle-hybrid": "start"})
    hits = [f for f in res["findings"] if f["rule_id"].startswith("C006")]
    assert hits and hits[0]["severity"] == "warn" and not res["gating"]


def test_c007_one_draft_strategy(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "dspark-speculative-decoding=on")
    compat = _load("compat_gate_t8", COMPAT_TOOL)
    res = compat.pre_change({"dflash-speculative-decoding": "on"})
    hits = [f for f in res["findings"] if f["rule_id"].startswith("C007")]
    assert hits and hits[0]["severity"] == "warn"
    assert "dspark" in hits[0]["reason"].lower() or "DSpark" in hits[0]["reason"]
