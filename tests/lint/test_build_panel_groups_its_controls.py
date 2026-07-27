"""The build area must be readable, and its most consequential switch obvious.

2026-07-27, operator: "improve the build panel, it needs a revamp".

The build controls were six flat flex rows of checkboxes at identical visual
weight. Among them sat "build INSTALLER", which switches between two entirely
different artifacts — a debian-installer ISO versus a whole-disk appliance —
and read as just another toggle. The operator spent a day on an ISO that was
the wrong artifact, partly because nothing about that control said it decided
anything larger than the others.

Grouping is done with headings inserted BETWEEN existing rows rather than by
wrapping them, so every id and event handler keeps working. That matters: the
panel is 6300 lines and its JS looks controls up by id.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL = REPO_ROOT / "webapp" / "build-configurator" / "index.html"

# Controls the JS resolves by id; a revamp must not rename or drop any of them.
CRITICAL_IDS = (
    "build-installer", "root-password", "allow-locked-root", "bake-dev",
    "bake-selfdef", "bake-graceful", "bake-openclaw", "bake-open_computer",
    "bake-intelligence", "bake-model", "bake-dashboards", "bake-gui",
    "bake-frontend", "tgt-hostname", "tgt-username", "tgt-cmdline",
    "tgt-blacklist", "tgt-kdebs",
)


def panel() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_the_build_area_is_grouped():
    headings = re.findall(r'<div class="bgrp"><span>([^<]+)</span></div>', panel())
    assert len(headings) >= 5, (
        f"only {len(headings)} section heading(s); the build controls were six "
        "undifferentiated rows and need grouping to be readable"
    )
    assert len(headings) == len(set(headings)), f"duplicate headings: {headings}"


def test_the_artifact_switch_is_visually_promoted():
    text = panel()
    i = text.index('id="build-installer"')
    row = text[text.rindex("<div", 0, i):i]
    assert "bkey" in row, (
        "build INSTALLER selects between two entirely different artifacts; it "
        "must not look like the bake toggles beside it"
    )


def test_the_grouping_styles_exist():
    text = panel()
    assert ".bgrp" in text and ".bkey" in text, "grouping styles are not defined"


def test_no_control_was_lost_in_the_revamp():
    """Headings are inserted BETWEEN rows, never wrapped around them."""
    text = panel()
    missing = [i for i in CRITICAL_IDS if f'id="{i}"' not in text]
    assert not missing, f"the revamp dropped control(s): {missing}"


def test_the_markup_stays_balanced():
    text = panel()
    assert text.count("<div") == text.count("</div>"), "unbalanced <div> in the panel"
    assert text.count("<details") == text.count("</details>"), "unbalanced <details>"
