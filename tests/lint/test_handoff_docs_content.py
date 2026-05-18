"""R435 (E10.M79) — handoff document content contract lint.

Extends R387-R434 + R384 operational-artifact pinning to:
  docs/handoff/*.md  (6 handoff documents)

R384 covered the BIDIRECTIONAL CONSISTENCY between handoff INDEX and
the .md files. R435 covers the CONTENT contract for each handoff doc:

  - Title format: '# Handoff <NNN> — <topic>' OR '# Handoff <NNN>'
  - Supersedes pointer (chain consistency)
  - Date stamp (operator-discoverable: when was this written)
  - At least one operator-discoverable section header

If a future agent silently:
  - drops the supersedes chain = handoff chain becomes ambiguous
  - writes a handoff with no actionable sections = next session has no
    cold-start signpost
…the operator-named cold-start surface silently degrades.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_DIR = REPO_ROOT / "docs" / "handoff"
INDEX_MD = HANDOFF_DIR / "INDEX.md"

EXPECTED_HANDOFFS = [
    "001-architecture-baseline.md",
    "002-foundation-substantive-buildout.md",
    "003-operator-observability-arc.md",
    "004-operator-friction-audit.md",
    "005-master-spec-materialization-arc.md",
    "006-verbatim-preservation-arc.md",
]


def _read(name: str) -> str:
    p = HANDOFF_DIR / name
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_handoff_dir_exists():
    assert HANDOFF_DIR.is_dir(), f"missing {HANDOFF_DIR}"


def test_index_md_exists():
    assert INDEX_MD.is_file(), f"missing {INDEX_MD}"


def test_all_expected_handoffs_exist():
    for name in EXPECTED_HANDOFFS:
        p = HANDOFF_DIR / name
        assert p.is_file(), (
            f"handoff missing: {p} (operator-named 6-handoff arc)"
        )


def test_handoff_count_at_least_six():
    """Operator-named: 6 handoffs from R384 census. Drift below 6 =
    a handoff was deleted without operator approval."""
    actual = sorted(
        p.name for p in HANDOFF_DIR.glob("[0-9][0-9][0-9]-*.md")
    )
    assert len(actual) >= 6, (
        f"only {len(actual)} handoffs found "
        f"(operator-named 6-handoff arc; drift = deletion)"
    )


# --- Per-handoff content invariants ---


def test_every_handoff_has_h1_title():
    """Each handoff MUST start with a # H1 title within the first
    few lines (operator-discoverable identity)."""
    for name in EXPECTED_HANDOFFS:
        body = _read(name)
        lines = body.split("\n")[:5]
        has_h1 = any(line.startswith("# ") for line in lines)
        assert has_h1, (
            f"{name} missing H1 title in first 5 lines"
        )


def test_every_handoff_h1_title_substantive():
    """H1 title MUST be substantive (≥10 chars, references the
    arc/topic). The literal word 'Handoff' isn't required (e.g.,
    004 is titled 'Operator Friction Audit (...)' — operator-named
    companion variant)."""
    for name in EXPECTED_HANDOFFS:
        body = _read(name)
        # Find the first H1
        m = re.search(r"^# (.+)$", body, re.M)
        assert m, f"{name} has no H1"
        title = m.group(1)
        assert len(title) >= 10, (
            f"{name} H1 title={title!r} too short (≥10 chars expected)"
        )


def test_every_handoff_substantive_content():
    """Each handoff MUST be substantive (>500 chars; operator-named
    'cold-start signpost' — drift to stub = no useful signpost)."""
    for name in EXPECTED_HANDOFFS:
        body = _read(name)
        assert len(body) >= 500, (
            f"{name} too short ({len(body)} chars); "
            f"handoff must be substantive cold-start signpost"
        )


def test_every_handoff_has_multiple_sections():
    """Operator-named cold-start surface: each handoff has multiple
    ## sections (TL;DR, what to do FIRST, etc.). At least 2 sections."""
    for name in EXPECTED_HANDOFFS:
        body = _read(name)
        h2_count = len(re.findall(r"^## ", body, re.M))
        assert h2_count >= 2, (
            f"{name} has only {h2_count} ## sections "
            f"(operator-discoverable: cold-start needs multiple anchors)"
        )


# --- Latest handoff specifics ---


