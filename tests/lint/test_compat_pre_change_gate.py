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


# ── the ⚖ Compatibility PANE (shared component, 2026-07-20) ─────────────────
# Operator verbatim: "if something is off you will have a badge in the
# header that allow you to redisplay the pane if you dismissed it. and it
# will take long time you need to identify what is Not-compatible with
# other things. like the u64 custom bits control"


def test_state_report_is_the_pane_payload(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "dspark-speculative-decoding=on")
    compat = _load("compat_pane_t1", COMPAT_TOOL)
    p = compat.state_report()
    assert p["available"]
    assert {"current", "findings", "rules", "implicit", "checkable"} <= set(p)
    # the live-state verdict trips C002 for the simulated current state
    assert any(f["rule_id"].startswith("C002") for f in p["findings"])
    # every rule row carries the pane's display fields
    for r in p["rules"]:
        assert {"id", "verb", "severity", "when", "targets",
                "reason", "remediation"} <= set(r)
    # the u64 custom-bits control is identifiable: avx-mode is a pick-one
    # group (mutually-exclusive options — the exclusivity mask)
    assert "avx-mode" in p["implicit"]["pick_one_groups"]
    assert any(c["id"] == "avx-mode" and "custom" in c["options"]
               for c in p["checkable"])


def test_state_report_clean_when_no_current_state(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "")
    compat = _load("compat_pane_t2", COMPAT_TOOL)
    p = compat.state_report()
    assert p["available"] and p["current"] == {} and p["findings"] == []


def test_exec_api_serves_the_bare_pane_payload():
    api = EXEC_API.read_text(encoding="utf-8")
    assert "state_report" in api
    # bare /api/control/compat (no control_id) serves the pane payload —
    # the 400 usage error is gone
    assert "pass ?control_id" not in api


def test_shared_component_carries_the_compat_pane_and_badge():
    shell = APP_SHELL.read_text(encoding="utf-8")
    # the pane (settings-pane row + overlay modal + fetch logic)
    for marker in ("so-compat-open", "so-compat-modal", "so-compat-close",
                   "soCompatPane", "so-compat-state", "so-compat-rules",
                   "so-compat-ctl", "so-compat-preview"):
        assert marker in shell, f"compat pane missing {marker}"
    # the header badge — visible only when something is off; click re-opens
    assert "so-compat-badge" in shell and "soCompatBadge" in shell
    assert "compatBadge.addEventListener('click'" in shell
    # the not-compatible-with drill-in (the `why` view, client-side)
    assert "soCompatRelations" in shell
    # pane opens from the settings row AND refreshes on open
    assert "compatSet(true); soCompatPane();" in shell
    # bare sanctioned fetch present
    assert "fetch('/api/control/compat'," in shell


def test_preexisting_violations_do_not_gate_unrelated_changes(monkeypatch):
    """Regression (found via the pane walkthrough): a force violation ALREADY
    in the current state must not 409 every unrelated rail action — only
    findings the proposed change INTRODUCES gate; pre-existing ones ride
    along labeled, and remediation actions stay executable."""
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "cost-policy=halt-cloud,openclaw-backend=anthropic")
    compat = _load("compat_gate_t9", COMPAT_TOOL)
    # unrelated change: not gated; C001 surfaces as pre-existing
    res = compat.pre_change({"cpu-mode": "balanced"})
    assert res["available"] and not res["gating"] and not res["findings"]
    assert any(f["rule_id"].startswith("C001") for f in res["preexisting"])
    # the remediation itself (backend -> local) clears the violation
    fix = compat.pre_change({"openclaw-backend": "local"})
    assert not fix["gating"] and not fix["findings"] and not fix["preexisting"]
    # and a change that INTRODUCES the violation still gates
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "openclaw-backend=anthropic")
    compat2 = _load("compat_gate_t10", COMPAT_TOOL)
    intro = compat2.pre_change({"cost-policy": "halt-cloud"})
    assert intro["gating"] and any(
        f["rule_id"].startswith("C001") for f in intro["findings"])


