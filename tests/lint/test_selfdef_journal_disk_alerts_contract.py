"""Selfdef systemd-journal disk-usage alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-journal-disk.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefJournalDiskTextfileEmitFailed",
    "SelfdefJournalDiskObserverSilent",
    "SelfdefJournalDiskRunaway",
    "SelfdefJournalNoPersistentStorage",
    "SelfdefJournalDiskHigh",
}


def _all_rules():
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r for g in doc["groups"] for r in g["rules"]]


def test_rules_file_present_and_valid_yaml():
    assert RULES_PATH.is_file()


def test_all_required_alerts_present():
    names = {r["alert"] for r in _all_rules()}
    assert not REQUIRED_ALERTS - names


def test_every_alert_carries_full_envelope():
    for r in _all_rules():
        for f in ("alert", "expr", "for", "labels", "annotations"):
            assert f in r
        assert r["labels"]["subsystem"] == "selfdef-journal-disk"
        assert r["labels"]["severity"] in ("warning", "critical")


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefJournalDiskObserverSilent"]["expr"]


def test_runaway_threshold_5_gib_in_bytes():
    """5 GiB exact in bytes (5 * 1024^3 = 5368709120)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefJournalDiskRunaway"]["expr"]
    assert "selfdef_journal_bytes_total" in expr
    assert "5368709120" in expr


def test_high_threshold_1_gib_in_bytes():
    """1 GiB exact in bytes (1 * 1024^3 = 1073741824)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefJournalDiskHigh"]["expr"]
    assert "selfdef_journal_bytes_total" in expr
    assert "1073741824" in expr


def test_no_persistent_alert_guards_on_journal_available():
    """Must require journal_available == 1 — otherwise rpm hosts
    without journalctl would fire (false positive)."""
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefJournalNoPersistentStorage"]["expr"]
    assert "selfdef_journal_available == 1" in expr
    assert "selfdef_journal_persistent == 0" in expr


def test_severity_classification():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefJournalDiskTextfileEmitFailed": "critical",
        "SelfdefJournalDiskObserverSilent":     "critical",
        "SelfdefJournalDiskRunaway":            "critical",
        "SelfdefJournalNoPersistentStorage":    "critical",
        "SelfdefJournalDiskHigh":               "warning",
    }
    for name, sev in expected.items():
        assert by_name[name]["labels"]["severity"] == sev


def test_journal_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefJournalDiskTextfileEmitFailed": "observer-fault",
        "SelfdefJournalDiskObserverSilent":     "observer-silent",
        "SelfdefJournalDiskRunaway":            "log-spam-runaway",
        "SelfdefJournalNoPersistentStorage":    "no-persistent",
        "SelfdefJournalDiskHigh":               "disk-high",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("journal_link") == link


def test_no_persistent_description_cites_forensic_gap():
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefJournalNoPersistentStorage"]["annotations"]["description"]
    assert "forensic" in desc.lower()


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-journal-disk")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "ec6a822" in RULES_PATH.read_text()


def test_every_alert_carries_runbook_url():
    for r in _all_rules():
        url = r["annotations"].get("runbook_url", "")
        assert "m060-deployment-guide.md#" in url
