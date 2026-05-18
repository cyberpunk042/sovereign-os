"""R368 (E10.M12) — SDD-037 spec_ref format lint.

Extends R367 SDD-037 doctrine enforcement: every architecture-qa item's
spec_ref MUST match one of the known operator-citation patterns. Catches
agents fabricating non-existent section refs (e.g. "master spec §99" or
"master spec ¶mystery") at push-time.

Recognized patterns (operator-verbatim citation forms):
  - "master spec §<N>"                              (§1..§23)
  - "master spec §<N>.<M>"                          (§1.1, §1.2, §3.2, etc)
  - "master spec §<N> + §<N>"                       (combined section refs)
  - "master spec §<N> + §<M>.<K>"                   (mixed forms)
  - "master spec Block <N>"                         (Block 6 Trinity Genesis)
  - "master spec Block <N> §..."                    (Block 6 + nested ref)
  - "master spec dump-tail ..."                     (post-Block 7 additions)
  - "macro-arc plan dump <date> ..."                (post-Plan refinements)
  - "operator overlay <date>"                       (overlay-extension entries)
  - "/goal directive <date>"                        (goal-contract entries)
  - "<round>-pattern" / "shipped via R<N>"          (cross-round refs)

The catalog of valid §N section numbers comes from the actual master
spec sections that exist in the raw dump (§1 through §23 + Block 6).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"


# Master spec section numbers operator actually cited in the raw dump.
# Range: §1..§23 + the "Block N" subdivision + "Modules N" within blocks.
VALID_MASTER_SPEC_SECTIONS = set(
    [str(n) for n in range(1, 24)]
    + [f"{n}.{m}" for n in range(1, 24) for m in range(1, 6)]
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Regex patterns matching operator-citation forms (one MUST match).
# Order matters: most-specific first.
SPEC_REF_PATTERNS = [
    # "master spec §N + §M ..." or "master spec §N + §M.K ..."
    re.compile(r"^master spec §[\d.]+(?:\s*\+\s*§[\d.]+)*"),
    # "master spec Block N §... verbatim"
    re.compile(r"^master spec Block \d+ §[\w/\d.]+"),
    # "master spec Block N ..."
    re.compile(r"^master spec Block \d+"),
    # "master spec §N.M verbatim ..."
    re.compile(r"^master spec §[\d.]+"),
    # "master spec dump-tail ..."
    re.compile(r"^master spec dump-tail"),
    # "macro-arc plan dump <date> ..."
    re.compile(r"^macro-arc plan dump \d{4}-\d{2}-\d{2}"),
    # "operator overlay <date>"
    re.compile(r"^operator overlay \d{4}-\d{2}-\d{2}"),
    # "/goal directive <date>"
    re.compile(r"^/goal directive \d{4}-\d{2}-\d{2}"),
    # "overlay test <date>" (for L3 test fixtures)
    re.compile(r"^overlay( test)?"),
    # "shipped via R<N>" (cross-round refs)
    re.compile(r"^shipped via R\d+"),
    # "test"  (operator-overlay test fixtures)
    re.compile(r"^test( .*)?$"),
]


def _matches_any_pattern(spec_ref: str) -> bool:
    return any(p.match(spec_ref) for p in SPEC_REF_PATTERNS)


def _extract_section_numbers(spec_ref: str) -> list[str]:
    """Extract §N or §N.M references from a spec_ref string."""
    return re.findall(r"§([\d.]+)", spec_ref)


def test_all_architecture_qa_spec_refs_match_known_format():
    """Every Q-NN / G-NN / C-NN spec_ref MUST match one of the
    recognized operator-citation patterns."""
    mod = _load_module(ARCH_QA, "architecture_qa_spec_ref_lint")
    for kind, items, prefix in (
        ("question", mod.ARCHITECTURE_QUESTIONS, "Q"),
        ("gotcha", mod.ARCHITECTURE_GOTCHAS, "G"),
        ("concept", mod.ARCHITECTURE_CONCEPTS, "C"),
    ):
        for item in items:
            sr = item.get("spec_ref", "")
            assert _matches_any_pattern(sr), (
                f"{prefix}-NN item {item.get('id', '?')} has spec_ref "
                f"that does NOT match any known operator-citation pattern: "
                f"{sr!r}. Known patterns are documented in "
                f"tests/lint/test_verbatim_spec_ref_format.py "
                f"SPEC_REF_PATTERNS. If you're adding a new citation form, "
                f"add the pattern to that list in the SAME commit."
            )


def test_master_spec_section_numbers_valid():
    """Every §N citation in spec_ref MUST point to a section number
    that exists in the master spec (§1..§23 + §N.M for first-level
    subsections). Catches fabricated section refs like §99."""
    mod = _load_module(ARCH_QA, "architecture_qa_section_lint")
    for items, prefix in (
        (mod.ARCHITECTURE_QUESTIONS, "Q"),
        (mod.ARCHITECTURE_GOTCHAS, "G"),
        (mod.ARCHITECTURE_CONCEPTS, "C"),
    ):
        for item in items:
            sr = item.get("spec_ref", "")
            # Only check items that cite master spec sections (skip
            # dump-tail / macro-arc / overlay / test refs).
            if "master spec §" not in sr:
                continue
            sections = _extract_section_numbers(sr)
            for sec in sections:
                assert sec in VALID_MASTER_SPEC_SECTIONS, (
                    f"item {item.get('id', '?')} cites master spec §{sec} "
                    f"which is NOT in the valid section set "
                    f"(§1..§23 + §N.M). Either operator extended the "
                    f"master spec (update VALID_MASTER_SPEC_SECTIONS) "
                    f"OR this is a fabricated section ref."
                )


def test_master_spec_section_distribution_diverse():
    """Sanity check: the concept catalog should cite ≥10 distinct
    master spec sections (proves coverage breadth, not just depth on
    one section)."""
    mod = _load_module(ARCH_QA, "architecture_qa_diverse_lint")
    cited_sections = set()
    for item in mod.ARCHITECTURE_CONCEPTS:
        sr = item.get("spec_ref", "")
        for sec in _extract_section_numbers(sr):
            # Normalize to top-level (§7.1 + §7.2 both count as §7)
            top = sec.split(".")[0]
            cited_sections.add(top)
    assert len(cited_sections) >= 10, (
        f"concept catalog cites only {len(cited_sections)} distinct master "
        f"spec sections (top-level): {sorted(cited_sections)}. "
        f"SDD-037 doctrine expects broad coverage — extend with more "
        f"verbatim concepts from un-cited sections."
    )


def test_no_fabricated_section_ref_in_examples():
    """Sanity: §99 + §1000 + §-1 must NOT pass the section validator
    (catches if VALID_MASTER_SPEC_SECTIONS is accidentally widened)."""
    assert "99" not in VALID_MASTER_SPEC_SECTIONS
    assert "1000" not in VALID_MASTER_SPEC_SECTIONS
    assert "-1" not in VALID_MASTER_SPEC_SECTIONS


def test_concept_spec_ref_count_matches_id_count():
    """Every concept has exactly one spec_ref (no array forms slipping
    in that the lint would miss)."""
    mod = _load_module(ARCH_QA, "architecture_qa_count_lint")
    for c in mod.ARCHITECTURE_CONCEPTS:
        sr = c.get("spec_ref")
        assert isinstance(sr, str), (
            f"concept {c.get('id')} spec_ref is not a string: {type(sr).__name__}"
        )


# ── Coverage-map source-field validation (mirrors spec_ref logic) ──
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"

COVERAGE_SOURCE_PATTERNS = [
    # "hook drop <date>" / "hook drop <date> (...)"
    re.compile(r"^hook drop \d{4}-\d{2}-\d{2}"),
    # "/goal directive <date>"
    re.compile(r"^/goal directive \d{4}-\d{2}-\d{2}"),
    # "mandate row E<N>.M<N>"
    re.compile(r"^mandate row E\d+\.M\d+"),
    # "raw dump §..."
    re.compile(r"^raw dump "),
    # "macro-arc plan dump <date>"
    re.compile(r"^macro-arc plan dump \d{4}-\d{2}-\d{2}"),
    # Test fixtures
    re.compile(r"^test$"),
]


def test_coverage_map_sources_match_known_format():
    """Every axis source field MUST match one of the recognized
    operator-origin patterns."""
    mod = _load_module(COVERAGE, "coverage_source_lint")
    for axis in mod.DEFAULT_AXES:
        src = axis.get("source", "")
        assert any(p.match(src) for p in COVERAGE_SOURCE_PATTERNS), (
            f"axis {axis.get('id', '?')} has source that does NOT match "
            f"any known origin pattern: {src!r}. Add the new pattern to "
            f"COVERAGE_SOURCE_PATTERNS in the SAME commit if operator "
            f"introduced a new origin form."
        )


def test_coverage_map_implementing_verbs_use_real_command_prefix():
    """Implementing verbs MUST start with 'sovereign-osctl ' (catches
    placeholder verbs / typos that wouldn't actually dispatch). Allowed
    exceptions: documentation pointers '#' prefix or 'systemctl '
    (system-level commands)."""
    mod = _load_module(COVERAGE, "coverage_verb_lint")
    valid_prefixes = ("sovereign-osctl ", "systemctl ", "# ")
    for axis in mod.DEFAULT_AXES:
        for verb in axis.get("implementing_verbs") or []:
            assert any(verb.startswith(p) for p in valid_prefixes), (
                f"axis {axis.get('id', '?')} implementing_verb does NOT "
                f"start with a valid prefix: {verb!r}. Allowed prefixes: "
                f"{valid_prefixes}"
            )
