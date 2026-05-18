"""R372 (E10.M16) — verb-dispatch + SDD reference validator.

Extends R368 + R371 cross-reference fabrication catches:

(a) Every `sovereign-osctl <subverb>` referenced in coverage-map
    A-NN axes (implementing_verbs) AND architecture-qa gotchas
    (related_verbs) AND repl modes (reference_commands) MUST have
    a corresponding `case` dispatch in `scripts/sovereign-osctl`.

(b) Every `sdd_refs: ["NNN"]` cited in coverage-map axes MUST
    correspond to a real `docs/sdd/NNN-*.md` file.

R368 checked the verb prefix is `sovereign-osctl `. R372 closes
the gap: the subverb after the prefix must dispatch.

Catches:
  - axis cites `sovereign-osctl placeholder` (placeholder never wired)
  - axis cites `sovereign-osctl autohelath` (typo)
  - axis cites SDD reference 099 that doesn't exist
  - axis cites SDD 011 but docs/sdd/011-*.md was renamed/deleted
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"
ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"
REPL = REPO_ROOT / "scripts" / "intelligence" / "repl.py"
SDD_DIR = REPO_ROOT / "docs" / "sdd"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _extract_dispatched_subverbs() -> set[str]:
    """Parse scripts/sovereign-osctl for `<subverb>)` case lines.
    Returns set of dispatched subverb names."""
    body = OSCTL.read_text(encoding="utf-8")
    # Match patterns like `  somesubverb)` at start of indentation
    # in case statements. The osctl script uses 2-space indent for
    # case branches.
    # Robust: find lines matching `^  <word>(-<word>)*)` (case branch)
    # OR `^    <word>(-<word>)*\|.*)` (multi-pattern case branch).
    subverbs: set[str] = set()
    # Look at top-level case dispatch (2-space indent + identifier + ')')
    for line in body.splitlines():
        m = re.match(r"^  ([a-z][\w-]*)\)", line)
        if m:
            subverbs.add(m.group(1))
        # Also multi-pattern cases: "  verb1|verb2|verb3)"
        m2 = re.match(r"^  ([a-z][\w|-]+)\)", line)
        if m2:
            for v in m2.group(1).split("|"):
                v = v.strip()
                if v:
                    subverbs.add(v)
    return subverbs


def _extract_verb_subverb(verb_string: str) -> str | None:
    """From 'sovereign-osctl autohealth tick' extract 'autohealth'.
    Returns None for non-sovereign-osctl strings."""
    m = re.match(r"^sovereign-osctl\s+([a-z][\w-]*)", verb_string)
    return m.group(1) if m else None


def _extract_existing_sdd_numbers() -> set[str]:
    """Parse docs/sdd/ for NNN-*.md filenames."""
    out: set[str] = set()
    for f in SDD_DIR.glob("*.md"):
        m = re.match(r"^(\d{3})-", f.name)
        if m:
            out.add(m.group(1))
    return out


def test_osctl_script_exists():
    assert OSCTL.is_file(), f"missing {OSCTL}"


def test_osctl_has_minimum_subverbs():
    """Sanity: osctl should dispatch ≥50 subverbs by this point."""
    subverbs = _extract_dispatched_subverbs()
    assert len(subverbs) >= 50, (
        f"osctl dispatches only {len(subverbs)} subverbs — expected ≥50. "
        f"Either parser is broken OR osctl got truncated."
    )


def test_coverage_axis_verbs_dispatch_in_osctl():
    """Every sovereign-osctl <subverb> in coverage-map implementing_verbs
    MUST have a dispatch case in scripts/sovereign-osctl."""
    mod = _load_module(COVERAGE, "coverage_verb_dispatch_lint")
    dispatched = _extract_dispatched_subverbs()
    for axis in mod.DEFAULT_AXES:
        for verb in axis.get("implementing_verbs") or []:
            sub = _extract_verb_subverb(verb)
            if sub is None:
                continue
            assert sub in dispatched, (
                f"axis {axis.get('id', '?')} cites verb "
                f"`sovereign-osctl {sub}` but {sub!r} has NO dispatch "
                f"case in scripts/sovereign-osctl. Either the verb was "
                f"renamed/deleted OR this is a fabricated reference. "
                f"Add the dispatch case OR fix the reference."
            )


def test_architecture_qa_gotcha_verbs_dispatch_in_osctl():
    """Every sovereign-osctl <subverb> in architecture-qa gotchas
    `related_verbs` MUST dispatch."""
    mod = _load_module(ARCH_QA, "archqa_gotcha_verb_dispatch_lint")
    dispatched = _extract_dispatched_subverbs()
    for gotcha in mod.ARCHITECTURE_GOTCHAS:
        for verb in gotcha.get("related_verbs") or []:
            sub = _extract_verb_subverb(verb)
            if sub is None:
                continue
            assert sub in dispatched, (
                f"gotcha {gotcha.get('id', '?')} cites verb "
                f"`sovereign-osctl {sub}` which doesn't dispatch."
            )


def test_repl_reference_command_verbs_dispatch_in_osctl():
    """Every sovereign-osctl <subverb> in repl reference_commands
    MUST dispatch. Catches: a repl mode reference command pointing
    to a stale/renamed verb."""
    mod = _load_module(REPL, "repl_verb_dispatch_lint")
    dispatched = _extract_dispatched_subverbs()
    for mode in mod.DEFAULT_MODES:
        for cmd in mode.get("reference_commands") or []:
            # Strip arguments after the subverb
            sub = _extract_verb_subverb(cmd)
            if sub is None:
                continue
            assert sub in dispatched, (
                f"repl mode {mode.get('mode', '?')} reference_command "
                f"cites verb `sovereign-osctl {sub}` which doesn't "
                f"dispatch. Either rename the verb OR fix the reference."
            )


def test_coverage_axis_sdd_refs_exist():
    """Every sdd_refs entry on coverage-map axes MUST correspond to a
    real docs/sdd/NNN-*.md file."""
    mod = _load_module(COVERAGE, "coverage_sdd_refs_lint")
    existing = _extract_existing_sdd_numbers()
    for axis in mod.DEFAULT_AXES:
        for sdd in axis.get("sdd_refs") or []:
            if not sdd:
                continue
            assert sdd in existing, (
                f"axis {axis.get('id', '?')} cites sdd_refs entry "
                f"{sdd!r} but no docs/sdd/{sdd}-*.md file exists. "
                f"Either the SDD got renamed OR this is fabricated."
            )


def test_sdd_directory_has_canonical_files():
    """Sanity: SDD directory should have SDD-000 through SDD-037 by
    this stage. If files got deleted/renamed unexpectedly, this catches
    it."""
    existing = _extract_existing_sdd_numbers()
    for must in ("000", "001", "030", "032", "035", "037"):
        assert must in existing, (
            f"expected SDD-{must} to exist in docs/sdd/ but it doesn't. "
            f"Existing SDDs: {sorted(existing)}"
        )


def test_no_duplicate_dispatched_subverbs_in_osctl():
    """A subverb should dispatch from ONE case branch. Duplicate
    dispatch silently picks the FIRST branch + shadows the rest."""
    body = OSCTL.read_text(encoding="utf-8")
    # Find each `<subverb>)` line
    all_subverbs = []
    for line in body.splitlines():
        m = re.match(r"^  ([a-z][\w-]*)\)", line)
        if m:
            all_subverbs.append(m.group(1))
    duplicates = sorted({v for v in all_subverbs if all_subverbs.count(v) > 1})
    assert not duplicates, (
        f"osctl has duplicate dispatch cases: {duplicates}. Each "
        f"subverb must dispatch from exactly one case branch."
    )
