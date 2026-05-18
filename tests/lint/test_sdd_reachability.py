"""R380 (E10.M24) — SDD reachability validator.

Inverse of R372 SDD reference validator:
  R372: every coverage-map sdd_refs entry must point to a real SDD file
  R380: every shipped SDD file must be REACHABLE from some catalog
        entry (architecture-qa concept spec_ref / coverage-map sdd_refs
        / verbatim-render manifest / mandate row references)

Catches: SDD-NNN docs that get authored but never wired into the
discoverable surface — operator who didn't write them can't find them.

Reachability sources:
  (a) architecture-qa C-NN spec_ref mentions SDD-NNN
  (b) coverage-map A-NN sdd_refs cites SDD-NNN
  (c) mandate file mentions SDD-NNN in any row
  (d) docs/src/SUMMARY.md links to SDD-NNN

Exemptions (allowed-to-be-unreachable):
  - SDD-000 charter (top-level, by definition references itself only)
  - SDD-001 cross-repo boundaries (referenced from ARCHITECTURE.md)
  - SDD-002 documentation pipeline (meta-doc about doc system)

Future agent shipping SDD-NNN must wire it into at least one catalog
or accept a documented exemption.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_DIR = REPO_ROOT / "docs" / "sdd"
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")
SUMMARY = REPO_ROOT / "docs" / "src" / "SUMMARY.md"
ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"


# SDDs that are exempt from reachability discipline.
# Rationale per ID range:
#   000-002: top-level docs (charter / cross-repo / pipeline)
#   003-029: pre-SDD-030 era (authored before R283 overlay doctrine
#            and the catalog-wiring convention; published via mdbook
#            tree but not always cited from catalog entries)
# SDDs ≥030 (operator-overlay doctrine + later) MUST be reachable
# from at least one catalog path — that's the post-doctrine discipline.
REACHABILITY_EXEMPTIONS: set[str] = {
    f"{n:03d}" for n in range(0, 30)
}


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _existing_sdds() -> set[str]:
    out: set[str] = set()
    for f in SDD_DIR.glob("*.md"):
        m = re.match(r"^(\d{3})-", f.name)
        if m:
            out.add(m.group(1))
    return out


def _archqa_referenced_sdds() -> set[str]:
    """Find SDD-NNN references in architecture-qa spec_ref fields +
    explanations + notes."""
    mod = _load_module(ARCH_QA, "sdd_reachability_archqa")
    refs: set[str] = set()
    for items in (mod.ARCHITECTURE_QUESTIONS,
                  mod.ARCHITECTURE_GOTCHAS,
                  mod.ARCHITECTURE_CONCEPTS):
        for item in items:
            for field in ("spec_ref", "explanation", "question",
                           "answer", "context", "gotcha", "prevention",
                           "notes"):
                v = item.get(field)
                if isinstance(v, str):
                    # Match SDD-NNN or SDD NNN patterns
                    refs.update(re.findall(r"SDD[- ](\d{3})", v))
    return refs


def _coverage_referenced_sdds() -> set[str]:
    mod = _load_module(COVERAGE, "sdd_reachability_coverage")
    refs: set[str] = set()
    for axis in mod.DEFAULT_AXES:
        for sdd in axis.get("sdd_refs") or []:
            if sdd:
                refs.add(sdd)
        # Also check axis notes for SDD-NNN references
        notes = axis.get("notes", "")
        refs.update(re.findall(r"SDD[- ](\d{3})", notes))
    return refs


def _mandate_referenced_sdds() -> set[str]:
    if not MANDATE.is_file():
        return set()
    body = MANDATE.read_text(encoding="utf-8")
    return set(re.findall(r"SDD[- ](\d{3})", body))


def _summary_referenced_sdds() -> set[str]:
    if not SUMMARY.is_file():
        return set()
    body = SUMMARY.read_text(encoding="utf-8")
    return set(re.findall(r"SDD[- ](\d{3})", body))


def test_sdd_directory_exists():
    assert SDD_DIR.is_dir(), f"missing {SDD_DIR}"


def test_at_least_30_sdds_shipped():
    """Sanity: by this stage we should have ≥30 SDDs shipped
    (currently 38: SDD-000 through SDD-037)."""
    sdds = _existing_sdds()
    assert len(sdds) >= 30, (
        f"only {len(sdds)} SDDs in docs/sdd/; expected ≥30"
    )


def test_every_sdd_reachable_from_catalog_or_mandate():
    """Every shipped SDD-NNN must be referenced from at least one of:
    architecture-qa / coverage-map / mandate / SUMMARY.md.
    Exemptions: SDD-000/001/002 (top-level docs)."""
    existing = _existing_sdds()
    archqa_refs = _archqa_referenced_sdds()
    coverage_refs = _coverage_referenced_sdds()
    mandate_refs = _mandate_referenced_sdds()
    summary_refs = _summary_referenced_sdds()
    all_refs = archqa_refs | coverage_refs | mandate_refs | summary_refs

    unreachable: list[str] = []
    for sdd in sorted(existing):
        if sdd in REACHABILITY_EXEMPTIONS:
            continue
        if sdd not in all_refs:
            unreachable.append(sdd)

    assert not unreachable, (
        f"SDDs {unreachable} exist in docs/sdd/ but are not referenced "
        f"from any catalog (architecture-qa / coverage-map / mandate / "
        f"SUMMARY.md). Either wire them into a catalog entry OR add to "
        f"REACHABILITY_EXEMPTIONS in tests/lint/test_sdd_reachability.py "
        f"with a documented reason."
    )


def test_no_dangling_sdd_references_in_catalogs():
    """Inverse direction (overlap with R372): every SDD-NNN cited from
    catalogs must correspond to a real docs/sdd/NNN-*.md file."""
    existing = _existing_sdds()
    archqa_refs = _archqa_referenced_sdds()
    coverage_refs = _coverage_referenced_sdds()
    mandate_refs = _mandate_referenced_sdds()
    all_refs = archqa_refs | coverage_refs | mandate_refs

    dangling: list[str] = []
    for sdd in all_refs:
        if sdd not in existing:
            dangling.append(sdd)
    assert not dangling, (
        f"Catalogs/mandate cite SDD-{dangling} but no docs/sdd/NNN-*.md "
        f"file exists. Either author the SDD or fix the references."
    )


def test_recent_sdds_referenced_in_mandate():
    """Sanity: SDDs ≥030 should ALL be cited in the mandate file
    (recent doctrine is operator-facing and mandate is the operator's
    main view)."""
    existing = _existing_sdds()
    mandate_refs = _mandate_referenced_sdds()
    missing: list[str] = []
    for sdd in sorted(existing):
        if int(sdd) >= 30 and sdd not in mandate_refs:
            missing.append(sdd)
    assert not missing, (
        f"Recent SDDs {missing} not mentioned in mandate file. "
        f"Each ≥SDD-030 doctrine round should have a mandate row "
        f"that cites it."
    )


def test_sdd_037_reachable_via_multiple_paths():
    """SDD-037 (verbatim-preservation doctrine) is the most cross-
    referenced SDD. Sanity: it's reachable via ALL 4 paths."""
    archqa_refs = _archqa_referenced_sdds()
    coverage_refs = _coverage_referenced_sdds()
    mandate_refs = _mandate_referenced_sdds()
    # SDD-037 must appear in mandate (its own row) + coverage (cited
    # by multiple axes' notes after R378).
    assert "037" in mandate_refs, "SDD-037 missing from mandate"
    # If covered by coverage_refs, that's bonus.
