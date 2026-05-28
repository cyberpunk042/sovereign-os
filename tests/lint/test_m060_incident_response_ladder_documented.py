"""M060 incident-response surface ladder documented in the deploy guide.

Surfaces that work under DIFFERENT failure modes — operator needs to
know which CLI verb works when Prometheus is down vs when selfdefd is
down. Documenting only one path (alerts → Grafana) silently strands
operators when that path itself is the unhealthy component.

This test locks the doc against regression: the ladder section must
list every CLI surface I've shipped (m060-doctor, m060-metrics
with + without --artifact), and the table must include the
"works when X is down" column so operators see the relevance.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = REPO_ROOT / "docs" / "operator" / "m060-deployment-guide.md"


def _body() -> str:
    return GUIDE_PATH.read_text()


def test_guide_has_incident_response_ladder_section():
    body = _body()
    assert "## Incident-response surface ladder" in body, (
        "deploy guide missing the Incident-response surface ladder section"
    )


def test_ladder_documents_both_cli_verbs():
    body = _body()
    # The two load-bearing CLI verbs MUST appear in the ladder.
    assert "selfdefctl m060-doctor" in body, (
        "ladder must document selfdefctl m060-doctor — works when "
        "selfdefd daemon is down (filesystem-only)"
    )
    assert "selfdefctl m060-metrics" in body, (
        "ladder must document selfdefctl m060-metrics — works when "
        "Prometheus is down (direct daemon /metrics)"
    )


def test_ladder_documents_artifact_filter():
    body = _body()
    assert "selfdefctl m060-metrics --artifact" in body, (
        "ladder must document the --artifact filter for single-publisher "
        "drill-down during incident response"
    )


def test_ladder_documents_failure_mode_per_surface():
    """The whole POINT of the ladder is showing which surface works when
    each higher-up surface is down. Drift catch on this column."""
    body = _body()
    # Header / wording flexibility — accept either explicit "Works when
    # this is DOWN" header or any per-row "when X is DOWN" mention.
    failure_phrases = (
        "DOWN",
        "Prometheus",
        "selfdefd",
    )
    ladder_idx = body.find("## Incident-response surface ladder")
    end_idx = body.find("## ", ladder_idx + len("## Incident-response surface ladder"))
    ladder_body = body[ladder_idx:end_idx].lower()
    for phrase in failure_phrases:
        assert phrase.lower() in ladder_body, (
            f"ladder section missing {phrase!r} — must surface "
            f"per-CLI-verb failure-mode independence"
        )


def test_ladder_documents_quick_triage_flow():
    """The ladder must include a copy-pasteable triage flow so operators
    don't compose it themselves at 3 AM."""
    body = _body()
    ladder_idx = body.find("## Incident-response surface ladder")
    end_idx = body.find("## ", ladder_idx + len("## Incident-response surface ladder"))
    ladder_body = body[ladder_idx:end_idx]
    assert "```bash" in ladder_body, (
        "ladder must include a fenced shell-block with the triage flow"
    )
    # The triage flow MUST exercise both CLI verbs in order.
    assert "m060-doctor" in ladder_body and "m060-metrics" in ladder_body


def test_ladder_appears_before_troubleshooting_section():
    """The ladder is the operator's FIRST stop during an incident — must
    appear before the troubleshooting table so it's seen first."""
    body = _body()
    ladder_idx = body.find("## Incident-response surface ladder")
    troubleshooting_idx = body.find("## Troubleshooting")
    assert ladder_idx > 0
    assert troubleshooting_idx > 0
    assert ladder_idx < troubleshooting_idx, (
        "Incident-response ladder must appear BEFORE Troubleshooting — "
        "operators glance at the first section during a page"
    )


def test_ladder_distinguishes_dashboard_cli_alert_surfaces():
    """Operators need to know there are 3 KINDS of surfaces: dashboards
    (visual), CLI verbs (direct query), alerts (page-trigger). The
    ladder must mention all three so the operator picks the right kind
    based on what failed."""
    body = _body()
    ladder_idx = body.find("## Incident-response surface ladder")
    end_idx = body.find("## ", ladder_idx + len("## Incident-response surface ladder"))
    ladder_body = body[ladder_idx:end_idx]
    for kind in ("dashboard", "Grafana", "alert"):
        assert kind in ladder_body, f"ladder missing {kind!r} surface kind"