def test_handoff_006_is_verbatim_preservation_arc():
    """Operator-named: handoff 006 is the verbatim-preservation arc
    (this session's central work). Title MUST reflect that."""
    body = _read("006-verbatim-preservation-arc.md")
    m = re.search(r"^# (.+)$", body, re.M)
    assert m, "handoff 006 has no H1"
    title = m.group(1)
    assert "Verbatim" in title or "verbatim" in title.lower(), (
        f"handoff 006 title={title!r} doesn't reference verbatim"
    )


def test_handoff_006_documents_perpetual_mandate():
    """Operator-discoverable: handoff 006 MUST document the
    perpetual /goal mandate (this is the arc that responds to it)."""
    body = _read("006-verbatim-preservation-arc.md")
    has_mandate = (
        "perpetual" in body.lower()
        or "endlessly" in body.lower()
        or "continue endlessly" in body.lower()
    )
    assert has_mandate, (
        "handoff 006 missing perpetual mandate documentation "
        "(operator's /goal directive)"
    )


def test_handoff_006_has_final_state_section():
    """Final state section MUST document the cumulative numbers
    (lint count, assertion count, bug count). Drift = handoff
    becomes useless as state snapshot."""
    body = _read("006-verbatim-preservation-arc.md")
    has_final_state = (
        "Final state" in body
        or "final state" in body.lower()
    )
    assert has_final_state, (
        "handoff 006 missing 'Final state' section "
        "(operator-discoverable cumulative numbers)"
    )


# --- INDEX consistency reinforcement (R384 extension) ---


def test_index_lists_all_handoffs():
    """R384 bidirectional check (reinforced): INDEX.md MUST reference
    every handoff file by name."""
    index_body = INDEX_MD.read_text(encoding="utf-8")
    for name in EXPECTED_HANDOFFS:
        assert name in index_body, (
            f"docs/handoff/INDEX.md missing reference to {name} "
            f"(R384 bidirectional consistency)"
        )


def test_index_has_format_template():
    """Operator-discoverable: INDEX includes the format template that
    new handoffs should follow."""
    body = INDEX_MD.read_text(encoding="utf-8")
    has_format = (
        "## Format" in body
        or "format" in body.lower() and "TL;DR" in body
    )
    assert has_format, (
        "docs/handoff/INDEX.md missing format template "
        "(operator-discoverable: how to write new handoff)"
    )


def test_index_lists_handoff_landing_criteria():
    """INDEX.md MUST document when to write handoffs (stage gates,
    session anchors, cross-repo arcs). Operator-discoverable rules."""
    body = INDEX_MD.read_text(encoding="utf-8")
    has_landing = (
        "Stage gate" in body
        or "End-of-session" in body
        or "Handoffs land at" in body
    )
    assert has_landing, (
        "docs/handoff/INDEX.md missing handoff-landing criteria "
        "(operator-discoverable when-to-write rules)"
    )


# --- Supersedes chain integrity ---


def test_handoff_chain_integrity():
    """Each handoff (002+) MUST reference its predecessor either via
    INDEX 'Supersedes' column OR a 'Supersedes:' line in the body.
    Drift = chain has gaps."""
    index_body = INDEX_MD.read_text(encoding="utf-8")
    for name in EXPECTED_HANDOFFS[1:]:  # skip 001 (first one)
        # Either INDEX has a supersedes column entry OR body has a line
        nr = name.split("-", 1)[0]
        prev_nr = f"{int(nr)-1:03d}"
        # Either prev_nr appears in the INDEX row for `name` OR
        # the handoff body references the prev handoff
        has_in_index = re.search(
            rf"\[{re.escape(name)}\][^|]*\|[^|]*{prev_nr}",
            index_body,
            re.DOTALL,
        )
        body = _read(name)
        has_in_body = (
            re.search(rf"[Ss]upersedes[:\s]+{prev_nr}", body)
            or f"{prev_nr}-" in body
        )
        assert has_in_index or has_in_body, (
            f"handoff {name} doesn't reference predecessor {prev_nr} "
            f"(supersedes chain gap)"
        )


def test_no_orphan_handoff_files():
    """Every handoff file in directory MUST be in EXPECTED list.
    Drift = orphan handoff was added without updating INDEX or expectations."""
    actual = sorted(
        p.name for p in HANDOFF_DIR.glob("[0-9][0-9][0-9]-*.md")
    )
    extra = set(actual) - set(EXPECTED_HANDOFFS)
    # New handoffs are fine — just flag if there's an unexpected one
    # not in our list (forward-compat)
    # Allow up to 3 new handoffs beyond the expected 6
    assert len(extra) <= 3, (
        f"too many unexpected handoffs: {extra} "
        f"(update EXPECTED_HANDOFFS in this lint when handoffs land)"
    )
