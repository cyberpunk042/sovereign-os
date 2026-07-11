"""Design-token scale contract (SDD-145).

The cockpit had no design-token scale — 751 font-size literals (29 distinct),
363 border-radius (16 distinct), thousands of spacing literals, hand-typed per
panel. SDD-145 introduced ONE grounded, rem-based scale in the synced app-shell
`:root` (`--fs-*` / `--space-*` / `--radius-*`), values chosen to land on the
fleet's dominant literals so adoption is a pure `var()` indirection.

Following the SDD-137 shape (define fleet-wide, prove on the reference panel,
don't force big-bang), this pins:
  1. the app-shell `:root` DECLARES every scale token (canonical source);
  2. build-configurator (the grammar-doc reference impl) USES each family,
     proving the scale is real and adoptable.

Fleet-wide adoption is gradual (follow-up SDDs) — no panel-wide literal ban
here, so unconverted panels stay green until they adopt.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"
APP_SHELL = WEBAPP / "_shared" / "app-shell-snippet.html"
REFERENCE = WEBAPP / "build-configurator" / "index.html"

FS_TOKENS = ("--fs-2xs", "--fs-xs", "--fs-sm", "--fs-base", "--fs-md", "--fs-lg")
RADIUS_TOKENS = ("--radius-xs", "--radius-sm", "--radius-md", "--radius-lg", "--radius-pill")
SPACE_TOKENS = ("--space-2xs", "--space-xs", "--space-sm", "--space-md",
                "--space-lg", "--space-xl", "--space-2xl", "--space-3xl")
ALL_TOKENS = FS_TOKENS + RADIUS_TOKENS + SPACE_TOKENS


def _authored_css(body: str) -> str:
    """Panel-authored CSS only — cut at the synced app-shell block (mirrors
    tests/lint/test_responsive_grid_contract.py)."""
    i = body.find("APP-SHELL:BEGIN")
    return body[:i] if i > 0 else body


def test_app_shell_root_declares_the_full_scale():
    body = APP_SHELL.read_text(encoding="utf-8")
    missing = [t for t in ALL_TOKENS if f"{t}:" not in body]
    assert not missing, (
        f"the app-shell :root must declare every design-scale token (SDD-145): missing {missing}"
    )


def test_reference_panel_adopts_each_scale_family():
    """build-configurator (the reference impl) must reference each family via
    var(), proving the scale is real + adoptable — not a set of unused vars."""
    css = _authored_css(REFERENCE.read_text(encoding="utf-8"))
    for family, floor in (("var(--fs-", 3), ("var(--radius-", 3), ("var(--space-", 3)):
        n = css.count(family)
        assert n >= floor, (
            f"build-configurator must adopt the {family[:-1]}*) scale family "
            f"(>= {floor} refs) to prove the scale; found {n}"
        )
