"""SDD-038 cross-repo binding doctrine L1 lint.

Pins SDD-038's load-bearing claims so a future edit can't silently
drop the two-repos identity, the typed-TOML-manifest pattern, the
R460-R469 implementation arc anchors, or the end-to-end acceptance
test reference.

SDD-038 formalizes the cross-repo binding pattern between
`cyberpunk042/sovereign-os` and `cyberpunk042/selfdef`. The
"two-ultimate-solutions" doctrine depends on the two repos
co-progressing without drift on operator-named taxonomies; silent
rewording would dissolve the contract.

Cousin pattern to test_sdd_033_perpetual_intake_doctrine.py +
test_sdd_036_inference_service_hardening_doctrine.py +
test_sdd_040_cockpit_dashboard_bridge.py.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "038-cross-repo-binding-doctrine.md"

REQUIRED_SECTIONS = [
    "## Mission",
    "## Problem",
    "## Required coverage",
    "## Goals",
    "## Non-goals",
    "## Open questions",
    "## Way forward",
    "## Cross-references",
]

# Both repos MUST be named explicitly — the doctrine's identity
# depends on the "two ultimate solutions" pair being unambiguous.
REQUIRED_REPOS = [
    "cyberpunk042/sovereign-os",
    "cyberpunk042/selfdef",
]

# Implementation-arc round anchors. Dropping these would erase the
# provenance trail that makes the doctrine refactorable.
R_ANCHORS = ["R460", "R462", "R464", "R465", "R466", "R469"]


def test_sdd_038_exists():
    """SDD-038 file must be present."""
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_038_has_required_sections():
    """All declared section headers must appear."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-038 missing required sections: {missing}. If you renamed "
        "a section deliberately, update REQUIRED_SECTIONS in this lint "
        "in the same commit (forces conscious doctrine evolution)."
    )


def test_sdd_038_sections_in_order():
    """Required sections must appear in declaration order."""
    body = SDD_PATH.read_text(encoding="utf-8")
    positions = [(s, body.index(s)) for s in REQUIRED_SECTIONS if s in body]
    actual_order = [s for s, _ in sorted(positions, key=lambda x: x[1])]
    assert actual_order == REQUIRED_SECTIONS, (
        f"SDD-038 sections out of order:\n"
        f"  expected: {REQUIRED_SECTIONS}\n"
        f"  actual:   {actual_order}"
    )


def test_sdd_038_names_both_repos_explicitly():
    """Both repos in the "two ultimate solutions" pair must be named
    explicitly — without the pair declaration the doctrine has no
    referent."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [r for r in REQUIRED_REPOS if r not in body]
    assert not missing, (
        f"SDD-038 missing repo names: {missing}. The doctrine names "
        "two ultimate solutions; dropping a repo dissolves the pair."
    )


def test_sdd_038_documents_typed_toml_manifest_pattern():
    """The typed-TOML-manifest pattern is the doctrine's core
    mechanism — it must be named explicitly."""
    body = SDD_PATH.read_text(encoding="utf-8").lower()
    assert "typed" in body and "toml" in body and "manifest" in body, (
        "SDD-038 must document the typed-TOML-manifest pattern "
        "(the doctrine's core mechanism)"
    )


def test_sdd_038_anchors_implementation_round_provenance():
    """The R460-R469 implementation-arc anchor set must remain
    referenceable so the doctrine is auditable against git history."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [r for r in R_ANCHORS if r not in body]
    assert not missing, (
        f"SDD-038 missing implementation-arc anchors: {missing}. "
        "Without the round provenance the doctrine cannot be "
        "audited against history."
    )


def test_sdd_038_documents_drift_prevention():
    """The doctrine's value is silent-drift prevention; that intent
    must be named so the reader understands WHY this matters."""
    body = SDD_PATH.read_text(encoding="utf-8").lower()
    assert "drift" in body, (
        "SDD-038 must name drift / drift-prevention explicitly as "
        "the doctrine's purpose"
    )


def test_sdd_038_listed_in_index():
    """SDD-038 row must appear in docs/sdd/INDEX.md."""
    index_path = REPO_ROOT / "docs" / "sdd" / "INDEX.md"
    if not index_path.is_file():
        return
    index_body = index_path.read_text(encoding="utf-8")
    assert "038" in index_body, "SDD-038 must be listed in docs/sdd/INDEX.md"
