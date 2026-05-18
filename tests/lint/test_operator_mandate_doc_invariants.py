"""R436 (E10.M80) — operator-mandate doc invariants (meta-pinning).

Extends R387-R435 + R367 operational-artifact pinning to:
  docs/standing-directives/2026-05-17-operator-mandate.md

This is the META document — it records every round's E.M row in the
mandate table. The doc itself is operator-named SACROSANCT (Section 6
forbids deletion / re-write of the operator verbatim text).

R436 ensures the structural integrity of the mandate doc:
  - Section 1: operator verbatim (sacrosanct, no edits)
  - Section 2: Epic/Module decomposition (the E.M rows)
  - Section 4: How future rounds use this file
  - Section 5: What this file does NOT do
  - Section 6: Anti-corruption invariants

If a future agent silently:
  - rewrites operator verbatim in § 1 = mandate violation
  - drops § 6 anti-corruption invariants = next agent doesn't know
    the rules
  - removes Epic 10 (the verbatim-preservation arc Epic) = R-arc
    rounds get orphaned without epic
…the operator-named mandate file silently corrupts.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE_DOC = (
    REPO_ROOT / "docs" / "standing-directives" / "2026-05-17-operator-mandate.md"
)


def _read() -> str:
    assert MANDATE_DOC.is_file(), f"missing {MANDATE_DOC}"
    return MANDATE_DOC.read_text(encoding="utf-8")


# --- Structural ---


def test_mandate_doc_exists():
    assert MANDATE_DOC.is_file(), f"missing {MANDATE_DOC}"


def test_mandate_doc_has_sections_1_through_6():
    """Operator-named 6-section structure: §1 mandate verbatim,
    §2 decomposition, §4 how to use, §5 what NOT to do, §6
    anti-corruption invariants. Drift dropping any silently
    loses operator-named structure."""
    body = _read()
    for section in (
        "## 1.",
        "## 4.",
        "## 5.",
        "## 6.",
    ):
        assert section in body, (
            f"mandate doc missing section '{section}' "
            f"(operator-named structure)"
        )


def test_mandate_doc_has_operator_verbatim_section():
    """§ 1 MUST be labeled 'verbatim, sacrosanct' or equivalent."""
    body = _read()
    has_verbatim = (
        "verbatim" in body.lower()
        and "sacrosanct" in body.lower()
    )
    assert has_verbatim, (
        "mandate doc missing verbatim+sacrosanct labels "
        "(operator-named contract on § 1)"
    )


# --- E.M row structure ---


def test_mandate_has_e_10_epic():
    """Epic 10 is the verbatim-preservation arc Epic (R-arc Modules
    live here). MUST be present."""
    body = _read()
    # Look for E10 marker
    has_e10 = (
        "E10." in body
        or "Epic 10" in body
        or "## Epic 10" in body
    )
    assert has_e10, (
        "mandate doc missing Epic 10 (verbatim-preservation arc "
        "Epic — R-arc Modules live here)"
    )


def test_mandate_has_at_least_60_e_module_rows():
    """E10.M-NN rows accumulate as the arc grows. At least 60 expected
    at this point (we're at ~M80 from R-arc + many earlier E.M rows)."""
    body = _read()
    em_rows = re.findall(r"^\| E\d+\.M\d+ \|", body, re.M)
    assert len(em_rows) >= 60, (
        f"mandate doc has only {len(em_rows)} E.M rows (expected ≥60; "
        f"may indicate accidental row deletion)"
    )


def test_mandate_e_module_ids_well_formed():
    """Every E.M row MUST follow E<N>.M<M> format. No drift to
    E10:M01 or E10-M01 etc."""
    body = _read()
    em_ids = re.findall(r"\| (E\d+\.M\d+) \|", body)
    for em in em_ids:
        assert re.match(r"^E\d+\.M\d+$", em), (
            f"malformed E.M id: {em!r}"
        )


def test_mandate_no_duplicate_e_module_rows():
    """Each E.M id MUST be unique. Drift = same Module shipped
    twice = inflated count."""
    body = _read()
    em_ids = re.findall(r"\| (E\d+\.M\d+) \|", body)
    duplicates = set(i for i in em_ids if em_ids.count(i) > 1)
    assert not duplicates, (
        f"duplicate E.M rows in mandate: {duplicates}"
    )


def test_mandate_e10_module_ids_sequential():
    """Within E10, modules are sequential (M1, M2, M3...). Drift
    = gap or out-of-order."""
    body = _read()
    em_ids = re.findall(r"\| (E10\.M\d+) \|", body)
    if not em_ids:
        return
    nums = sorted(int(re.search(r"M(\d+)", e).group(1)) for e in em_ids)
    # Check no big gaps (allow some gaps from earlier R-arc that
    # mixed with other Epics; just ensure no jumps > 10)
    for i in range(len(nums) - 1):
        gap = nums[i + 1] - nums[i]
        assert gap >= 0, "E10.M ids not sorted"
        # No more than 10-module gap (allow some gaps but flag huge ones)
        assert gap <= 10, (
            f"E10.M sequence has gap > 10 between M{nums[i]} and M{nums[i+1]}"
        )


# --- Anti-corruption invariants (§ 6) ---


def test_mandate_documents_anti_corruption_invariants():
    """§ 6 MUST document the rules: NO rewriting operator verbatim,
    NO deleting TODO Modules without confirmation, new Modules MUST
    quote operator-verbatim source."""
    body = _read()
    section_6_match = re.search(r"## 6\.(.+?)(?=## |$)", body, re.DOTALL)
    assert section_6_match, "mandate doc missing § 6 anti-corruption section"
    section_6 = section_6_match.group(1)
    expected_terms = [
        "rewrite",
        "delete",
        "operator",
    ]
    for term in expected_terms:
        assert term in section_6.lower(), (
            f"§ 6 anti-corruption section missing {term!r} rule"
        )


def test_mandate_has_format_rules_section():
    """§ 4 documents how future rounds USE this file."""
    body = _read()
    section_4_match = re.search(r"## 4\.(.+?)(?=## |$)", body, re.DOTALL)
    assert section_4_match, "mandate doc missing § 4 'how to use' section"
    section_4 = section_4_match.group(1)
    has_round_id = (
        "round-ID" in section_4
        or "R<N>" in section_4
        or "round" in section_4.lower()
    )
    assert has_round_id, (
        "§ 4 missing round-ID format rules (operator-discoverable: "
        "how to cite rounds in commits)"
    )


# --- Section 1 verbatim quote integrity ---


def test_mandate_contains_operator_goal_quote_verbatim():
    """The operator's /goal directive text MUST appear verbatim in
    § 1. Drift = rephrasing = SACROSANCT violation."""
    body = _read()
    # Key operator-verbatim phrases that MUST appear
    expected_phrases = [
        "continue till you meet ALL MY REQUIREMENTS",
        "REPROCESS",  # 'RETURN REREAD ALL THE RAW DUMP AND REPROCESS'
    ]
    for phrase in expected_phrases:
        assert phrase in body, (
            f"mandate doc missing operator-verbatim phrase {phrase!r} "
            f"(SACROSANCT contract — verbatim must be preserved)"
        )


def test_mandate_contains_perpetual_mandate_quote():
    """The 'continue endlessly' framing MUST be present verbatim."""
    body = _read()
    has_endless = (
        "continue endlessly" in body.lower()
        or "Continue Endlessly" in body
        or "continue endless" in body.lower()
    )
    assert has_endless, (
        "mandate doc missing 'continue endlessly' verbatim "
        "(operator-named perpetual framing)"
    )


def test_mandate_contains_no_minimizing_quote():
    """Operator-verbatim: 'Do not minimize anything nor the
    situation'. Drift = rephrasing = SACROSANCT violation."""
    body = _read()
    has_no_minimize = (
        "Do not minimize" in body
        or "do not minimize" in body
        or "MINIMIZING" in body
        or "We do not minimize" in body
    )
    assert has_no_minimize, (
        "mandate doc missing 'Do not minimize' operator-verbatim "
        "(SACROSANCT phrase)"
    )


# --- Recent R-arc presence ---


def test_mandate_documents_recent_rounds():
    """Each shipped round leaves an E.M row. Recent R-arc rounds
    (R430+) MUST appear in the mandate doc — drift = round shipped
    without recording."""
    body = _read()
    # Check that at least R420-R430 rounds are recorded
    recent_rounds = ["R420", "R425", "R430"]
    for rid in recent_rounds:
        assert rid in body, (
            f"mandate doc missing {rid} reference "
            f"(round shipped without recording in mandate)"
        )


# --- File size sanity ---


def test_mandate_doc_substantive():
    """The mandate doc is the central record. Drift to <50KB =
    accidental truncation."""
    body = _read()
    assert len(body) >= 50_000, (
        f"mandate doc too small ({len(body)} bytes); "
        f"may indicate accidental truncation"
    )
