"""Selfdef listening-sockets alerts — contract test."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = (
    REPO_ROOT / "config" / "prometheus" / "alerts"
    / "selfdef-listening-sockets.rules.yml"
)

REQUIRED_ALERTS = {
    "SelfdefListeningSocketsTextfileEmitFailed",
    "SelfdefListeningSocketsObserverSilent",
    "SelfdefListeningSocketsTcpCountHigh",
    "SelfdefListeningSocketsZeroTcp",
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
        assert r["labels"]["subsystem"] == "selfdef-listening-sockets"
        assert r["labels"]["severity"] in ("warning", "critical")
        for ann in ("summary", "description", "runbook_url"):
            assert ann in r["annotations"]


def test_observer_silent_threshold_300s():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "> 300" in by_name["SelfdefListeningSocketsObserverSilent"]["expr"]


def test_emit_failed_references_sentinel():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert "selfdef_listening_sockets_textfile_emit_failed" in by_name[
        "SelfdefListeningSocketsTextfileEmitFailed"
    ]["expr"]


def test_tcp_high_threshold_20():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefListeningSocketsTcpCountHigh"]["expr"]
    assert "> 20" in expr
    # Must sum v4 + v6.
    assert "selfdef_listening_sockets_tcp" in expr
    assert "selfdef_listening_sockets_tcp6" in expr


def test_zero_tcp_threshold():
    by_name = {r["alert"]: r for r in _all_rules()}
    expr = by_name["SelfdefListeningSocketsZeroTcp"]["expr"]
    assert "< 1" in expr


def test_observer_fault_and_zero_tcp_critical():
    by_name = {r["alert"]: r for r in _all_rules()}
    for name in (
        "SelfdefListeningSocketsTextfileEmitFailed",
        "SelfdefListeningSocketsObserverSilent",
        "SelfdefListeningSocketsZeroTcp",
    ):
        assert by_name[name]["labels"]["severity"] == "critical"


def test_tcp_count_high_warning():
    by_name = {r["alert"]: r for r in _all_rules()}
    assert by_name["SelfdefListeningSocketsTcpCountHigh"]["labels"]["severity"] == "warning"


def test_sockets_link_labels_canonical():
    by_name = {r["alert"]: r for r in _all_rules()}
    expected = {
        "SelfdefListeningSocketsTextfileEmitFailed": "observer-fault",
        "SelfdefListeningSocketsObserverSilent":     "observer-silent",
        "SelfdefListeningSocketsTcpCountHigh":       "rollup",
        "SelfdefListeningSocketsZeroTcp":            "rollup",
    }
    for name, link in expected.items():
        assert by_name[name]["labels"].get("sockets_link") == link


def test_tcp_high_description_includes_ss_command():
    """The TcpCountHigh description MUST suggest `ss -ltn` so
    operators have an actionable diagnostic command."""
    by_name = {r["alert"]: r for r in _all_rules()}
    desc = by_name["SelfdefListeningSocketsTcpCountHigh"]["annotations"]["description"]
    assert "ss -ltn" in desc


def test_rule_group_interval_30s():
    doc = yaml.safe_load(RULES_PATH.read_text())
    g = next(g for g in doc["groups"] if g["name"] == "selfdef-listening-sockets")
    assert g["interval"] == "30s"


def test_rules_cite_selfdef_producer_commit():
    assert "ca3cad1" in RULES_PATH.read_text()


def test_runbook_sections_present_for_every_alert():
    guide = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide.read_text()
    for name in REQUIRED_ALERTS:
        assert f"#### {name}" in body


def test_tcp_high_runbook_includes_ss_diagnostic():
    guide = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"
    body = guide.read_text()
    start = body.find("#### SelfdefListeningSocketsTcpCountHigh")
    next_h = body.find("\n#### ", start + 1)
    section = body[start:next_h if next_h > 0 else len(body)]
    assert "ss -ltn" in section
