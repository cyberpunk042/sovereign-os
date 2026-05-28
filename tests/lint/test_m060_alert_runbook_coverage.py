"""Every M060 chain-health alert MUST have a matching runbook section.

Each Prometheus alert in m060-chain-health.rules.yml carries a
`runbook_url` pointing at docs/operator/m060-deployment-guide.md.
This test locks the structural invariant: every alert name appears
as a section heading in the deployment guide, AND the section walks
operator through diagnosis + fix.

Drift between the rules file and the runbook is a silent paging
hazard — the alert URL goes to a section that doesn't exist or
that doesn't actually tell the operator what to do.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "config" / "prometheus" / "alerts" / "m060-chain-health.rules.yml"
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"


def _alert_names() -> list[str]:
    doc = yaml.safe_load(RULES_PATH.read_text())
    return [r["alert"] for g in doc["groups"] for r in g["rules"]]


def _guide_text() -> str:
    return GUIDE_PATH.read_text()


def test_deployment_guide_has_alert_runbook_section():
    text = _guide_text()
    assert "## Troubleshooting" in text or "### Alert runbook" in text, (
        "deployment guide missing Troubleshooting/Alert runbook section"
    )


def test_every_alert_has_a_section_heading_in_the_guide():
    """Every alert name must appear as a section heading (####) in the
    runbook — otherwise the runbook_url silently 404s on the anchor."""
    text = _guide_text()
    for name in _alert_names():
        # Section heading uses #### prefix; the alert name appears in it.
        # Be tolerant of "(critical)" / "(warning)" suffix.
        expected_heading_starts = (f"#### {name}",)
        assert any(s in text for s in expected_heading_starts), (
            f"alert {name!r} has no runbook section heading in "
            f"docs/operator/m060-deployment-guide.md"
        )


def test_every_runbook_section_contains_diagnosis_and_fix():
    """Operators paged at 3 AM need actionable diagnosis steps + an
    explicit fix — not just a description."""
    text = _guide_text()
    # Locate each alert's runbook block (from its heading up to the
    # next #### heading or end of file) and assert the operator-action
    # vocabulary is present.
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#### "):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines)
            # Strip suffix like " (critical)" / " (warning)".
            head = line[5:].strip()
            for tail in (" (critical)", " (warning)"):
                if head.endswith(tail):
                    head = head[: -len(tail)].strip()
                    break
            current_name = head
            current_lines = []
        elif line.startswith("## "):
            # Top-level section break terminates any in-flight ####
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines)
                current_name = None
                current_lines = []
        else:
            if current_name is not None:
                current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines)

    for name in _alert_names():
        assert name in sections, (
            f"alert {name!r} runbook section not parsed; expected a "
            f"`#### {name}` heading"
        )
        body = sections[name].lower()
        # Operator vocabulary that MUST appear: diagnosis + fix.
        for kw in ("diagnosis", "fix"):
            assert kw in body, (
                f"alert {name!r} runbook missing `{kw}` block — "
                f"operator paged at 3 AM has no actionable steps"
            )
        # Every runbook block must include at least one shell command.
        assert "```bash" in sections[name] or "```sh" in sections[name], (
            f"alert {name!r} runbook missing shell-command block — "
            f"operator can't copy-paste a diagnosis step"
        )


def test_runbook_sections_link_at_least_one_systemctl_or_journalctl():
    """Every runbook walks the operator through systemctl + journalctl
    inspection at some point — this is the universal first step."""
    text = _guide_text()
    for name in _alert_names():
        # Find the position of the heading, then scan forward up to
        # the next #### or ## boundary.
        idx = text.find(f"#### {name}")
        assert idx >= 0, f"alert {name!r} heading not found"
        # Take a 4 KiB window from the heading; bounded so we don't
        # falsely match content from later sections.
        window = text[idx : idx + 4096]
        # Trim at next ## heading to scope tightly.
        for boundary in ("\n## ", "\n#### "):
            next_idx = window.find(boundary, len(name) + 5)
            if next_idx > 0:
                window = window[:next_idx]
        assert ("systemctl" in window) or ("journalctl" in window), (
            f"alert {name!r} runbook section has no systemctl/journalctl "
            f"reference — first-line diagnosis missing"
        )


def test_deploy_step_for_observability_present():
    """The deployment guide must explicitly walk operators through
    installing the chain-health unit + Prometheus rules, otherwise
    the alerts ship without an install path."""
    text = _guide_text()
    assert "sovereign-m060-health-api.service" in text, (
        "deployment guide must reference the chain-health api unit"
    )
    assert "m060-chain-health.rules.yml" in text, (
        "deployment guide must reference the alert rules file"
    )
    assert "systemctl enable" in text or "systemctl daemon-reload" in text, (
        "deployment guide must show the systemctl install pattern"
    )


def test_guide_mirror_count_is_current():
    """Outdated 'all 8 mirrors stay red' string would mislead operators
    on a 10-mirror deployment."""
    text = _guide_text()
    assert "All 10 mirrors" in text or "all 10 mirrors" in text, (
        "deployment guide troubleshooting still references the old "
        "8-mirror count — drift catch"
    )
