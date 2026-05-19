"""R548 (E5++) — SDD-039 §1g 8-surface delivery contract lint.

Pins SDD-039's load-bearing content so a future "tidy-up" pass can't
silently drop the operator-verbatim anchors or the historic-milestone
table.

Operator §1g verbatim (R453 anchor, sacrosanct):

  "everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Operator §1g STANDING RULE (R456-anchored, sacrosanct):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

Both quotes are pinned verbatim — the lint fails loud on any
paraphrase / silent compression.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD = REPO_ROOT / "docs" / "sdd" / "039-eight-surface-delivery-contract.md"
INDEX = REPO_ROOT / "docs" / "sdd" / "INDEX.md"


def _sdd() -> str:
    return SDD.read_text(encoding="utf-8")


R453_VERBATIM = (
    'everything is not just core, not just cli, not just TUI, '
    'not just\n>  API, not just tool and MCP but also Dashboards '
    'and Web Apps and\n>  Services'
)

R456_STANDING_RULE_VERBATIM = (
    'If you think something is really already done, ask yourself if\n'
    '>  you covered all angles and levels and layers and even if then\n'
    '>  improve it. Do not minimize or settle for less.'
)


def test_sdd_039_file_exists():
    assert SDD.is_file(), f"SDD-039 must exist at {SDD}"


def test_sdd_039_status_block():
    txt = _sdd()
    for marker in ("Status:", "Owner:", "Last updated:"):
        assert marker in txt, (
            f"SDD-039 must include canonical status block marker "
            f"{marker!r}"
        )


def test_sdd_039_quotes_r453_verbatim():
    """The §1g 8-surface anchor MUST appear verbatim — operator words
    sacrosanct, no paraphrase tolerated."""
    txt = _sdd()
    assert R453_VERBATIM in txt, (
        "SDD-039 must quote the R453 operator §1g 8-surface anchor "
        "VERBATIM (no paraphrase / no compression)"
    )


def test_sdd_039_quotes_r456_standing_rule_verbatim():
    """The R456 STANDING RULE MUST appear verbatim — operator words
    sacrosanct."""
    txt = _sdd()
    assert R456_STANDING_RULE_VERBATIM in txt, (
        "SDD-039 must quote the R456 operator §1g STANDING RULE "
        "VERBATIM (no paraphrase / no compression)"
    )


def test_sdd_039_enumerates_all_8_surfaces():
    """SDD-039 must enumerate the 8-surface vocabulary verbatim.
    Order matters — the operator's verbatim phrasing carries the
    progression core → service."""
    txt = _sdd()
    for surf in (
        "`core`", "`cli`", "`tui`", "`api`", "`mcp`",
        "`dashboard`", "`webapp`", "`service`",
    ):
        assert surf in txt, (
            f"SDD-039 must enumerate surface {surf} in the ladder table"
        )


def test_sdd_039_codifies_r478_precision():
    """The structural-vs-FUTURE distinction (R478) is load-bearing for
    the anti-min surface-gap pattern; SDD-039 must surface it."""
    txt = _sdd()
    assert "R478" in txt, "SDD-039 must cite R478 (precision ruling)"
    assert "structural" in txt.lower()
    assert "future" in txt.lower()


def test_sdd_039_codifies_r539_historic_milestone():
    """The R539 historic ceiling-closure is the load-bearing anchor
    for the way-forward vector (no new surface promotions; quality of
    existing surfaces only)."""
    txt = _sdd()
    assert "R539" in txt
    low = txt.lower()
    assert "rotation pool" in low or "exhausted" in low, (
        "SDD-039 must surface the R539 'rotation pool exhausted' state"
    )
    assert "twelfth" in low or "12" in txt, (
        "SDD-039 must surface the twelfth-module milestone"
    )


def test_sdd_039_enumerates_4_instrument_compliance_suite():
    """SDD-039 must surface the 4-instrument compliance rollup that
    enforces the §1g contract."""
    txt = _sdd()
    for instrument in (
        "surface-map",
        "doc-coverage",
        "anti-minimization-audit",
        "ux-design-audit",
    ):
        assert instrument in txt, (
            f"SDD-039 must reference 4-instrument suite member "
            f"{instrument!r}"
        )
    assert "R458" in txt, "SDD-039 must cite R458 (compliance aggregator)"


def test_sdd_039_anchors_r546_dashboard_symmetry():
    """The R546 verb-coverage symmetry is the most recent closure —
    SDD-039 must anchor it."""
    txt = _sdd()
    assert "R546" in txt
    assert "R547" in txt


def test_sdd_039_anchors_r462_cross_repo():
    """Cross-repo (R462 / SDD-038) participation is part of the
    contract; SDD-039 must cite the binding."""
    txt = _sdd()
    assert "R462" in txt
    assert "SDD-038" in txt
    assert "SurfaceManifest" in txt or "surface-manifest" in txt.lower()


def test_sdd_039_listed_in_index():
    """INDEX.md must carry an SDD-039 row so the doc is discoverable."""
    txt = INDEX.read_text(encoding="utf-8")
    rows = [
        line for line in txt.splitlines()
        if line.startswith("| 039 ")
    ]
    assert len(rows) == 1, (
        f"INDEX.md must contain exactly one '039' row; got {len(rows)}"
    )
    row = rows[0]
    assert "8-surface" in row or "8 surface" in row.lower(), (
        f"INDEX row for SDD-039 must mention 8-surface; got {row!r}"
    )


def test_sdd_039_index_row_does_not_clobber_038():
    """Inserting SDD-039 above SDD-038 must NOT destroy the
    pre-existing 038 row."""
    txt = INDEX.read_text(encoding="utf-8")
    rows = [
        line for line in txt.splitlines()
        if line.startswith("| 038 ")
    ]
    assert rows, "INDEX.md must still contain the SDD-038 row"
    assert "Cross-repo binding" in rows[0]


def test_sdd_039_open_questions_present():
    """Canonical SDD shape: open-questions section with at least one
    Q-039-X row."""
    txt = _sdd()
    assert "Open questions" in txt or "open questions" in txt.lower()
    assert "Q-039-A" in txt
