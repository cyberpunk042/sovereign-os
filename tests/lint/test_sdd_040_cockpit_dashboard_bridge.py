"""SDD-040 cockpit-dashboard-implementation-bridge L1 lint.

Pins the SDD-040 contract so future edits don't silently drop the
mission, the UX doctrine verbatim quote, the palette token table, or
the 21-dashboard catalog reference.

SDD-040 is the bridge artifact between the M060 cockpit-dashboard
catalog (D-00..D-20) and the `/webapp/*` implementations. Its
load-bearing claims:

  1. mission narrative + correct M060 dashboard count (21)
  2. UX doctrine verbatim quote (preserved from master-dashboard)
  3. complete palette token table (10 CSS custom properties)
  4. all 21 D-NN dashboard slots enumerated in the coverage map

Operators may edit prose freely; section headers + the named
load-bearing fragments stay pinned.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "040-cockpit-dashboard-implementation-bridge.md"

REQUIRED_SECTIONS = [
    "## Mission",
    "## UX doctrine (preserved from existing dashboards)",
    "## M060 → webapp coverage map",
    "## Implementation ordering (operator-priority)",
    "## Decisions locked here",
    "## Open questions (Q-040)",
    "## Closing",
]

# Verbatim quote preserved from /webapp/master-dashboard/index.html.
# The bridge claims this quote is the operator-validated UX doctrine;
# silently rewriting it would dissolve the bridge contract.
UX_DOCTRINE_VERBATIM = (
    "Operator-§1g UX: readable in 30 seconds, monochrome palette, "
    "no JS framework, no CDN, no fonts fetched from elsewhere — "
    "sovereignty-clean single-file webapp."
)

# The CSS custom-property palette tokens lifted from :root block.
# Renaming/dropping any token would force every dashboard to drift
# from the sovereignty-clean visual contract.
PALETTE_TOKENS = [
    "--bg",
    "--fg",
    "--muted",
    "--accent",
    "--good",
    "--bad",
    "--warn",
    "--panel",
    "--border",
    "--mono",
]

# 21-dashboard catalog slots (M060 D-00..D-20). The bridge MUST
# reference every slot at least once in its coverage map.
DASHBOARD_SLOTS = [f"D-{n:02d}" for n in range(21)]  # D-00..D-20


def test_sdd_040_exists():
    """SDD-040 file must be present."""
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_040_has_required_sections():
    """All declared section headers must appear."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-040 missing required sections: {missing}. "
        "If you renamed deliberately, update REQUIRED_SECTIONS in "
        "the same commit."
    )


def test_sdd_040_sections_in_order():
    """Required sections must appear in declaration order."""
    body = SDD_PATH.read_text(encoding="utf-8")
    positions = [(s, body.index(s)) for s in REQUIRED_SECTIONS if s in body]
    actual_order = [s for s, _ in sorted(positions, key=lambda x: x[1])]
    assert actual_order == REQUIRED_SECTIONS, (
        f"SDD-040 sections out of order:\n"
        f"  expected: {REQUIRED_SECTIONS}\n"
        f"  actual:   {actual_order}"
    )


def test_sdd_040_carries_ux_doctrine_verbatim():
    """The operator-validated UX doctrine quote must appear verbatim
    (any silent rewrite dissolves the bridge contract)."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert UX_DOCTRINE_VERBATIM in body, (
        "SDD-040 must carry the master-dashboard UX-doctrine quote "
        "verbatim — silent paraphrase is forbidden per SDD-037 "
        "verbatim-preservation doctrine."
    )


def test_sdd_040_documents_all_palette_tokens():
    """All 10 CSS custom-property palette tokens must be documented."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [tok for tok in PALETTE_TOKENS if tok not in body]
    assert not missing, (
        f"SDD-040 missing palette tokens: {missing}. The bridge claims "
        "to fully document the sovereignty-clean palette contract; "
        "every token must appear."
    )


def test_sdd_040_references_all_21_dashboard_slots():
    """All 21 D-NN dashboard slots must appear in the bridge."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in DASHBOARD_SLOTS if s not in body]
    assert not missing, (
        f"SDD-040 missing dashboard slots: {missing}. The bridge is "
        "the M060 → webapp coverage map; every D-NN slot (D-00..D-20) "
        "must appear at least once."
    )


def test_sdd_040_declares_source_milestone():
    """SDD-040 must point at M060 explicitly so the bridge target is
    unambiguous."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "M060" in body, (
        "SDD-040 must reference M060 explicitly as the source milestone"
    )


def test_sdd_040_implementation_surface_named():
    """Implementation surface (/webapp/) must be named so the bridge
    output target is unambiguous."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "/webapp/" in body, (
        "SDD-040 must name the /webapp/ implementation surface"
    )


def test_sdd_040_listed_in_index():
    """SDD-040 must appear in docs/sdd/INDEX.md so cross-link tooling
    can discover it."""
    index_path = REPO_ROOT / "docs" / "sdd" / "INDEX.md"
    if not index_path.is_file():
        return  # tolerated if INDEX absent
    index_body = index_path.read_text(encoding="utf-8")
    assert "040" in index_body, (
        "SDD-040 must be listed in docs/sdd/INDEX.md"
    )
