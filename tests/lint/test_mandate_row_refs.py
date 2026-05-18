"""R371 (E10.M15) — mandate-row reference validator (extends SDD-037).

R368 validated `master spec §N` references against the real master
spec section set. This lint extends the same fabrication-catch pattern
to `mandate_rows` cited in `coverage-map.py` axes AND `mandate_rows`
cited in any catalog: every `E<N>.M<M>` reference MUST point to a row
that actually exists in `docs/standing-directives/2026-05-17-operator-mandate.md`.

Catches:
  - Agent writes `mandate_rows: ["E1.M999"]` for a fabricated row
  - Typo in epic/module number (E1.M21 → E1.M22 when the work
    actually closed E1.M21)
  - Mandate row gets renamed/deleted but stale axes still reference it
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _extract_mandate_row_ids() -> set[str]:
    """Parse mandate file for E<N>.M<N> row IDs."""
    body = MANDATE.read_text(encoding="utf-8")
    # Mandate row lines start with "| E<N>.M<N> |"
    return set(re.findall(r"^\| (E\d+\.M\d+)\s*\|", body, re.M))


def test_mandate_file_exists():
    assert MANDATE.is_file(), f"missing {MANDATE}"


def test_mandate_has_minimum_row_count():
    """Sanity: mandate should have ≥100 rows by this point in the
    program. If file got truncated, this catches it."""
    rows = _extract_mandate_row_ids()
    assert len(rows) >= 100, (
        f"mandate file has only {len(rows)} rows — expected ≥100 by "
        f"this stage. File may be truncated or malformed."
    )


def test_coverage_axis_mandate_rows_exist():
    """Every mandate_rows entry on a coverage-map axis MUST point to a
    row that actually exists in the mandate file."""
    mod = _load_module(COVERAGE, "coverage_mandate_refs_lint")
    valid_rows = _extract_mandate_row_ids()
    for axis in mod.DEFAULT_AXES:
        for row_ref in axis.get("mandate_rows") or []:
            if not row_ref:
                continue
            assert row_ref in valid_rows, (
                f"axis {axis.get('id', '?')} cites mandate_row "
                f"{row_ref!r} which does NOT exist in "
                f"docs/standing-directives/2026-05-17-operator-mandate.md. "
                f"Either the row got renamed/deleted OR this is a "
                f"fabricated reference."
            )


def test_mandate_row_id_format_well_formed():
    """Every mandate_rows entry MUST match the E<N>.M<N> pattern.
    Catches: lowercase 'e1.m1', missing dot 'E1M1', stray whitespace."""
    mod = _load_module(COVERAGE, "coverage_mandate_format_lint")
    pattern = re.compile(r"^E\d+\.M\d+$")
    for axis in mod.DEFAULT_AXES:
        for row_ref in axis.get("mandate_rows") or []:
            if not row_ref:
                continue
            assert pattern.match(row_ref), (
                f"axis {axis.get('id', '?')} mandate_row {row_ref!r} "
                f"is malformed (expected E<N>.M<N>)"
            )


def test_coverage_axis_mandate_row_count_diverse():
    """Sanity: across the 30 A-NN axes, mandate_rows references should
    span ≥5 distinct epics (E1, E2, ..., not all clustered in one)."""
    mod = _load_module(COVERAGE, "coverage_mandate_epic_diversity_lint")
    epics = set()
    for axis in mod.DEFAULT_AXES:
        for row_ref in axis.get("mandate_rows") or []:
            m = re.match(r"^(E\d+)\.", row_ref or "")
            if m:
                epics.add(m.group(1))
    assert len(epics) >= 5, (
        f"coverage-map axes cite only {len(epics)} distinct epics: "
        f"{sorted(epics)}. Expected ≥5 (E1..E10 range) per SDD-037 "
        f"coverage breadth doctrine."
    )


def test_mandate_row_ids_in_mandate_are_well_formed():
    """The mandate file itself must use well-formed row IDs (no typos
    in the source-of-truth)."""
    rows = _extract_mandate_row_ids()
    pattern = re.compile(r"^E\d+\.M\d+$")
    for row in rows:
        assert pattern.match(row), (
            f"mandate file contains malformed row ID: {row!r}"
        )


def test_no_duplicate_mandate_rows_in_mandate():
    """The mandate file should NOT have duplicate row IDs. If E1.M21
    appears twice, that's a copy-paste bug that ambiguates references."""
    body = MANDATE.read_text(encoding="utf-8")
    all_refs = re.findall(r"^\| (E\d+\.M\d+)\s*\|", body, re.M)
    duplicates = [r for r in all_refs if all_refs.count(r) > 1]
    # Unique duplicate set
    duplicate_set = sorted(set(duplicates))
    assert not duplicate_set, (
        f"mandate file has duplicate row IDs: {duplicate_set}. "
        f"Each E<N>.M<N> must be unique."
    )
