#!/usr/bin/env python3
"""scripts/operator/compat.py — cross-system compatibility resolver.

Operator directive 2026-07-19 (verbatim): "I think we need a
compatibility module if not already present which talk about
cross-modules or cross-features compatibility and suggest or even
force something else off in order to enable one thing, or offer the
possibility to chose one of many things. like the u64 bit control
strategy for example."

Operator-confirmed design (2026-07-19 evaluation):
  - config/compatibility.yaml is the authoring source of truth
    (schema: schemas/compatibility.schema.yaml);
  - this tool COMPILES the feature universe to bit indexes + u64 mask
    words (the M002 bit-machine "policy becomes bits" strategy applied
    to configuration) and validates candidate configurations with
    bitwise ops: `requires` is a subset test, `conflicts_with` /
    `forces_off` an AND, `one_of` a popcount;
  - per-rule severity: suggest (never gates) | warn (gates only under
    --strict) | force (gates `check`, rc=1).

Every kind=mode / kind=profile system in config/control-systems.yaml is
an IMPLICIT pick-one group — the compiler emits an exclusivity mask per
such system, so "offer the possibility to chose one of many things" is
structural, not per-rule boilerplate.

Scope v2 (2026-07-19 follow-on): the PROVISIONING universe. The
image-build provisioning modules (profiles/*.yaml + profiles/mixins/)
join the bit universe as two virtual systems:
  provisioning-profile   pick-one over the declared profile ids
                         (sain-01, developer, minimal, ...) — implicit
                         exclusivity mask like any kind=profile system
  provisioning-mixin     the mixin set (role-*, whitelabel-default,
                         observability-tier-1, ...) — multi-select
plus IMPLICIT per-profile `requires` relations derived from each
profile's own declared `mixins:` list — grounded in the profile files
themselves, not hand-authored rules. Rules in compatibility.yaml may
reference the two virtual systems like any registry system.

Pre-change gate (consumed by scripts/operator/_action_exec.py + the
control-exec-api compat preview): `pre_change(proposed)` overlays a
proposed control change onto the best-effort CURRENT state (single-value
state_path files + $SOVEREIGN_OS_COMPAT_CURRENT overrides) and returns
findings; force findings gate the exec rail (with reason + remediation +
an audited override), warn/suggest ride along.

Verbs:
  list                       rules table (--json for fleet tooling)
  compile [--json]           bit universe + rule masks (hex words)
  check --set sys=opt ...    validate a candidate configuration
        [--on sys] [--current] [--strict] [--json]
  explain <rule-id>          one rule in full
  why <system>[=option]      every rule touching a feature

Exit codes:
  0  ok (or only suggest/warn findings without --strict)
  1  force violation (or warn under --strict)
  2  usage / registry-reference error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR PyYAML missing — install with `pip install PyYAML`", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT_PATH = REPO_ROOT / "config" / "compatibility.yaml"
CONTROLS_PATH = REPO_ROOT / "config" / "control-systems.yaml"
PROFILES_DIR = REPO_ROOT / "profiles"

WORD_BITS = 64

# Scope v2 — the two virtual provisioning systems (never in
# control-systems.yaml; derived from profiles/ at compile time).
PROV_PROFILE = "provisioning-profile"
PROV_MIXIN = "provisioning-mixin"


def _norm_opt(value: Any) -> str:
    """Options in control-systems.yaml may be str/bool/number — normalise
    to the string form used on the CLI (`--set dashboard-toggle=true`)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load_controls() -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(CONTROLS_PATH.read_text(encoding="utf-8"))
    return {s["id"]: s for s in doc.get("systems", [])}


def load_rules() -> list[dict[str, Any]]:
    doc = yaml.safe_load(COMPAT_PATH.read_text(encoding="utf-8"))
    return doc["compatibility"]["rules"]


