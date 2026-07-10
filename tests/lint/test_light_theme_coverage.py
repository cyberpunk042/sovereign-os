"""Light-theme coverage lint (SDD-126).

The app-shell's theme toggle sets `<html data-theme="light|dark">`; a panel only
actually goes light if it defines light values for its CSS vars under
`html[data-theme="light"]` (the dark `:root` is the default). Operator (2026-07-10):
"when the theme is light, isn't it supposed to be light". This pins that EVERY
cockpit panel carries the light override, so a new panel can't ship dark-only.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"


def test_every_panel_has_a_light_theme_override():
    missing = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        body = idx.read_text(encoding="utf-8")
        if '[data-theme' not in body and 'data-theme="light"' not in body:
            missing.append(idx.parent.name)
    assert not missing, (
        "these panels have no html[data-theme=\"light\"] override so they stay dark in "
        f"light theme — add one: {missing}"
    )
