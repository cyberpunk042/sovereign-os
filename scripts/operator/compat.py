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

Verbs:
  list                       rules table (--json for fleet tooling)
  compile [--json]           bit universe + rule masks (hex words)
  check --set sys=opt ...    validate a candidate configuration
        [--on sys] [--strict] [--json]
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

WORD_BITS = 64


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


def _rule_feature_refs(rule: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [rule["when"]]
    if rule.get("target"):
        refs.append(rule["target"])
    refs.extend(rule.get("targets") or [])
    return refs


def validate_references(
    rules: list[dict[str, Any]], controls: dict[str, dict[str, Any]]
) -> list[str]:
    """Every referenced system id must exist in the registry; every
    referenced option must be one of that system's declared options."""
    errors: list[str] = []
    for rule in rules:
        for ref in _rule_feature_refs(rule):
            sys_id = ref.get("system")
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
    return errors


class Universe:
    """The compiled bit universe: every feature -> a stable bit index.

    Features are (system, None) — "system active" — plus (system, option)
    for every option of every pick-one (mode/profile) system and every
    option referenced by a rule. Deterministic: sorted, so the same
    inputs always compile to the same bit layout.
    """

    def __init__(self, controls: dict[str, dict[str, Any]], rules: list[dict[str, Any]]):
        feats: set[tuple[str, str | None]] = set()
        for sys_id, system in controls.items():
            feats.add((sys_id, None))
            if system.get("kind") in ("mode", "profile"):
                for o in system.get("options") or []:
                    feats.add((sys_id, _norm_opt(o)))
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


# ---------------- CLI verbs ----------------


def _load_all() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], Universe]:
    controls = load_controls()
    rules = load_rules()
    errors = validate_references(rules, controls)
    if errors:
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        sys.exit(2)
    return controls, rules, Universe(controls, rules)


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
    if not findings:
        print("  CLEAN — no compatibility findings")
        return 0
    for f in findings:
        mark = {"force": "FORCE", "warn": "WARN ", "suggest": "HINT "}[f["severity"]]
        print(f"  [{mark}] {f['rule_id']} ({f['verb']})")
        print(f"      reason:      {f['reason']}")
        print(f"      remediation: {f['remediation']}")
        if f["hits"]:
            print(f"      involves:    {', '.join(f['hits'])}")
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
    ck.add_argument("--strict", action="store_true",
                    help="warn-severity findings also gate (rc=1)")
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
