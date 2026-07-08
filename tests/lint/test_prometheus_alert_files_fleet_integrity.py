"""Prometheus alert file fleet integrity — every config/prometheus/
alerts/selfdef-*.rules.yml file must have valid Prometheus rule-file
structure regardless of whether it has a per-file contract test.

sovereign-os ships 33 alert rule files. ~18 of them have per-file
contract tests (`test_selfdef_<name>_alerts_contract.py`) covering
semantic invariants (specific alert names + thresholds + dashboard
deep-link labels). The remaining 15+ have NO contract test at all —
a silent regression of their structural shape (groups: list /
alert: name / expr: presence) wouldn't be caught at commit time.

This fleet-level gate runs symmetric STRUCTURAL invariants every
Prometheus rule file MUST satisfy per the Prometheus rule file
schema:

  1. parses as YAML
  2. top-level `groups` is a non-empty list
  3. each group has `name` (non-empty string) + `rules` (non-empty list)
  4. each rule in a group has either `alert:` (alert rule) or
     `record:` (recording rule)
  5. every alert rule has `expr:` (the PromQL trigger)
  6. every alert rule has `labels` (severity / dashboard label) +
     `annotations` (summary / description) maps

A silent regression of any here would either (a) reject the rule
file at Prometheus load time OR (b) leave the alert nameless /
expr-less / unrouted at fire time.

Coverage gap closed: every alert file in the fleet now structurally
gated, complementing the heavier per-file contract gates.

Pure text + YAML-shape assertions (no Prometheus instance needed).
"""
from __future__ import annotations

import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_DIR = REPO_ROOT / "config" / "prometheus" / "alerts"


def _alert_files() -> list[Path]:
    if not ALERTS_DIR.is_dir():
        return []
    return sorted(ALERTS_DIR.glob("*.rules.yml"))


def test_alerts_dir_present():
    """The alerts directory exists where Prometheus expects."""
    assert ALERTS_DIR.is_dir(), f"alerts directory not found at {ALERTS_DIR}"


def test_at_least_one_alert_file():
    """Sanity: the fleet is non-empty."""
    files = _alert_files()
    assert files, f"no alert *.rules.yml files found under {ALERTS_DIR}"


def test_every_alert_file_parses():
    """Every alert file must parse as YAML."""
    parse_failures: list[tuple[str, str]] = []
    for f in _alert_files():
        try:
            yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            parse_failures.append((f.relative_to(REPO_ROOT).as_posix(), str(e)))
    assert not parse_failures, f"YAML parse failures: {parse_failures}"


def test_every_alert_file_has_groups_top_level():
    """Every Prometheus rule file MUST have a top-level `groups:` list
    (per the Prometheus rule file schema). A file with rules but no
    `groups:` wrapper is rejected at Prometheus load time."""
    missing: list[str] = []
    for f in _alert_files():
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "groups" not in doc:
            missing.append(f.relative_to(REPO_ROOT).as_posix())
            continue
        groups = doc["groups"]
        if not isinstance(groups, list) or len(groups) == 0:
            missing.append(f.relative_to(REPO_ROOT).as_posix())
    assert not missing, (
        f"alert files without a non-empty top-level `groups:` list "
        f"(Prometheus would reject at load): {missing}"
    )


def test_every_group_has_name_and_rules():
    """Each group in `groups:` MUST have `name:` (non-empty string)
    + `rules:` (non-empty list). Otherwise the group is unrouteable
    + carries no alerts."""
    violations: list[tuple[str, int, str]] = []
    for f in _alert_files():
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        groups = (doc or {}).get("groups", [])
        for i, group in enumerate(groups):
            if not isinstance(group, dict):
                violations.append((f.relative_to(REPO_ROOT).as_posix(), i, "not a mapping"))
                continue
            name = group.get("name")
            if not isinstance(name, str) or not name.strip():
                violations.append((f.relative_to(REPO_ROOT).as_posix(), i, "missing/empty name"))
            rules = group.get("rules")
            if not isinstance(rules, list) or len(rules) == 0:
                violations.append((f.relative_to(REPO_ROOT).as_posix(), i, "missing/empty rules list"))
    assert not violations, (
        f"groups missing required fields (Prometheus would reject): {violations}"
    )


def test_every_rule_is_alert_or_record():
    """Each rule MUST be either an alert rule (has `alert:` key) or
    a recording rule (has `record:` key). A rule with neither is
    nonsense the Prometheus schema rejects."""
    violations: list[str] = []
    for f in _alert_files():
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for group in (doc or {}).get("groups", []):
            group_name = group.get("name", "<no-name>")
            for j, rule in enumerate(group.get("rules", [])):
                if not isinstance(rule, dict):
                    violations.append(
                        f"{f.relative_to(REPO_ROOT)}/groups/{group_name}/rules[{j}]: not a mapping"
                    )
                    continue
                if "alert" not in rule and "record" not in rule:
                    violations.append(
                        f"{f.relative_to(REPO_ROOT)}/groups/{group_name}/rules[{j}]: "
                        f"neither `alert:` nor `record:` present"
                    )
    assert not violations, (
        f"rules without `alert:`/`record:` discriminator (Prometheus "
        f"rejects): {violations}"
    )


def test_every_alert_rule_has_expr():
    """Every alert rule MUST have an `expr:` field (the PromQL trigger).
    An alert without expr never fires."""
    violations: list[str] = []
    for f in _alert_files():
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for group in (doc or {}).get("groups", []):
            group_name = group.get("name", "<no-name>")
            for rule in group.get("rules", []):
                if not isinstance(rule, dict) or "alert" not in rule:
                    continue
                alert_name = rule.get("alert", "<no-name>")
                if not rule.get("expr"):
                    violations.append(
                        f"{f.relative_to(REPO_ROOT)}/groups/{group_name}/alert[{alert_name}]: "
                        f"missing `expr:` (alert can never fire)"
                    )
    assert not violations, f"alerts missing expr: {violations}"


def test_every_alert_rule_has_labels_and_annotations():
    """Every alert rule MUST have `labels` + `annotations` maps. Labels
    carry severity (Alertmanager routing) + dashboard deep-link tags;
    annotations carry summary/description (operator-readable). An
    alert without either fires unrouted + with no operator-visible
    text."""
    violations: list[str] = []
    for f in _alert_files():
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        for group in (doc or {}).get("groups", []):
            group_name = group.get("name", "<no-name>")
            for rule in group.get("rules", []):
                if not isinstance(rule, dict) or "alert" not in rule:
                    continue
                alert_name = rule.get("alert", "<no-name>")
                prefix = f"{f.relative_to(REPO_ROOT)}/groups/{group_name}/alert[{alert_name}]"
                if not isinstance(rule.get("labels"), dict) or not rule["labels"]:
                    violations.append(f"{prefix}: missing/empty `labels:` map")
                if not isinstance(rule.get("annotations"), dict) or not rule["annotations"]:
                    violations.append(f"{prefix}: missing/empty `annotations:` map")
    assert not violations, f"alerts missing labels/annotations: {violations}"
