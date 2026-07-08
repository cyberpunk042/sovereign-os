"""Dashboard palette consistency L1 lint — pins SDD-040's
sovereignty-clean palette contract across all webapp/d-*/index.html
dashboards.

SDD-040 documents 10 CSS custom-property palette tokens lifted from
the master-dashboard `:root` block. The sovereignty-clean UX doctrine
requires every D-NN dashboard to use the SAME palette so the operator
sees a coherent visual surface across all dashboards.

A future edit that introduces a one-off color override in a single
dashboard would silently fragment the visual contract. This lint
catches that at push-time.

Cousin pattern to test_sdd_040_cockpit_dashboard_bridge.py (which
pins the doctrine document's claim about the palette); this lint
pins the IMPLEMENTATION against the same set.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_DIR = REPO_ROOT / "webapp"

# The 10 CSS custom-property palette tokens. Verbatim list — must
# stay aligned with SDD-040 + master-dashboard :root block.
PALETTE_TOKEN_DECLARATIONS = [
    "--bg:",
    "--fg:",
    "--muted:",
    "--accent:",
    "--good:",
    "--bad:",
    "--warn:",
    "--panel:",
    "--border:",
    "--mono:",
]

# Canonical RGB values for the 6 color tokens whose hex MUST match
# across all dashboards (--mono is a font stack; --panel/--border
# allowed to vary slightly per dashboard).
CANONICAL_HEX_VALUES = {
    "--bg": "#0e0e0e",
    "--fg": "#e6e6e6",
    "--muted": "#888",
    "--accent": "#9bd1ff",
    "--good": "#7ad17a",
    "--bad": "#ff7676",
    "--warn": "#e6c062",
}


def _discover_dashboard_indexes():
    """Yield Path objects for every webapp/d-*/index.html."""
    if not WEBAPP_DIR.is_dir():
        return []
    out = []
    for child in sorted(WEBAPP_DIR.iterdir()):
        if not child.is_dir():
            continue
        if not child.name.startswith("d-"):
            continue
        idx = child / "index.html"
        if idx.is_file():
            out.append(idx)
    return out


def test_dashboards_exist():
    """At least one webapp/d-*/index.html dashboard must exist for
    this lint to be meaningful."""
    indexes = _discover_dashboard_indexes()
    assert indexes, (
        "no webapp/d-*/index.html dashboards found — palette-"
        "consistency lint has no targets"
    )


def test_all_dashboards_declare_palette_tokens():
    """Every D-NN dashboard's index.html must declare all 10 palette
    tokens (sovereignty-clean palette contract per SDD-040)."""
    indexes = _discover_dashboard_indexes()
    missing_per_file = {}
    for idx in indexes:
        body = idx.read_text(encoding="utf-8", errors="replace")
        missing = [tok for tok in PALETTE_TOKEN_DECLARATIONS if tok not in body]
        if missing:
            missing_per_file[idx.relative_to(REPO_ROOT).as_posix()] = missing
    assert not missing_per_file, (
        f"Dashboards missing palette tokens (SDD-040 contract):\n"
        + "\n".join(
            f"  {fp}: {toks}" for fp, toks in sorted(missing_per_file.items())
        )
        + "\nEvery webapp/d-*/index.html must declare all 10 CSS "
        "custom-property palette tokens. If a dashboard genuinely "
        "needs a different palette, propose an SDD-040 evolution "
        "round first."
    )


def test_canonical_dark_palette_hex_values_present():
    """SDD-040 dark-palette canonical hex values must appear somewhere
    in each dashboard's CSS. Dashboards may also ship a light-palette
    overlay (prefers-color-scheme), but the dark-palette canonical
    contract is non-negotiable — without it the operator's nighttime
    default-dark UX is broken.

    Per-token presence (substring match) is sufficient — we don't
    constrain WHERE the token appears so dashboards with light+dark
    multi-palette stay green."""
    indexes = _discover_dashboard_indexes()
    missing = []
    for idx in indexes:
        body = idx.read_text(encoding="utf-8", errors="replace").lower()
        for token, canonical_hex in CANONICAL_HEX_VALUES.items():
            if canonical_hex.lower() not in body:
                missing.append(
                    f"{idx.relative_to(REPO_ROOT).as_posix()}: "
                    f"canonical {token}={canonical_hex} not found"
                )
    assert not missing, (
        f"Dashboards missing SDD-040 canonical dark-palette hex "
        f"values:\n"
        + "\n".join(f"  {m}" for m in missing[:20])
        + "\nEvery dashboard must include the canonical dark-palette "
        "hex values so the operator's default-dark UX is consistent. "
        "A light-palette overlay (prefers-color-scheme) is allowed "
        "but cannot replace the dark-palette canonical set."
    )


def test_dashboards_declare_mono_font_stack():
    """The --mono custom property must be declared in every dashboard
    so the operator's monospace UX is consistent."""
    indexes = _discover_dashboard_indexes()
    missing = [
        idx.relative_to(REPO_ROOT).as_posix()
        for idx in indexes
        if "--mono:" not in idx.read_text(encoding="utf-8", errors="replace")
    ]
    assert not missing, (
        f"Dashboards missing --mono font-stack declaration: {missing}.\n"
        "Sovereignty-clean UX requires every dashboard to declare the "
        "monospace stack token."
    )


def test_dashboards_avoid_cdn_fonts():
    """SDD-040 + master-dashboard doctrine: 'no fonts fetched from
    elsewhere'. Any <link rel="stylesheet" href="https://fonts...">
    or similar CDN font fetch violates sovereignty-clean."""
    indexes = _discover_dashboard_indexes()
    cdn_offenders = []
    forbidden_patterns = [
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "https://fonts.",
        "use.typekit.net",
    ]
    for idx in indexes:
        body = idx.read_text(encoding="utf-8", errors="replace")
        for pat in forbidden_patterns:
            if pat in body:
                cdn_offenders.append(
                    f"{idx.relative_to(REPO_ROOT).as_posix()}: contains {pat!r}"
                )
                break
    assert not cdn_offenders, (
        f"Dashboards fetching CDN fonts (sovereignty-clean violation):\n"
        + "\n".join(f"  {o}" for o in cdn_offenders)
    )


def test_minimum_dashboard_count():
    """SDD-040 + M060 target ≥ 14 shipped dashboards. The bridge
    artifact named that floor; this lint catches accidental deletion."""
    indexes = _discover_dashboard_indexes()
    assert len(indexes) >= 14, (
        f"only {len(indexes)} webapp/d-*/index.html dashboards found "
        f"(SDD-040 + M060 floor is 14). If you deliberately removed a "
        "dashboard, propose a milestone evolution round first."
    )
