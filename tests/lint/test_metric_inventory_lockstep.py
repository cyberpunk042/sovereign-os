"""Layer 1 lint — every `sovereign_os_*` metric emitted by the source
tree MUST appear in the operator-facing inventory at
`docs/observability/dashboards/README.md`.

Catches "I added a metric but forgot to document it" — a silent
operator-blindness bug. Operators reading the inventory should be
able to discover every metric they can scrape; if the inventory drifts
behind the code, the inventory is a lie.

Inverse direction (dashboard refs an emitter that doesn't exist) is
covered by `test_dashboard_metrics_lockstep.py`. Together they form
a two-way contract: code ↔ dashboard ↔ inventory.

Waiver path: list the metric token under a `LAYER-B-WAIVER:` comment
in the README, OR drop the metric.
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "docs" / "observability" / "dashboards" / "README.md"
EMITTING_ROOTS = [REPO_ROOT / "scripts", REPO_ROOT / "systemd" / "system"]

METRIC_NAME_RE = re.compile(r"\bsovereign_os_[a-z][a-z0-9_]*\b")

# Tokens that grep up as `sovereign_os_*` but are NOT metric names —
# label fragments, function suffixes, comment chatter. Add cautiously;
# every entry weakens the gate.
KNOWN_NON_METRICS = {
    "sovereign_os_trap_err",  # bash trap name in common.sh, not a metric
}


def _emitted_metric_names() -> set[str]:
    """Scan emit_metric / emit_metric_set call sites and # HELP lines.
    We restrict to lines that look like a metric DEFINITION (emit_metric
    NAME, emit_metric_set BASENAME with literal metric lines, # HELP
    NAME description, # TYPE NAME type), not arbitrary substring
    matches — otherwise label-value strings inflate the set."""
    found: set[str] = set()
    patterns = [
        # emit_metric sovereign_os_xxx
        re.compile(r"emit_metric\s+(sovereign_os_[a-z][a-z0-9_]*)\b"),
        # "sovereign_os_xxx value" inside emit_metric_set arg blocks
        re.compile(r"\"(sovereign_os_[a-z][a-z0-9_]*)\s+\$?\{?"),
        re.compile(r"'(sovereign_os_[a-z][a-z0-9_]*)\s"),
        # # HELP / # TYPE lines
        re.compile(r"#\s+(?:HELP|TYPE)\s+(sovereign_os_[a-z][a-z0-9_]*)\b"),
    ]
    for root in EMITTING_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            for pat in patterns:
                for m in pat.findall(text):
                    found.add(m)
    return found - KNOWN_NON_METRICS


def _inventoried_metric_names() -> set[str]:
    text = INVENTORY.read_text()
    return set(METRIC_NAME_RE.findall(text))


def test_inventory_present():
    assert INVENTORY.is_file(), f"metric inventory missing: {INVENTORY}"


def test_emitting_dirs_present():
    for root in EMITTING_ROOTS:
        assert root.is_dir(), f"emitting source dir missing: {root}"


def test_every_emitted_metric_is_documented():
    emitted = _emitted_metric_names()
    documented = _inventoried_metric_names()
    undocumented = sorted(emitted - documented)
    assert not undocumented, (
        f"{len(undocumented)} metric(s) emitted by scripts/ but NOT listed in "
        f"docs/observability/dashboards/README.md inventory:\n"
        + "\n".join(f"  - {m}" for m in undocumented)
        + "\n\nFix: add each metric (with label set + 1-line meaning) to the "
        "relevant section in the README. Operators rely on the inventory to "
        "know what they can scrape."
    )


def test_inventory_has_no_orphan_entries():
    """Inverse: every metric in the inventory should be emitted by some
    script. Otherwise the inventory is advertising vapor.

    Exception: build-step metrics use a generic `step` label in
    examples, e.g. `sovereign_os_build_step_render_total` is real but
    `sovereign_os_build_step_xxx_total` wildcards would also be valid
    placeholders if any were ever added. We strictly compare names —
    no fuzzy wildcards.
    """
    emitted = _emitted_metric_names()
    documented = _inventoried_metric_names()
    orphans = sorted(documented - emitted - KNOWN_NON_METRICS)
    assert not orphans, (
        f"{len(orphans)} metric(s) listed in inventory but NOT emitted by "
        f"any script:\n"
        + "\n".join(f"  - {m}" for m in orphans)
        + "\n\nFix: either add the emit_metric call OR drop the inventory row."
    )
