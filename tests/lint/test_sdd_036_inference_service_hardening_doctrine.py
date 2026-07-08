"""SDD-036 inference-service-hardening-doctrine L1 lint.

Pins SDD-036's doctrinal claims so future edits don't silently drop
the 4-service set, the two harder-posture directive names, or the
inline-comment waiver pattern.

The R171 baseline (10 directives) is enforced elsewhere. SDD-036 is
the STRICTER overlay specifying that the 4 inference services
(`sovereign-pulse`, `sovereign-logic-engine`, `sovereign-oracle-core`,
`sovereign-router`) carry `MemoryDenyWriteExecute` and
`RestrictAddressFamilies` on top of the baseline. Silent rewording
of the doctrine would let lint drift without warning.

Cousin pattern to test_sdd_033_perpetual_intake_doctrine.py +
test_sdd_040_cockpit_dashboard_bridge.py.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "036-inference-service-hardening-doctrine.md"

REQUIRED_SECTIONS = [
    "## Mission",
    "## The contract — every inference service MUST",
    "## Current shipped posture",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future-quarter hardening extensions",
    "## Doctrine evolution",
]

# The 4 inference services SDD-036 names. If a 5th inference service
# lands, doctrine should name it explicitly — the lint catches the
# inconsistency.
INFERENCE_SERVICES = [
    "sovereign-pulse",
    "sovereign-logic-engine",
    "sovereign-oracle-core",
    "sovereign-router",
]

# The two harder-posture systemd directives this SDD adds on top of
# R171's 10-key baseline. Renaming/dropping either dissolves the
# contract; the lint catches that.
HARDER_POSTURE_DIRECTIVES = [
    "MemoryDenyWriteExecute",
    "RestrictAddressFamilies",
]


def test_sdd_036_exists():
    """SDD-036 file must be present."""
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_036_has_required_sections():
    """All declared section headers must appear."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-036 missing required sections: {missing}.\n"
        "If you renamed a section deliberately, update REQUIRED_SECTIONS "
        "in this lint in the same commit (forces conscious doctrine "
        "evolution)."
    )


def test_sdd_036_sections_in_order():
    """Required sections must appear in declaration order."""
    body = SDD_PATH.read_text(encoding="utf-8")
    positions = [(s, body.index(s)) for s in REQUIRED_SECTIONS if s in body]
    actual_order = [s for s, _ in sorted(positions, key=lambda x: x[1])]
    assert actual_order == REQUIRED_SECTIONS, (
        f"SDD-036 sections out of order:\n"
        f"  expected: {REQUIRED_SECTIONS}\n"
        f"  actual:   {actual_order}"
    )


def test_sdd_036_names_all_4_inference_services():
    """All 4 named inference services must appear in the doctrine."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in INFERENCE_SERVICES if s not in body]
    assert not missing, (
        f"SDD-036 missing inference services: {missing}.\n"
        "The contract names exactly 4 inference services; dropping one "
        "would silently exempt it from the stricter posture."
    )


def test_sdd_036_names_harder_posture_directives():
    """Both stricter-posture directive names must appear."""
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [d for d in HARDER_POSTURE_DIRECTIVES if d not in body]
    assert not missing, (
        f"SDD-036 missing harder-posture directives: {missing}.\n"
        "The contract REQUIRES both MemoryDenyWriteExecute AND "
        "RestrictAddressFamilies on top of R171 baseline."
    )


def test_sdd_036_documents_inline_comment_waiver():
    """The inline `#`-comment waiver pattern must be documented so the
    lint's tolerance matches the doctrine."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "inline" in body.lower() and "comment" in body.lower(), (
        "SDD-036 must document the inline-comment waiver pattern "
        "(consistent with `RestrictNamespaces=false  # podman` convention)"
    )


def test_sdd_036_names_inference_services_constant():
    """The lint constant name `INFERENCE_SERVICES` must be referenced
    so doctrine and lint stay aligned."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "INFERENCE_SERVICES" in body, (
        "SDD-036 must reference the INFERENCE_SERVICES lint constant"
    )


def test_sdd_036_anchors_r171_baseline():
    """R171 baseline anchor must appear (this SDD is the STRICTER
    overlay; without the baseline reference the relationship is lost)."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "R171" in body, (
        "SDD-036 must anchor itself against R171 baseline doctrine"
    )


def test_sdd_036_documents_codegen_waiver_example():
    """The vLLM/Triton JIT-compile waiver example must be present so
    operators know the operator-rationale convention."""
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "vLLM" in body or "Triton" in body or "JIT" in body, (
        "SDD-036 must show the codegen-needing-waiver example "
        "(vLLM/Triton JIT-compile)"
    )


def test_sdd_036_listed_in_index():
    """SDD-036 row must appear in docs/sdd/INDEX.md."""
    index_path = REPO_ROOT / "docs" / "sdd" / "INDEX.md"
    if not index_path.is_file():
        return
    index_body = index_path.read_text(encoding="utf-8")
    assert "036" in index_body, "SDD-036 must be listed in docs/sdd/INDEX.md"
