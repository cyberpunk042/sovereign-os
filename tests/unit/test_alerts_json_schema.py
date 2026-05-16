"""Layer 2 unit tests — sovereign-osctl alerts --json schema (SDD-023 Q23-A).

SDD-023 § Output formats specifies that the JSON-array output has a
stable schema, fields additive only. Q23-A asked whether the sort
order (ALERT-before-WARN, then alphabetic by metric) should be locked
as schema. Recommendation: YES.

These tests pin:
  1. The four required fields (level, metric, value, remediation)
     are present on every entry
  2. The `level` value is exactly one of "ALERT" | "WARN"
  3. `labels` field is an object (may be empty {})
  4. `value` is numeric
  5. Empty state is `[]` (NOT null, NOT error message — fleet
     aggregation tools depend on parseable output)
  6. Sort order: ALERT entries precede WARN entries; within a level,
     entries are sorted alphabetically by `metric` name

These are CONTRACT TESTS — changing them is intentional, audited,
and goes through SDD-023 revision."""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

REQUIRED_FIELDS = {"level", "metric", "value", "remediation"}
ALLOWED_LEVELS = {"ALERT", "WARN"}


def _run_alerts_json(metrics_dir: pathlib.Path) -> list[dict]:
    """Run sovereign-osctl alerts --json against a metrics dir; return parsed array."""
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
        "SOVEREIGN_OS_METRICS_DIR": str(metrics_dir),
    }
    result = subprocess.run(
        [str(OSCTL), "alerts", "--json"],
        capture_output=True,
        text=True,
        env=env,
    )
    # alerts --json exits 0 — empty array or alerts. Both are success here.
    assert result.returncode == 0, f"alerts --json failed: {result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture
def absent_metrics_dir(tmp_path):
    return tmp_path / "nonexistent"


@pytest.fixture
def clean_metrics_dir(tmp_path):
    d = tmp_path / "clean"
    d.mkdir()
    (d / "sovereign-os-clean.prom").write_text(
        "sovereign_os_build_step_render_total{profile=\"sain-01\",result=\"success\"} 1\n"
    )
    return d


@pytest.fixture
def dirty_metrics_dir(tmp_path):
    """Multiple alert-triggering metrics with different levels + names —
    used to verify sort order."""
    d = tmp_path / "dirty"
    d.mkdir()
    (d / "sovereign-os-mix.prom").write_text(
        # WARN: pending security updates
        'sovereign_os_security_updates_available 3\n'
        # ALERT: ZFS pool degraded
        'sovereign_os_zfs_pool_health{pool="tank"} 0\n'
        # ALERT: perimeter inactive
        'sovereign_os_perimeter_status 0\n'
        # ALERT: friction-audit failures
        'sovereign_os_friction_audit_failures{profile="sain-01"} 2\n'
    )
    return d


def test_empty_state_returns_array_not_null(absent_metrics_dir, clean_metrics_dir):
    """SDD-023: empty state MUST be `[]`, never null/error/object."""
    for d in (absent_metrics_dir, clean_metrics_dir):
        alerts = _run_alerts_json(d)
        assert isinstance(alerts, list), f"empty state not a list for {d}"
        assert alerts == [], f"clean dir should produce [], got: {alerts}"


def test_every_entry_has_required_fields(dirty_metrics_dir):
    alerts = _run_alerts_json(dirty_metrics_dir)
    assert len(alerts) > 0
    for entry in alerts:
        missing = REQUIRED_FIELDS - entry.keys()
        assert not missing, f"entry missing required fields {missing}: {entry}"


def test_level_field_is_exactly_alert_or_warn(dirty_metrics_dir):
    alerts = _run_alerts_json(dirty_metrics_dir)
    for entry in alerts:
        assert entry["level"] in ALLOWED_LEVELS, \
            f"unknown level {entry['level']!r}; must be one of {ALLOWED_LEVELS}"


def test_labels_field_is_object(dirty_metrics_dir):
    alerts = _run_alerts_json(dirty_metrics_dir)
    for entry in alerts:
        labels = entry.get("labels")
        if labels is not None:
            assert isinstance(labels, dict), \
                f"labels MUST be a dict (may be {{}}): got {type(labels).__name__}"


def test_value_field_is_numeric(dirty_metrics_dir):
    alerts = _run_alerts_json(dirty_metrics_dir)
    for entry in alerts:
        v = entry["value"]
        assert isinstance(v, (int, float)) and not isinstance(v, bool), \
            f"value MUST be numeric, got {type(v).__name__}: {v!r}"


def test_sort_order_alert_before_warn(dirty_metrics_dir):
    """Q23-A locked: ALERT entries precede WARN entries."""
    alerts = _run_alerts_json(dirty_metrics_dir)
    levels = [e["level"] for e in alerts]
    # Find boundary between ALERTs and WARNs
    saw_warn = False
    for level in levels:
        if level == "WARN":
            saw_warn = True
        elif level == "ALERT" and saw_warn:
            pytest.fail(
                f"sort order broken: ALERT entry after WARN entry. Sequence: {levels}"
            )


def test_sort_order_alphabetic_by_metric_within_level(dirty_metrics_dir):
    """Q23-A locked: within a level, entries sorted alphabetically by metric name."""
    alerts = _run_alerts_json(dirty_metrics_dir)
    for level in ALLOWED_LEVELS:
        in_level = [e["metric"] for e in alerts if e["level"] == level]
        assert in_level == sorted(in_level), \
            f"{level} entries not in alphabetic-by-metric order: {in_level}"


def test_remediation_is_non_empty_string(dirty_metrics_dir):
    """SDD-023: remediation is a 'concrete next command' — never empty,
    never null. If a future rule has no remediation, document that
    explicitly in the SDD and update this test."""
    alerts = _run_alerts_json(dirty_metrics_dir)
    for entry in alerts:
        r = entry["remediation"]
        assert isinstance(r, str) and len(r) > 0, \
            f"remediation MUST be a non-empty string: {entry}"


def test_no_meta_metrics_trigger_rules(tmp_path):
    """SDD-023: sovereign_os_meta_* metrics MUST NOT trigger rules
    (prevents self-reinforcing alert loops with alerts-check.sh)."""
    d = tmp_path / "meta"
    d.mkdir()
    # Put a meta_alert_count value that would trigger Rule 1 (*_total + result=fail)
    # IF the meta-exclusion wasn't honored. But meta_alert_count is a gauge
    # not _total — verify that no rule fires.
    (d / "sovereign-os-meta.prom").write_text(
        'sovereign_os_meta_alert_count{level="ALERT"} 5\n'
        'sovereign_os_meta_alert_count{level="WARN"} 2\n'
        'sovereign_os_meta_alerts_check_last_run_timestamp 1715817600\n'
    )
    alerts = _run_alerts_json(d)
    for entry in alerts:
        assert not entry["metric"].startswith("sovereign_os_meta_"), \
            f"meta metric triggered a rule (would cause self-reinforcing loop): {entry}"
