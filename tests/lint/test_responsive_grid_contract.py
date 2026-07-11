"""Responsive grid contract (SDD-137) — generalizes the code-console fix.

The cockpit assistant pane opens on the right and shrinks `#so-content` by
~360px via `margin-right` (app-shell, global) — WITHOUT changing the viewport.
So a panel whose main grid keys its collapse to a viewport-width `@media` query
never reflows when the assistant opens: a bare `1fr` flexible track (min-width
auto) can't shrink below its widest content and forces horizontal overflow.

The fix (proven on code-console, SDD-112): a flexible center/main track uses
`minmax(0,1fr)` (min 0 → shrinks) instead of a bare `1fr`, and — for rigid
grids with a fixed sidebar — a `body.so-assist-open` reflow rule collapses the
grid when the assistant steals space.

This lint pins that standard so it can't regress:
  * no panel-authored `grid-template-columns` pairs a bare `1fr` flexible track
    with a fixed `Npx` track (the crush pattern);
  * the two rigid-sidebar panels (build-configurator, d-22) carry the
    `minmax(0,1fr)` main track AND a `body.so-assist-open` reflow.

Panel-authored CSS only — the synced APP-SHELL:BEGIN/END M067 block, the a11y /
responsive shared snippets, and auto-fill `minmax(...)` grids are out of scope.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"

# a bare 1fr track (NOT minmax(...,1fr)) directly next to a fixed Npx track
_CRUSH_RE = re.compile(
    r"grid-template-columns:[^;]*?(?:\b1fr\s+\d+px|\b\d+px\s+1fr)[^;]*;"
)


def _panels() -> list[Path]:
    return sorted(p for p in WEBAPP.glob("*/index.html"))


def _panel_authored_css(body: str) -> str:
    """Everything before the synced app-shell block — where each panel's own
    <style> lives (the shared block + a11y/responsive snippets follow it)."""
    i = body.find("APP-SHELL:BEGIN")
    return body[:i] if i > 0 else body


def test_no_bare_1fr_next_to_a_fixed_sidebar_track():
    """A bare `1fr` main column beside a fixed `Npx` sidebar can't shrink → it
    overflows when the assistant pane steals width. Use `minmax(0,1fr)`."""
    offenders: list[str] = []
    for idx in _panels():
        css = _panel_authored_css(idx.read_text(encoding="utf-8"))
        for m in _CRUSH_RE.finditer(css):
            offenders.append(f"{idx.parent.name}: {m.group(0).strip()}")
    assert not offenders, (
        "panel grids pairing a bare 1fr with a fixed px track (use minmax(0,1fr) "
        "so the flexible column shrinks under the assistant pane):\n  " + "\n  ".join(offenders)
    )


def test_rigid_sidebar_panels_carry_the_assist_open_reflow():
    """The two panels with a rigid fixed-sidebar grid must both use a
    `minmax(0,1fr)` main track and reflow on `body.so-assist-open` (a viewport
    media query alone never fires when the assistant shrinks #so-content)."""
    checks = {
        "build-configurator": (".wrap", "body.so-assist-open .wrap"),
        "d-22-lm-status-operability": (".devgrid", "body.so-assist-open .devgrid"),
    }
    for slug, (grid_sel, reflow_sel) in checks.items():
        body = (WEBAPP / slug / "index.html").read_text(encoding="utf-8")
        css = _panel_authored_css(body)
        # the grid's own rule must use minmax(0,1fr), not a bare 1fr flexible track
        grid_rule = re.search(re.escape(grid_sel) + r"\s*\{[^}]*grid-template-columns:[^;]*;", css)
        assert grid_rule, f"{slug}: {grid_sel} grid rule not found"
        assert "minmax(0,1fr)" in grid_rule.group(0), (
            f"{slug}: {grid_sel} must use minmax(0,1fr) for its flexible main track"
        )
        assert reflow_sel in css, (
            f"{slug}: missing `{reflow_sel}` reflow — the grid won't collapse when the "
            f"assistant pane opens (viewport media query alone won't fire)"
        )


def test_moderate_equal_split_grids_are_minmax_hardened():
    """The equal-split `1fr 1fr` grids that hold tables were hardened to
    `minmax(0,1fr) minmax(0,1fr)` so a wide cell shrinks instead of overflowing."""
    for slug in ("d-21-lm-orchestration", "d-24-cpu-features", "d-25-selfdef-management"):
        css = _panel_authored_css((WEBAPP / slug / "index.html").read_text(encoding="utf-8"))
        assert "grid-template-columns:1fr 1fr" not in css.replace(" ", " "), (
            f"{slug}: a bare `1fr 1fr` grid remains — harden to minmax(0,1fr) minmax(0,1fr)"
        )