# ── the AVX / runtime-mode rule families (C008–C011) ────────────────────────
# Operator 2026-07-20: "you need to identify what is Not-compatible with
# other things. like the u64 custom bits control" — avx-mode previously had
# NO cross-system rules; C008/C011 give it its grounded relations.


def test_avx_mode_has_cross_system_relations(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "avx-mode=off")
    compat = _load("compat_avx_t1", COMPAT_TOOL)
    touching = [r["id"] for r in compat.load_rules()
                if r["when"].get("system") == "avx-mode"
                or any(t.get("system") == "avx-mode"
                       for t in (r.get("targets") or [r.get("target")] if r.get("target") else []))]
    assert touching, "avx-mode must have cross-system rules (operator directive)"
    # pulse on a scalar-AVX box warns (C008)
    res = compat.pre_change({"inference-tier": "pulse"})
    assert any(f["rule_id"].startswith("C008") and f["severity"] == "warn"
               for f in res["findings"])


def test_high_concurrency_requires_all_three_tiers(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "inference-tier=oracle")
    compat = _load("compat_avx_t2", COMPAT_TOOL)
    res = compat.pre_change({"runtime-mode": "high-concurrency-burst"})
    hits = [f for f in res["findings"] if f["rule_id"].startswith("C009")]
    assert hits and hits[0]["severity"] == "warn"
    # the missing tiers are named in the hits
    joined = " ".join(hits[0]["hits"])
    assert "pulse" in joined and "logic" in joined and "oracle" not in joined


def test_ultra_sovereign_efficiency_advisories(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "gpu-mode=peak,avx-mode=off")
    compat = _load("compat_avx_t3", COMPAT_TOOL)
    res = compat.pre_change({"runtime-mode": "ultra-sovereign-efficiency"})
    ids = {f["rule_id"][:4] for f in res["findings"]}
    assert "C010" in ids and "C011" in ids
    assert not res["gating"]        # suggest never gates


# ── compat-gate refusals emit through notifykit (the compat-gate trigger) ──


def test_compat_reject_emits_notifykit_event(tmp_path):
    sink = tmp_path / "sink.jsonl"
    cfg = tmp_path / "notifykit.toml"
    cfg.write_text(
        f'[channels.file]\nkind = "file"\nenabled = true\npath = "{sink}"\n',
        encoding="utf-8")
    env = _hermetic_env("openclaw-backend=anthropic")
    env["SOVEREIGN_OS_NOTIFYKIT_CONFIG"] = str(cfg)
    env["SOVEREIGN_OS_NOTIFYKIT_OVERRIDES"] = str(tmp_path / "ov.json")
    d = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud", env=env)
    assert d["code"] == 409
    rows = [json.loads(x) for x in sink.read_text().splitlines()]
    assert rows and rows[-1]["source"] == "compat-gate"
    assert "C001" in rows[-1]["title"] and "INSTEAD" in rows[-1]["message"]
    # no config → no emission, gate result unchanged
    env2 = _hermetic_env("openclaw-backend=anthropic")
    env2["SOVEREIGN_OS_NOTIFYKIT_CONFIG"] = str(tmp_path / "absent.toml")
    d2 = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud", env=env2)
    assert d2["code"] == 409


# ── the RESOLUTION engine ("force something else off in order to enable
#    one thing", executable + simulated) ────────────────────────────────────


def test_resolve_plans_only_the_active_offenders(monkeypatch):
    """C001 carries four backend-switch steps; with only ONE backend
    actively offending, the plan contains exactly that one — and the
    simulation verifies applying it clears the finding."""
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "openclaw-backend=anthropic")
    compat = _load("compat_res_t1", COMPAT_TOOL)
    r = compat.resolve({"cost-policy": "halt-cloud"})
    assert r["available"]
    assert [s["system"] for s in r["plan"]] == ["openclaw-backend"]
    assert r["plan"][0]["args"] == {"verb": "local"}
    assert r["clean_after"] and r["resolved_all"]


