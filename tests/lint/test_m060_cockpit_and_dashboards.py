"""M060 cockpit + dashboards + UX-surface contract lint.

Locks `config/observability/m060-cockpit-and-dashboards.yaml` to the M060 spec:
the dashboard philosophy 9 operational questions (E0578), the 21-dashboard
catalog D-00..D-20 (E0579-E0582), the CLI surface (E0583), the API surface
(E0584), the IDE client surface (E0585), the 3-level configuration surfaces
(E0586), UX coherence (E0587), and the dashboard-toggle contract. No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Project boundary (R10212): D-12..D-18 are selfdef READ-ONLY mirrors.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "observability" / "m060-cockpit-and-dashboards.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M060-cockpit-and-dashboards-ux-surface.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M060"


def test_dashboard_philosophy_nine_questions():
    dp = _c()["dashboard_philosophy"]
    assert dp["doctrine"] == "A dashboard should not show vanity graphs"
    assert len(dp["operational_questions"]) == 9
    assert dp["operational_questions"][0] == "Is the Blackwell idle?"
    assert dp["operational_questions"][-1] == "Is the system becoming more efficient over time?"


def test_twenty_one_dashboards_d00_to_d20():
    ids = [x["id"] for x in _c()["dashboards"]]
    assert ids == [f"D-{n:02d}" for n in range(21)], f"dashboard id drift: {ids}"
    assert len(ids) == 21


def test_selfdef_mirror_dashboards_are_readonly():
    mirrors = [x for x in _c()["dashboards"] if x["scope"] == "selfdef-mirror-readonly"]
    ids = [x["id"] for x in mirrors]
    assert ids == ["D-12", "D-13", "D-14", "D-15", "D-16", "D-17", "D-18"], (
        f"selfdef-mirror boundary drift (R10212): {ids}")


def test_cockpit_must_show_seven_views():
    v = _c()["cockpit_must_show"]["views"]
    assert v == ["running", "cost", "can-touch", "changed", "approval-waiting",
                 "resumable", "rollback-points"]


def test_ui_surfaces_eleven():
    s = _c()["ui_surfaces"]["surfaces"]
    assert len(s) == 11 and "adapter status" in s and "hardware pressure" in s


def test_local_dashboard_six_panels():
    p = _c()["local_dashboard_panels"]["panels"]
    assert p == ["profiles", "costs", "traces", "model health", "memory", "approvals"]


def test_cli_five_verbs():
    v = [x["verb"] for x in _c()["cli_surface"]["verbs"]]
    assert v == ["sovereign run <task>", "sovereign resume <session-id>",
                 "sovereign inspect <trace-id>", "sovereign rollback <commit-id>",
                 "sovereign profile <name>"]


def test_api_surface_five_primary_four_secondary():
    api = _c()["api_surface"]
    assert len(api["anthropic_first_primary"]) == 5
    assert "POST /v1/messages" in api["anthropic_first_primary"]
    assert api["openai_compatible_secondary"] == ["POST /v1/chat/completions",
                                                  "POST /v1/responses", "POST /v1/embeddings",
                                                  "GET /v1/models"]


def test_ide_clients_three():
    ic = _c()["ide_clients"]
    assert ic["clients"] == ["Claude Code", "Cline", "OpenCode"]
    assert "base_url override" in ic["mechanism"]


def test_configuration_three_levels():
    lv = [x["level"] for x in _c()["configuration_surfaces"]["levels"]]
    assert lv == ["User", "Power user", "System"]


def test_ux_coherence_and_toggle_contract():
    ux = _c()["ux_coherence"]
    assert len(ux["standards"]) == 5 and "keyboard shortcuts" in ux["standards"]
    assert ux["operator_direction"] == "you cannot re-invent what UX mean"
    dt = _c()["dashboard_toggle"]
    assert dt["state_path"] == "/etc/sovereign-os/dashboards.toml"
    assert dt["signed_via"] == "selfdef MS003"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01003", "M01006", "M01014", "M01015", "M01016", "M01018", "M01019"):
        assert mod in body, f"{mod} not in the M060 milestone (must trace to spec)"


def test_traces_to_selfdef_mirror_features():
    body = MILESTONE.read_text()
    for feat in ("F05069", "F05075", "F05076", "F05077"):
        assert feat in body, f"{feat} not in the M060 milestone (must trace to spec)"
