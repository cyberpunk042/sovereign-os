"""Layer 1 lint — every lifecycle hook MUST emit at least one Prometheus
metric via the SDD-016 Layer B `emit_metric` helper, or carry an
explicit `# LAYER-B-WAIVER: <reason>` comment.

Catches regressions where a new pre-install / during-install /
post-install / recurrent hook lands without observability — fleet
operators rely on these counters to alert on degradation without
scraping journald.

Found-in-the-wild: first-login-assistant.sh shipped without
emit_metric coverage despite the rest of post-install having it. This
gate would have flagged it.
"""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK_ROOTS = (
    REPO_ROOT / "scripts" / "hooks" / "pre-install",
    REPO_ROOT / "scripts" / "hooks" / "during-install",
    REPO_ROOT / "scripts" / "hooks" / "post-install",
    REPO_ROOT / "scripts" / "hooks" / "recurrent",
)


def _hook_scripts() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in HOOK_ROOTS:
        if root.is_dir():
            out.extend(sorted(root.glob("*.sh")))
    return out


def test_hook_dirs_exist():
    for root in HOOK_ROOTS:
        assert root.is_dir(), f"hook dir missing: {root}"


def test_hook_scripts_present():
    hooks = _hook_scripts()
    assert len(hooks) >= 15, f"expected ≥15 lifecycle hooks, found {len(hooks)}"


@pytest.mark.parametrize("hook", _hook_scripts(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_hook_emits_layer_b_metric(hook: pathlib.Path):
    """Hook calls emit_metric OR emit_metric_set OR has an explicit waiver."""
    text = hook.read_text()

    if "# LAYER-B-WAIVER:" in text:
        return

    has_call = "emit_metric " in text or "emit_metric_set " in text
    has_source = "observability.sh" in text

    assert has_source, (
        f"{hook.relative_to(REPO_ROOT)} does not source observability.sh "
        f"(needed to call emit_metric). Add:\n"
        f"  . \"${{__REPO_ROOT}}/scripts/build/lib/observability.sh\"\n"
        f"Or document a waiver with: # LAYER-B-WAIVER: <reason>"
    )
    assert has_call, (
        f"{hook.relative_to(REPO_ROOT)} sources observability.sh but never "
        f"calls emit_metric / emit_metric_set. Lifecycle hooks must emit "
        f"at least one counter (typically result=pass|fail). Or waive with: "
        f"# LAYER-B-WAIVER: <reason>"
    )
