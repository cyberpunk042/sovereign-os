"""2026-07-19 — cross-system compatibility registry lint.

Operator directive (verbatim): "I think we need a compatibility module
if not already present which talk about cross-modules or cross-features
compatibility and suggest or even force something else off in order to
enable one thing, or offer the possibility to chose one of many things.
like the u64 bit control strategy for example."

Gates:
  1. config/compatibility.yaml conforms to
     schemas/compatibility.schema.yaml (Draft 2020-12);
  2. every referenced system id exists in config/control-systems.yaml,
     and every referenced option is declared on that system;
  3. every rule carries a non-trivial reason + remediation (the hook
     doctrine: no black-box blocks);
  4. the bit compiler round-trips: every feature gets a unique bit,
     masks describe back to the same features;
  5. severity semantics hold end-to-end: force gates (rc=1), suggest
     never gates, warn gates only under --strict — exercised through
     the real CLI evaluate path.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT = REPO_ROOT / "config" / "compatibility.yaml"
SCHEMA = REPO_ROOT / "schemas" / "compatibility.schema.yaml"
CONTROLS = REPO_ROOT / "config" / "control-systems.yaml"
TOOL = REPO_ROOT / "scripts" / "operator" / "compat.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("compat_tool", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["compat_tool"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_files_exist():
    for p in (COMPAT, SCHEMA, CONTROLS, TOOL):
        assert p.is_file(), f"missing {p}"


def test_schema_conformance():
    import jsonschema

    doc = yaml.safe_load(COMPAT.read_text(encoding="utf-8"))
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def test_registry_references_resolve():
    mod = _load_tool()
    errors = mod.validate_references(mod.load_rules(), mod.load_controls())
    assert not errors, f"dangling registry references: {errors}"


def test_rules_carry_reason_and_remediation():
    doc = yaml.safe_load(COMPAT.read_text(encoding="utf-8"))
    for rule in doc["compatibility"]["rules"]:
        assert len(rule["reason"].strip()) >= 20, rule["id"]
        assert len(rule["remediation"].strip()) >= 10, rule["id"]


def test_rule_ids_unique():
    doc = yaml.safe_load(COMPAT.read_text(encoding="utf-8"))
    ids = [r["id"] for r in doc["compatibility"]["rules"]]
    assert len(ids) == len(set(ids)), f"duplicate rule ids: {ids}"


def test_bit_universe_roundtrip():
    mod = _load_tool()
    controls, rules = mod.load_controls(), mod.load_rules()
    universe = mod.Universe(controls, rules)
    # unique bit per feature
    assert len(universe.index) == len(universe.features)
    # every mode/profile system got a pick-one group covering all options
    for sys_id, system in controls.items():
        if system.get("kind") in ("mode", "profile") and system.get("options"):
            assert sys_id in universe.one_of_groups, sys_id
            described = universe.describe(universe.one_of_groups[sys_id])
            assert len(described) == len(system["options"]), sys_id
    # compiled masks describe back to the referenced features
    for c in mod.compile_rules(universe, rules):
        assert universe.describe(c["cond"]), c["rule"]["id"]
        assert universe.describe(c["tgt"]), c["rule"]["id"]


def test_severity_semantics_end_to_end():
    mod = _load_tool()
    controls, rules = mod.load_controls(), mod.load_rules()
    universe = mod.Universe(controls, rules)
    compiled = mod.compile_rules(universe, rules)

    def findings(assignment):
        return mod.evaluate(
            universe, compiled, mod.config_word(universe, assignment)
        )

    # force: halt-cloud + anthropic backend violates C001
    f = findings({"cost-policy": "halt-cloud", "openclaw-backend": "anthropic"})
    assert any(x["rule_id"].startswith("C001") and x["severity"] == "force" for x in f)

    # requires satisfied: no C002 finding
    f = findings({"dspark-speculative-decoding": "on", "inference-tier": "oracle"})
    assert not any(x["rule_id"].startswith("C002") for x in f)

    # requires unsatisfied: C002 warn finding
    f = findings({"dspark-speculative-decoding": "on"})
    assert any(x["rule_id"].startswith("C002") and x["severity"] == "warn" for x in f)

    # implicit pick-one: two avx-modes at once is a force finding
    word = mod.config_word(universe, {"avx-mode": "custom"})
    word |= 1 << universe.index[("avx-mode", "hybrid")]
    f = mod.evaluate(universe, compiled, word)
    assert any(x["verb"] == "one_of" and "avx-mode" in x["rule_id"] for x in f)


def test_cli_rc_semantics():
    import subprocess

    def run(*args):
        return subprocess.run(
            [sys.executable, str(TOOL), *args], capture_output=True, text=True
        )

    assert run("list").returncode == 0
    assert run("compile", "--json").returncode == 0
    ok = run("check", "--set", "cpu-mode=balanced")
    assert ok.returncode == 0, ok.stderr
    force = run("check", "--set", "cost-policy=halt-cloud",
                "--set", "openclaw-backend=anthropic")
    assert force.returncode == 1
    warn = run("check", "--set", "dspark-speculative-decoding=on")
    assert warn.returncode == 0
    strict = run("check", "--set", "dspark-speculative-decoding=on", "--strict")
    assert strict.returncode == 1
    unknown = run("check", "--set", "no-such-system=x")
    assert unknown.returncode == 2