def test_resolve_requires_plans_only_missing_tiers(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT", "inference-tier=oracle")
    compat = _load("compat_res_t2", COMPAT_TOOL)
    r = compat.resolve({"runtime-mode": "high-concurrency-burst"})
    tiers = sorted(s["args"]["tier"] for s in r["plan"])
    assert tiers == ["logic", "pulse"]     # oracle already up — not planned
    assert all(next(iter(s["effect"])) == "add" for s in r["plan"])
    assert r["clean_after"] and r["resolved_all"]


def test_resolve_current_state_plan(monkeypatch):
    """resolve(None) = fix what the box trips RIGHT NOW (the pane's
    Fix buttons + state_report.resolution)."""
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_STATE", "off")
    monkeypatch.setenv("SOVEREIGN_OS_COMPAT_CURRENT",
                       "cost-policy=halt-cloud,openclaw-backend=anthropic")
    compat = _load("compat_res_t3", COMPAT_TOOL)
    r = compat.resolve(None)
    assert any(f["rule_id"].startswith("C001") for f in r["findings"])
    assert [s["system"] for s in r["plan"]] == ["openclaw-backend"]
    assert r["clean_after"]
    rep = compat.state_report()
    assert rep["resolution"] and rep["resolution"]["plan"]


def test_exec_rail_409_carries_the_resolution_plan():
    env = _hermetic_env("openclaw-backend=anthropic")
    d = _exec_cli("--control", "cost-policy", "--arg", "verb=halt-cloud", env=env)
    assert d["code"] == 409
    plan = (d.get("resolution") or {}).get("plan") or []
    assert plan and plan[0]["system"] == "openclaw-backend"
    assert d["resolution"]["clean_after"] is True


def test_cli_check_resolve_prints_verified_plan():
    env = _hermetic_env("inference-tier=oracle")
    r = subprocess.run(
        [sys.executable, str(COMPAT_TOOL), "check",
         "--set", "runtime-mode=high-concurrency-burst", "--resolve"],
        capture_output=True, text=True, env=env)
    assert "resolution plan" in r.stdout and "VERIFIED" in r.stdout
    assert "tier=pulse" in r.stdout and "tier=logic" in r.stdout


def test_pane_renders_fix_buttons():
    shell = APP_SHELL.read_text(encoding="utf-8")
    assert "so-compat-fix" in shell
    assert "Force: " in shell            # the button prefix
    assert "soExec(stp.system, stp.args" in shell   # fixes go through the rail


# ── the CLI-side gate: sovereign-osctl mutating verbs honor the rules ──────
# (2026-07-20 — before this, `sovereign-osctl cost-policy halt-cloud` typed
# in a terminal bypassed compat entirely; only the exec rail was gated.)

OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _precheck(system: str, option: str | None, env: dict[str, str]):
    argv = [sys.executable, str(COMPAT_TOOL), "precheck", "--system", system]
    if option is not None:
        argv += ["--option", option]
    return subprocess.run(argv, capture_output=True, text=True, env=env)


def test_precheck_rc_semantics():
    env = _hermetic_env("")
    assert _precheck("cpu-mode", "balanced", env).returncode == 0   # clean
    warn = _precheck("dspark-speculative-decoding", "on", env)
    assert warn.returncode == 0 and "WARN" in warn.stdout           # advisory proceeds
    env_force = _hermetic_env("openclaw-backend=anthropic")
    force = _precheck("cost-policy", "halt-cloud", env_force)
    assert force.returncode == 1
    assert "REFUSED" in force.stdout and "resolution plan" in force.stdout
    env_ovr = dict(env_force); env_ovr["SOVEREIGN_OS_COMPAT_OVERRIDE"] = "1"
    ovr = _precheck("cost-policy", "halt-cloud", env_ovr)
    assert ovr.returncode == 0 and "OVERRIDDEN" in ovr.stdout
    env_off = dict(env_force); env_off["SOVEREIGN_OS_COMPAT_GATE"] = "off"
    off = _precheck("cost-policy", "halt-cloud", env_off)
    assert off.returncode == 0 and off.stdout.strip() == ""


def test_osctl_mutating_verb_is_gated():
    """`sovereign-osctl cost-policy halt-cloud` with an anthropic backend
    active refuses BEFORE the verb executes — rc=1, REFUSED + the plan."""
    env = _hermetic_env("openclaw-backend=anthropic")
    r = subprocess.run(["bash", str(OSCTL), "cost-policy", "halt-cloud"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "compat [BLOCK] C001" in r.stdout
    assert "compat: REFUSED" in r.stdout
    assert "resolution plan" in r.stdout


def test_osctl_warn_advises_and_proceeds():
    """A warn finding prints and the verb still runs (no REFUSED)."""
    env = _hermetic_env("avx-mode=off")
    r = subprocess.run(["bash", str(OSCTL), "inference", "start", "pulse"],
                       capture_output=True, text=True, env=env)
    assert "compat [WARN ] C008" in r.stdout
    assert "compat: REFUSED" not in r.stdout


def test_osctl_gate_off_is_silent():
    env = _hermetic_env("avx-mode=off")
    env["SOVEREIGN_OS_COMPAT_GATE"] = "off"
    r = subprocess.run(["bash", str(OSCTL), "inference", "start", "pulse"],
                       capture_output=True, text=True, env=env)
    assert "compat [" not in r.stdout


def test_osctl_route_covers_the_gated_verbs():
    src = OSCTL.read_text(encoding="utf-8")
    assert "_compat_precheck_route" in src and "_compat_guard" in src
    route = src.split("_compat_precheck_route() {", 1)[1].split("\n}", 1)[0]
    for verb in ("cpu-mode|gpu-mode|avx-mode|frontend", "dspark", "cost-policy",
                 "openclaw|open-computer|claude-code|vscode", "inference",
                 "trinity"):
        assert verb in route, f"gated verb family {verb!r} missing from the route"


# ── compat as a MONITORED condition: the R226 health probe ─────────────────


def test_health_scan_compat_probe_severity_mapping():
    scan = REPO_ROOT / "scripts" / "hardware" / "health-scan.py"
    def run(current):
        env = _hermetic_env(current)
        r = subprocess.run([sys.executable, str(scan), "--probe", "compat",
                            "--json"], capture_output=True, text=True, env=env)
        return r.returncode, json.loads(r.stdout)
    rc, clean = run("")
    assert rc == 0 and clean["severity"] == "ok"
    rc, force = run("cost-policy=halt-cloud,openclaw-backend=anthropic")
    assert rc == 1 and force["severity"] == "attention"
    assert any(i["id"].startswith("C001") for i in force["flagged_items"])
    assert "fix plan available" in force["detail"]
    rc, warn = run("dspark-speculative-decoding=on")
    assert rc == 1 and warn["severity"] == "attention"
    rc, sugg = run("cpu-mode=ultra-low-power,gpu-mode=peak")
    assert rc == 0 and sugg["severity"] == "informational"   # suggest-only


def test_incompatible_state_flows_to_notifykit(tmp_path):
    """The full monitored loop: health-scan (compat attention) → R228
    dispatch → notifykit channels — an incompatible box NOTIFIES."""
    sink = tmp_path / "sink.jsonl"
    cfg = tmp_path / "notifykit.toml"
    cfg.write_text(
        f'[channels.file]\nkind = "file"\nenabled = true\npath = "{sink}"\n',
        encoding="utf-8")
    env = _hermetic_env("cost-policy=halt-cloud,openclaw-backend=anthropic")
    env["SOVEREIGN_OS_NOTIFYKIT_CONFIG"] = str(cfg)
    env["SOVEREIGN_OS_NOTIFYKIT_OVERRIDES"] = str(tmp_path / "ov.json")
    env["SOVEREIGN_OS_NOTIFY_STATE"] = str(tmp_path / "state.json")
    env["SOVEREIGN_OS_NOTIFY_CONFIG"] = str(tmp_path / "absent-notify.toml")
    dispatch = REPO_ROOT / "scripts" / "notify" / "dispatch.py"
    r = subprocess.run([sys.executable, str(dispatch), "dispatch", "--json"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [json.loads(x) for x in sink.read_text().splitlines()]
    compat_rows = [x for x in rows if "compat" in x.get("title", "")]
    assert compat_rows, rows
    assert compat_rows[0]["source"] == "r228-health"
    assert compat_rows[0]["priority"] == "high"
