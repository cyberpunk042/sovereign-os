"""Contract for the incremental cockpit visual-system remaster.

The foundation remains intentionally opt-in while legacy panels are migrated.
Every adopter must link the one shared source and use its semantic section and
card primitives; otherwise a copied local approximation would recreate the
cross-cockpit drift this refactor removes.
"""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
FOUNDATION = REPO / "webapp" / "_shared" / "cockpit-foundations.css"
# First migration wave: the model-operation path and its directly adjacent
# runtime observability panels. Keeping the list explicit makes expansion a
# reviewed design-system decision rather than a silent, partial rollout.
ADOPTERS = (
    REPO / "webapp" / "d-01-active-sessions" / "index.html",
    REPO / "webapp" / "d-03-model-health" / "index.html",
    REPO / "webapp" / "d-05-traces" / "index.html",
    REPO / "webapp" / "d-09-hardware-pressure" / "index.html",
    REPO / "webapp" / "d-10-eval-history" / "index.html",
    REPO / "webapp" / "d-21-lm-orchestration" / "index.html",
    REPO / "webapp" / "d-22-lm-status-operability" / "index.html",
    REPO / "webapp" / "d-23-models-catalog" / "index.html",
)


def test_foundation_expresses_operational_hierarchy():
    css = FOUNDATION.read_text(encoding="utf-8")
    for selector in (".so-section", ".so-card", ".so-meter", "--so-card-shadow"):
        assert selector in css, f"shared cockpit foundation missing {selector}"


def test_adopters_use_the_shared_foundation_not_a_local_copy():
    for panel in ADOPTERS:
        html = panel.read_text(encoding="utf-8")
        assert 'href="/_shared/cockpit-foundations.css"' in html
        assert (
            "so-section" in html or "so-card" in html or "--so-surface-1" in html
        ), f"{panel.parent.name}: linked the foundation without using its surface primitives"