def load_provisioning() -> dict[str, Any]:
    """Scope v2 — scan the image-build provisioning modules.

    Returns {"profiles": {id: [mixin, ...]}, "mixins": [name, ...]}.
    Grounded in profiles/*.yaml (identity.id + the profile's own
    `mixins:` list) and profiles/mixins/*.yaml (the mixin inventory).
    Degrades to empty on a missing tree — the v1 control-systems scope
    keeps working standalone.
    """
    profiles: dict[str, list[str]] = {}
    mixins: list[str] = []
    try:
        for f in sorted(PROFILES_DIR.glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            pid = (doc.get("identity") or {}).get("id")
            if pid:
                profiles[str(pid)] = [str(m) for m in (doc.get("mixins") or [])]
        mixins = sorted(
            p.stem for p in (PROFILES_DIR / "mixins").glob("*.yaml")
        )
    except OSError:
        return {"profiles": {}, "mixins": []}
    return {"profiles": profiles, "mixins": mixins}


def _rule_feature_refs(rule: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [rule["when"]]
    if rule.get("target"):
        refs.append(rule["target"])
    refs.extend(rule.get("targets") or [])
    return refs


def validate_references(
    rules: list[dict[str, Any]],
    controls: dict[str, dict[str, Any]],
    provisioning: dict[str, Any] | None = None,
) -> list[str]:
    """Every referenced system id must exist in the registry (or be a
    scope-v2 virtual provisioning system); every referenced option must
    be one of that system's declared options."""
    prov = provisioning if provisioning is not None else load_provisioning()
    virtual = {
        PROV_PROFILE: sorted(prov.get("profiles", {})),
        PROV_MIXIN: list(prov.get("mixins", [])),
    }
    errors: list[str] = []
    for rule in rules:
        for ref in _rule_feature_refs(rule):
            sys_id = ref.get("system")
            if sys_id in virtual:
                declared = virtual[sys_id]
                if "option" in ref and _norm_opt(ref["option"]) not in declared:
                    errors.append(
                        f"{rule['id']}: provisioning system {sys_id!r} has no "
                        f"module {ref['option']!r} (declared: {declared})"
                    )
                continue
            if sys_id not in controls:
                errors.append(f"{rule['id']}: unknown system {sys_id!r}")
                continue
            if "option" in ref:
                declared = [
                    _norm_opt(o) for o in (controls[sys_id].get("options") or [])
                ]
                if declared and _norm_opt(ref["option"]) not in declared:
                    errors.append(
                        f"{rule['id']}: system {sys_id!r} has no option "
                        f"{ref['option']!r} (declared: {declared})"
                    )
        # resolution steps execute real controls and declare feature effects —
        # both must resolve against the registry (typo-proof the fix plans).
        for st in rule.get("resolution") or []:
            if st.get("system") not in controls:
                errors.append(
                    f"{rule['id']}: resolution step targets unknown control "
                    f"{st.get('system')!r}")
            eff = st.get("effect") or {}
            for _kind, ref in eff.items():
                es = ref.get("system")
                if es in virtual:
                    continue
                if es not in controls:
                    errors.append(
                        f"{rule['id']}: resolution effect on unknown system {es!r}")
                    continue
                if "option" in ref:
                    declared = [_norm_opt(o)
                                for o in (controls[es].get("options") or [])]
                    if declared and _norm_opt(ref["option"]) not in declared:
                        errors.append(
                            f"{rule['id']}: resolution effect {es!r} has no "
                            f"option {ref['option']!r}")
    return errors


class Universe:
    """The compiled bit universe: every feature -> a stable bit index.

    Features are (system, None) — "system active" — plus (system, option)
    for every option of every pick-one (mode/profile) system and every
    option referenced by a rule. Deterministic: sorted, so the same
    inputs always compile to the same bit layout.
    """

    def __init__(
        self,
        controls: dict[str, dict[str, Any]],
        rules: list[dict[str, Any]],
        provisioning: dict[str, Any] | None = None,
    ):
        prov = provisioning or {"profiles": {}, "mixins": []}
        feats: set[tuple[str, str | None]] = set()
        for sys_id, system in controls.items():
            feats.add((sys_id, None))
            if system.get("kind") in ("mode", "profile"):
                for o in system.get("options") or []:
                    feats.add((sys_id, _norm_opt(o)))
        # Scope v2 — the provisioning universe (profiles pick-one + mixins).
        for pid in prov.get("profiles", {}):
            feats.add((PROV_PROFILE, pid))
        for m in prov.get("mixins", []):
            feats.add((PROV_MIXIN, m))
        if prov.get("profiles"):
            feats.add((PROV_PROFILE, None))
        if prov.get("mixins"):
            feats.add((PROV_MIXIN, None))
        for rule in rules:
            for ref in _rule_feature_refs(rule):
                feats.add((ref["system"], _norm_opt(ref["option"])
                           if "option" in ref else None))
        self.features: list[tuple[str, str | None]] = sorted(
            feats, key=lambda f: (f[0], f[1] is not None, f[1] or "")
        )
        self.index: dict[tuple[str, str | None], int] = {
            f: i for i, f in enumerate(self.features)
        }
        self.n_words = (len(self.features) + WORD_BITS - 1) // WORD_BITS
        # Implicit pick-one exclusivity masks (kind=mode/profile systems).
        self.one_of_groups: dict[str, int] = {}
        for sys_id, system in controls.items():
            if system.get("kind") in ("mode", "profile"):
                mask = 0
                for o in system.get("options") or []:
                    mask |= 1 << self.index[(sys_id, _norm_opt(o))]
                if mask:
                    self.one_of_groups[sys_id] = mask
        # Scope v2 — exactly one image-build profile is realized at a time.
        if prov.get("profiles"):
            mask = 0
            for pid in prov["profiles"]:
                mask |= 1 << self.index[(PROV_PROFILE, pid)]
            self.one_of_groups[PROV_PROFILE] = mask
        # Scope v2 — implicit per-profile requires, grounded in each
        # profile's own declared mixins list (not hand-authored rules).
        self.implicit_requires: list[dict[str, Any]] = []
        for pid, mixin_list in sorted(prov.get("profiles", {}).items()):
            wanted = [m for m in mixin_list if (PROV_MIXIN, m) in self.index]
            if not wanted:
                continue
            tgt = 0
            for m in wanted:
                tgt |= 1 << self.index[(PROV_MIXIN, m)]
            self.implicit_requires.append({
                "name": f"profile-mixins:{pid}",
                "cond": 1 << self.index[(PROV_PROFILE, pid)],
                "tgt": tgt,
                "mixins": wanted,
            })

    def bit(self, ref: dict[str, Any]) -> int:
        key = (ref["system"], _norm_opt(ref["option"]) if "option" in ref else None)
        return 1 << self.index[key]

    def mask_of(self, refs: list[dict[str, Any]]) -> int:
        mask = 0
        for r in refs:
            mask |= self.bit(r)
        return mask

    def words(self, mask: int) -> list[str]:
        return [
            f"0x{(mask >> (w * WORD_BITS)) & ((1 << WORD_BITS) - 1):016x}"
            for w in range(self.n_words)
        ]

    def describe(self, mask: int) -> list[str]:
        out = []
        for f, i in self.index.items():
            if mask & (1 << i):
                out.append(f"{f[0]}={f[1]}" if f[1] is not None else f[0])
        return sorted(out)


def compile_rules(
    universe: Universe, rules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    compiled = []
    for rule in rules:
        cond = universe.bit(rule["when"])
        if rule["verb"] == "one_of":
            tgt = universe.mask_of(rule.get("targets") or [])
        elif rule.get("targets"):
            tgt = universe.mask_of(rule["targets"])
        else:
            tgt = universe.bit(rule["target"])
        compiled.append({"rule": rule, "cond": cond, "tgt": tgt})
    return compiled


def config_word(universe: Universe, assignment: dict[str, str | None]) -> int:
    """A candidate configuration as a word: for `sys=opt` both the
    (sys,opt) bit and the (sys,None) "active" bit are set; for a bare
    `sys` only the active bit."""
    word = 0
    for sys_id, opt in assignment.items():
        key_active = (sys_id, None)
        if key_active not in universe.index:
            raise KeyError(f"unknown system {sys_id!r}")
        word |= 1 << universe.index[key_active]
        if opt is not None:
            key = (sys_id, opt)
            if key not in universe.index:
                raise KeyError(f"unknown option {sys_id}={opt}")
            word |= 1 << universe.index[key]
    return word


def evaluate(
    universe: Universe,
    compiled: list[dict[str, Any]],
    word: int,
) -> list[dict[str, Any]]:
    """The bitwise pass. requires: cond⊆W ∧ tgt⊄W. conflicts/forces_off:
    cond⊆W ∧ W∧tgt≠0. one_of: popcount(W ∧ tgt) > 1. Plus the implicit
    pick-one groups per mode/profile system."""
    findings: list[dict[str, Any]] = []
    for sys_id, group in universe.one_of_groups.items():
        if bin(word & group).count("1") > 1:
            findings.append(
                {
                    "rule_id": f"(implicit) pick-one:{sys_id}",
                    "verb": "one_of",
                    "severity": "force",
                    "reason": f"system {sys_id!r} is kind=mode/profile — "
                    "at most one option may be active",
                    "remediation": "keep a single option for this system",
                    "hits": universe.describe(word & group),
                }
            )
    # Scope v2 — implicit profile→mixin requires (derived from profiles/*.yaml).
    for ir in getattr(universe, "implicit_requires", []):
        if word & ir["cond"] == ir["cond"] and word & ir["tgt"] != ir["tgt"]:
            findings.append(
                {
                    "rule_id": f"(implicit) {ir['name']}",
                    "verb": "requires",
                    "severity": "warn",
                    "reason": "the image-build profile declares these mixins "
                    "in profiles/*.yaml — realizing it without them is not "
                    "the profile the file describes",
                    "remediation": "include the profile's declared mixins: "
                    + ", ".join(ir["mixins"]),
                    "hits": universe.describe(ir["tgt"] & ~word),
                }
            )
    for c in compiled:
        rule, cond, tgt = c["rule"], c["cond"], c["tgt"]
        if word & cond != cond:
            continue  # condition not active
        verb = rule["verb"]
        violated = False
        hits: list[str] = []
        if verb == "requires":
            if word & tgt != tgt:
                violated = True
                hits = universe.describe(tgt & ~word)
        elif verb in ("conflicts_with", "forces_off"):
            if word & tgt:
                violated = True
                hits = universe.describe(word & tgt)
        elif verb == "one_of":
            if bin(word & tgt).count("1") > 1:
                violated = True
                hits = universe.describe(word & tgt)
        if violated:
            findings.append(
                {
                    "rule_id": rule["id"],
                    "verb": verb,
                    "severity": rule["severity"],
                    "reason": rule["reason"].strip(),
                    "remediation": rule["remediation"].strip(),
                    "hits": hits,
                }
            )
    return findings


# ---------------- pre-change gate API (exec-rail + web preview) ----------------


def read_current_state(
    controls: dict[str, dict[str, Any]]
) -> dict[str, str]:
    """Best-effort CURRENT assignment {system: option}.

    Two sources, never raising:
      1. $SOVEREIGN_OS_COMPAT_CURRENT — "sys=opt,sys2=opt2" explicit
         overrides (tests + operator escape hatch); wins over files.
      2. Each system's `state_path` when it is an existing regular file
         whose stripped single-line content equals one of the system's
         declared options (e.g. /etc/sovereign-os/active-profile).
         Anything else (unit names, TOML stores, missing files) is
         simply UNKNOWN — the gate only reasons over what it can read.
    """
    current: dict[str, str] = {}
    # Hermetic switch (tests + operator escape hatch): COMPAT_STATE=off
    # skips the state_path file scan; explicit $SOVEREIGN_OS_COMPAT_CURRENT
    # overrides still apply.
    scan_files = os.environ.get(
        "SOVEREIGN_OS_COMPAT_STATE", "on").lower() not in ("off", "0")
    for sys_id, system in (controls.items() if scan_files else ()):
        sp = system.get("state_path")
        if not isinstance(sp, str) or not sp.startswith("/"):
            continue
        try:
            p = Path(sp)
            if not p.is_file() or p.stat().st_size > 4096:
                continue
            value = p.read_text(encoding="utf-8").strip().splitlines()
            value = value[0].strip() if value else ""
        except (OSError, UnicodeDecodeError):
            continue
        declared = [_norm_opt(o) for o in (system.get("options") or [])]
        if value and value in declared:
            current[sys_id] = value
    env = os.environ.get("SOVEREIGN_OS_COMPAT_CURRENT", "")
    for item in env.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            current[k.strip()] = v.strip()
    return current


def pre_change(proposed: dict[str, str | None]) -> dict[str, Any]:
    """The pre-change compatibility gate: overlay a PROPOSED assignment
    onto the best-effort current state and evaluate every rule.

    Returns {"available": True, "findings": [...], "gating": bool,
    "current": {...}, "proposed": {...}} — `gating` is True iff a
    force-severity finding fired. Never raises: an unreadable registry
    or config degrades to {"available": False, "error": ...} so the
    exec rail stays functional (gate degrades OPEN, with the reason on
    the result for the operator to see).
    """
    try:
        controls = load_controls()
        rules = load_rules()
        provisioning = load_provisioning()
        errors = validate_references(rules, controls, provisioning)
        if errors:
            return {"available": False,
                    "error": f"compat registry references unresolved: {errors}"}
        universe = Universe(controls, rules, provisioning)
        compiled = compile_rules(universe, rules)
        current = read_current_state(controls)
        merged: dict[str, str | None] = dict(current)
        # The proposed change REPLACES the changed system's current option
        # (a switch is a switch, not an addition).
        for k, v in proposed.items():
            merged[k] = v
        # The universe carries every pick-one option + every rule-referenced
        # option. An option NO rule references has no bit — represent it as
        # the system's active bit only (identical evaluation semantics), and
        # skip systems the universe doesn't know at all (best-effort input).
        def _word(assignment: dict[str, str | None]) -> int:
            safe: dict[str, str | None] = {}
            for k, v in assignment.items():
                if (k, None) not in universe.index:
                    continue
                safe[k] = v if (v is None or (k, v) in universe.index) else None
            return config_word(universe, safe)

        all_findings = evaluate(universe, compiled, _word(merged))
        # A finding the CURRENT state trips on its own is PRE-EXISTING —
        # it must not gate an UNRELATED change (else one bad state bricks
        # every rail action, including fixes). Only findings the proposed
        # change INTRODUCES gate; pre-existing ones ride along labeled.
        baseline_ids = {f["rule_id"] for f in
                        evaluate(universe, compiled, _word(dict(current)))}
        findings = [f for f in all_findings if f["rule_id"] not in baseline_ids]
        preexisting = [f for f in all_findings if f["rule_id"] in baseline_ids]
        return {
            "available": True,
            "findings": findings,
            "preexisting": preexisting,
            "gating": any(f["severity"] == "force" for f in findings),
            "current": current,
            "proposed": {k: v for k, v in proposed.items()},
        }
    except (OSError, KeyError, ValueError, yaml.YAMLError) as e:
        return {"available": False, "error": f"compat gate unavailable: {e}"}


def _parse_hit(hit: str) -> tuple[str, str | None]:
    if "=" in hit:
        s, o = hit.split("=", 1)
        return s, o
    return hit, None


def _steps_for_finding(rule: dict[str, Any],
                       finding: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter a rule's resolution steps to the ones addressing THIS
    finding's actual hits — C001 has four backend-switch steps but only
    the backends that are actively offending get planned."""
    steps = rule.get("resolution") or []
    hits = [_parse_hit(h) for h in (finding.get("hits") or [])]
    verb = rule["verb"]
    out: list[dict[str, Any]] = []
    for st in steps:
        eff = st.get("effect") or {}
        if not eff:
            continue
        kind, ref = next(iter(eff.items()))
        es = ref.get("system")
        eo = _norm_opt(ref["option"]) if "option" in ref else None
        relevant = False
        for hs, ho in hits:
            if hs != es:
                continue
            if verb == "requires":
                # hit = MISSING feature; the step must provide it
                if kind in ("set", "add") and (ho is None or eo == ho):
                    relevant = True
            else:  # conflicts_with / forces_off / one_of — hit = offending ACTIVE
                if kind == "unset" and eo == ho:
                    relevant = True
                elif kind == "set" and eo != ho:
                    relevant = True  # pick-one replace clears the offender
        if relevant:
            out.append(st)
    return out


def _apply_step_word(universe: Universe, word: int, step: dict[str, Any]) -> int:
    """Simulate one resolution step on the state word (set = pick-one
    replace · add = activate without clearing siblings · unset = clear)."""
    kind, ref = next(iter(step["effect"].items()))
    s = ref.get("system")
    o = _norm_opt(ref["option"]) if "option" in ref else None
    if kind in ("set", "add"):
        if kind == "set" and s in universe.one_of_groups:
            word &= ~universe.one_of_groups[s]
        if o is not None and (s, o) in universe.index:
            word |= 1 << universe.index[(s, o)]
        if (s, None) in universe.index:
            word |= 1 << universe.index[(s, None)]
    else:  # unset
        if o is not None and (s, o) in universe.index:
            word &= ~(1 << universe.index[(s, o)])
    return word


def resolve(proposed: dict[str, str | None] | None = None) -> dict[str, Any]:
    """The RESOLUTION engine — the operator's "force something else off
    in order to enable one thing" made executable.

    proposed=None  → plan to clear what the CURRENT state trips.
    proposed={...} → plan to clear what the proposed change INTRODUCES
                     (the exec rail attaches this to a 409).

    The plan is the per-finding-filtered union of the firing rules'
    resolution steps (each step maps 1:1 onto an exec-rail control
    call), then SIMULATED on the u64 state word — `clean_after` is True
    only when applying the whole plan actually clears every gating
    finding, so the cockpit never offers a fix that would not fix.
    Never raises."""
    try:
        controls = load_controls()
        rules = load_rules()
        provisioning = load_provisioning()
        errors = validate_references(rules, controls, provisioning)
        if errors:
            return {"available": False,
                    "error": f"compat registry references unresolved: {errors}"}
        universe = Universe(controls, rules, provisioning)
        compiled = compile_rules(universe, rules)
        current = read_current_state(controls)

        def _word_of(assignment: dict[str, str | None]) -> int:
            safe: dict[str, str | None] = {}
            for k, v in assignment.items():
                if (k, None) not in universe.index:
                    continue
                safe[k] = v if (v is None or (k, v) in universe.index) else None
            return config_word(universe, safe)

        cur_word = _word_of(dict(current))
        if proposed is None:
            base_ids: set[str] = set()
            work_word = cur_word
        else:
            merged: dict[str, str | None] = dict(current)
            merged.update(proposed)
            work_word = _word_of(merged)
            base_ids = {f["rule_id"]
                        for f in evaluate(universe, compiled, cur_word)}
        findings = [f for f in evaluate(universe, compiled, work_word)
                    if f["rule_id"] not in base_ids]
        rules_by_id = {r["id"]: r for r in rules}
        plan: list[dict[str, Any]] = []
        seen: set[tuple] = set()
        for f in findings:
            rule = rules_by_id.get(f["rule_id"])
            if rule is None:
                continue  # implicit findings carry no authored resolution
            for st in _steps_for_finding(rule, f):
                key = (st["system"],
                       tuple(sorted((st.get("args") or {}).items())))
                if key in seen:
                    continue
                seen.add(key)
                plan.append({"system": st["system"],
                             "args": st.get("args") or {},
                             "label": st["label"],
                             "effect": st["effect"],
                             "rule_id": f["rule_id"]})
        sim = work_word
        for st in plan:
            sim = _apply_step_word(universe, sim, st)
        findings_after = [f for f in evaluate(universe, compiled, sim)
                          if f["rule_id"] not in base_ids]
        return {
            "available": True,
            "findings": findings,
            "plan": plan,
            "findings_after": findings_after,
            "clean_after": not any(f["severity"] == "force"
                                   for f in findings_after),
            "resolved_all": not findings_after,
            "current": current,
            "proposed": dict(proposed) if proposed else {},
        }
    except (OSError, KeyError, ValueError, yaml.YAMLError) as e:
        return {"available": False, "error": f"compat resolve unavailable: {e}"}


def state_report() -> dict[str, Any]:
    """The compatibility-pane payload (header ⚙ → ⚖ Compatibility overlay):
    every rule (id/verb/severity/reason/remediation/when/targets), the
    best-effort CURRENT state, the findings that state trips RIGHT NOW
    (`check --current` equivalent), and the checkable control inventory
    (id + options) for the per-control preview drill-in. Never raises —
    degrades to {"available": False, "error": ...}."""
    try:
        controls = load_controls()
        rules = load_rules()
        provisioning = load_provisioning()
        errors = validate_references(rules, controls, provisioning)
        if errors:
            return {"available": False,
                    "error": f"compat registry references unresolved: {errors}"}
        universe = Universe(controls, rules, provisioning)
        compiled = compile_rules(universe, rules)
        current = read_current_state(controls)
        findings: list[dict[str, Any]] = []
        if current:
            safe = {
                k: (v if (k, v) in universe.index else None)
                for k, v in current.items() if (k, None) in universe.index
            }
            findings = evaluate(universe, compiled, config_word(universe, safe))
        resolution = None
        if findings:
            r = resolve(None)
            if r.get("available"):
                resolution = {"plan": r["plan"],
                              "clean_after": r["clean_after"],
                              "resolved_all": r["resolved_all"]}
        return {
            "available": True,
            "current": current,
            "findings": findings,
            "resolution": resolution,
            "rules": [
                {
                    "id": r["id"], "verb": r["verb"], "severity": r["severity"],
                    "when": r["when"],
                    "targets": r.get("targets") or ([r["target"]] if r.get("target") else []),
                    "reason": r["reason"].strip(),
                    "remediation": r["remediation"].strip(),
                }
                for r in rules
            ],
            "implicit": {
                "pick_one_groups": sorted(universe.one_of_groups),
                "profile_requires": [ir["name"] for ir in universe.implicit_requires],
            },
            "checkable": [
                {"id": cid, "options": [_norm_opt(o) for o in (c.get("options") or [])]}
                for cid, c in sorted(controls.items())
            ],
        }
    except (OSError, KeyError, ValueError, yaml.YAMLError) as e:
        return {"available": False, "error": f"compat state unavailable: {e}"}


def option_preview(control_id: str) -> dict[str, Any] | None:
    """Per-option compat preview for ONE control against current state —
    the payload the cockpit uses to GREY incompatible options on the
    control rail. Returns None for an unknown control; never raises."""
    try:
        controls = load_controls()
    except (OSError, yaml.YAMLError):
        return None
    control = controls.get(control_id)
    if control is None:
        return None
    options = [_norm_opt(o) for o in (control.get("options") or [])]
    rows = []
    for opt in options:
        res = pre_change({control_id: opt})
        if not res.get("available"):
            return {"control_id": control_id, "available": False,
                    "error": res.get("error"), "options": []}
        rows.append({
            "option": opt,
            "gating": res["gating"],
            "findings": res["findings"],
        })
    current = read_current_state(controls)
    return {"control_id": control_id, "available": True,
            "current": current, "options": rows}


# ---------------- CLI verbs ----------------


def _load_all() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Universe]:
    controls = load_controls()
    rules = load_rules()
    provisioning = load_provisioning()
    errors = validate_references(rules, controls, provisioning)
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        sys.exit(2)
    return controls, rules, Universe(controls, rules, provisioning)


def cmd_list(args: argparse.Namespace) -> int:
    _, rules, _ = _load_all()
    if args.json:
        print(json.dumps({"rules": rules}, indent=2, default=str))
        return 0
    print("── sovereign-os cross-system compatibility rules ──")
    for r in rules:
        tgt = r.get("target") or r.get("targets")
        print(f"  {r['id']}")
        print(f"    {r['verb']}  when={r['when']}  target={tgt}")
        print(f"    severity={r['severity']}")
    print(f"\n  {len(rules)} rules — `compat explain <id>` for reason + remediation")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    _, rules, universe = _load_all()
    compiled = compile_rules(universe, rules)
    payload = {
        "n_features": len(universe.features),
        "n_words": universe.n_words,
        "features": [
            {"bit": i, "system": f[0], "option": f[1]}
            for f, i in sorted(universe.index.items(), key=lambda kv: kv[1])
        ],
        "one_of_groups": {
            s: universe.words(m) for s, m in sorted(universe.one_of_groups.items())
        },
        "implicit_profile_requires": [
            {"name": ir["name"], "mixins": ir["mixins"]}
            for ir in universe.implicit_requires
        ],
        "rules": [
            {
                "id": c["rule"]["id"],
                "verb": c["rule"]["verb"],
                "severity": c["rule"]["severity"],
                "cond_words": universe.words(c["cond"]),
                "target_words": universe.words(c["tgt"]),
            }
            for c in compiled
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print("── compat compile — the M002 bit-word view ──")
    print(f"  features: {payload['n_features']}  →  {payload['n_words']} × u64 word(s)")
    print(f"  implicit pick-one groups: {len(universe.one_of_groups)}")
    print(f"  implicit profile→mixin requires (scope v2): "
          f"{len(universe.implicit_requires)}")
    for r in payload["rules"]:
        print(f"  {r['id']:44s} {r['verb']:14s} sev={r['severity']}")
        print(f"    cond   {' '.join(r['cond_words'])}")
        print(f"    target {' '.join(r['target_words'])}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    _, rules, universe = _load_all()
    compiled = compile_rules(universe, rules)
    assignment: dict[str, str | None] = {}
    for item in args.set or []:
        if "=" not in item:
            print(f"ERROR --set expects system=option, got {item!r}", file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        assignment[k] = v
    for item in args.on or []:
        assignment.setdefault(item, None)
    if getattr(args, "current", False):
        controls = load_controls()
        for sys_id, opt in read_current_state(controls).items():
            assignment.setdefault(sys_id, opt)
    if not assignment:
        print("ERROR nothing to check — pass --set system=option / --on system",
              file=sys.stderr)
        return 2
    try:
        word = config_word(universe, assignment)
    except KeyError as e:
        print(f"ERROR {e.args[0]}", file=sys.stderr)
        return 2
    findings = evaluate(universe, compiled, word)
    gating = [
        f for f in findings
        if f["severity"] == "force" or (args.strict and f["severity"] == "warn")
    ]
    if args.json:
        print(json.dumps({
            "assignment": assignment,
            "word": universe.words(word),
            "findings": findings,
            "rc": 1 if gating else 0,
        }, indent=2))
        return 1 if gating else 0
    print("── compat check ──")
    print(f"  config: {', '.join(sorted(k + ('=' + v if v else '') for k, v in assignment.items()))}")
    print(f"  word:   {' '.join(universe.words(word))}")

    def _print_resolution() -> None:
        res = resolve({k: v for k, v in assignment.items()})
        if not res.get("available"):
            return
        if res["plan"]:
            print("  ── resolution plan (\"force something else off in order "
                  "to enable one thing\") — vs the LIVE state ──")
            for st in res["plan"]:
                argv = " ".join(f"{k}={v}" for k, v in st["args"].items())
                print(f"    → {st['label']}")
                print(f"        exec-rail: control={st['system']} args {{{argv}}}"
                      f"   [{st['rule_id']}]")
            verdict = ("VERIFIED — applying the plan clears every gating finding"
                       if res["clean_after"] else
                       "PARTIAL — force findings would remain after the plan")
            if res["resolved_all"]:
                verdict = "VERIFIED — applying the plan clears ALL findings"
            print(f"    {verdict}")
        elif res["findings"]:
            print("  (no executable resolution steps for what this change "
                  "introduces on the live state)")

    if not findings:
        print("  CLEAN — no compatibility findings")
        if getattr(args, "resolve", False):
            _print_resolution()
        return 0
    for f in findings:
        mark = {"force": "FORCE", "warn": "WARN ", "suggest": "HINT "}[f["severity"]]
        print(f"  [{mark}] {f['rule_id']} ({f['verb']})")
        print(f"      reason:      {f['reason']}")
        print(f"      remediation: {f['remediation']}")
        if f["hits"]:
            print(f"      involves:    {', '.join(f['hits'])}")
    if getattr(args, "resolve", False):
        _print_resolution()
    return 1 if gating else 0


def cmd_explain(args: argparse.Namespace) -> int:
    _, rules, _ = _load_all()
    for r in rules:
        if r["id"] == args.rule_id:
            print(yaml.safe_dump(r, sort_keys=False))
            return 0
    print(f"ERROR unknown rule id {args.rule_id!r}", file=sys.stderr)
    return 2


def cmd_why(args: argparse.Namespace) -> int:
    _, rules, _ = _load_all()
    sys_id, _, opt = args.feature.partition("=")
    matched = []
    for r in rules:
        for ref in _rule_feature_refs(r):
            if ref["system"] != sys_id:
                continue
            if opt and "option" in ref and _norm_opt(ref["option"]) != opt:
                continue
            matched.append(r)
            break
    if not matched:
        print(f"  no rules touch {args.feature}")
        return 0
    print(f"── rules touching {args.feature} ──")
    for r in matched:
        print(f"  {r['id']}  ({r['verb']}, severity={r['severity']})")
        print(f"    {r['reason'].strip()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="compat.py",
        description="Cross-system compatibility resolver (YAML → u64 masks).",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list", help="rules table")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pc = sub.add_parser("compile", help="bit universe + rule masks")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_compile)

    ck = sub.add_parser("check", help="validate a candidate configuration")
    ck.add_argument("--set", action="append", metavar="SYS=OPT",
                    help="feature assignment (repeatable)")
    ck.add_argument("--on", action="append", metavar="SYS",
                    help="mark a system active without picking an option")
    ck.add_argument("--current", action="store_true",
                    help="merge the best-effort live state (state_path files "
                         "+ $SOVEREIGN_OS_COMPAT_CURRENT) under the --set/--on "
                         "assignment")
    ck.add_argument("--strict", action="store_true",
                    help="warn-severity findings also gate (rc=1)")
    ck.add_argument("--resolve", action="store_true",
                    help="print the verified resolution plan (the steps that "
                         "force the offending things off / bring the missing "
                         "ones up)")
    ck.add_argument("--json", action="store_true")
    ck.set_defaults(func=cmd_check)

    pe = sub.add_parser("explain", help="one rule in full")
    pe.add_argument("rule_id")
    pe.set_defaults(func=cmd_explain)

    pw = sub.add_parser("why", help="rules touching a system[=option]")
    pw.add_argument("feature")
    pw.set_defaults(func=cmd_why)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
