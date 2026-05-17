"""R336 (E9.M15) — SDD-034 snapshot doctrine L1 lint.

Pins the 6-script snapshot family contract from SDD-034: each
script declares SCHEMA_VERSION / ROUND / SDD_VECTOR constants
matching the doctrine table; producers declare expected round IDs;
the SDD carries required sections.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "034-snapshot-doctrine.md"


# (script_path, expected ROUND, expected SDD_VECTOR)
SNAPSHOT_FAMILY = [
    ("scripts/diagnostics/state-snapshot.py",         "R322", "E2.M18"),
    ("scripts/fleet/snapshot-aggregator.py",          "R324", "E2.M20"),
    ("scripts/diagnostics/config-snapshot.py",         "R332", "E2.M23"),
    ("scripts/diagnostics/config-restore.py",          "R333", "E2.M24"),
    ("scripts/diagnostics/snapshot-diff.py",           "R334", "E2.M25"),
    ("scripts/diagnostics/config-snapshot-diff.py",    "R335", "E2.M26"),
]


REQUIRED_SDD_SECTIONS = [
    "## Mission",
    "## The snapshot family — 6 scripts",
    "## Schema invariants",
    "## Producer-consumer contract",
    "## NEVER-raise contract",
    "## Round-mismatch enforcement",
    "## Schema-version evolution",
    "## L1 lint enforcement",
    "## What this SDD does NOT do",
    "## Future snapshot-family evolution",
]


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_sdd_034_exists():
    assert SDD_PATH.is_file(), f"missing {SDD_PATH}"


def test_sdd_034_has_required_sections():
    body = SDD_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SDD_SECTIONS if s not in body]
    assert not missing, (
        f"SDD-034 missing required sections: {missing}.\n"
        "If a section was deliberately renamed, update "
        "REQUIRED_SDD_SECTIONS in tests/lint/test_snapshot_doctrine.py "
        "in the same commit."
    )


def test_all_six_snapshot_scripts_present():
    for rel, _, _ in SNAPSHOT_FAMILY:
        path = REPO_ROOT / rel
        assert path.is_file(), f"missing snapshot family script: {path}"


def test_snapshot_scripts_declare_constants():
    """Each script declares SCHEMA_VERSION='1.0.0' + ROUND='R<N>' +
    SDD_VECTOR='E<n>.M<m>' constants matching the doctrine table."""
    for rel, expected_round, expected_vector in SNAPSHOT_FAMILY:
        body = _read(rel)
        assert body, f"empty body for {rel}"
        assert "SCHEMA_VERSION" in body, (
            f"{rel} missing SCHEMA_VERSION constant"
        )
        # Match `SCHEMA_VERSION = "1.0.0"` (whitespace tolerant)
        assert re.search(r'SCHEMA_VERSION\s*=\s*"1\.0\.0"', body), (
            f"{rel} SCHEMA_VERSION != '1.0.0' (per SDD-034)"
        )
        # Match `ROUND = "R<N>"`
        assert re.search(rf'ROUND\s*=\s*"{expected_round}"', body), (
            f"{rel} ROUND != '{expected_round}' (per SDD-034 family table)"
        )
        # Match `SDD_VECTOR = "<Epic.Module>"`
        # Escape '.' in the regex.
        escaped = expected_vector.replace(".", r"\.")
        assert re.search(rf'SDD_VECTOR\s*=\s*"{escaped}"', body), (
            f"{rel} SDD_VECTOR != '{expected_vector}' (per SDD-034)"
        )


def test_consumer_scripts_carry_round_mismatch_handling():
    """R333/R334 demand R322; R335 demands R332. Verify the
    round-mismatch string appears in each consumer."""
    consumers = {
        "scripts/diagnostics/config-restore.py": "R332",
        "scripts/diagnostics/snapshot-diff.py": "R322",
        "scripts/diagnostics/config-snapshot-diff.py": "R332",
    }
    for rel, expected_round in consumers.items():
        body = _read(rel)
        # Look for the "round mismatch" structural rejection.
        assert "round mismatch" in body.lower(), (
            f"{rel} must implement round mismatch detection"
        )
        # And it must reference the expected round it accepts.
        assert expected_round in body, (
            f"{rel} must accept rounds tagged {expected_round}"
        )


def test_sdd_034_cross_links_all_six_rounds():
    body = SDD_PATH.read_text(encoding="utf-8")
    for _, expected_round, _ in SNAPSHOT_FAMILY:
        assert expected_round in body, (
            f"SDD-034 must cross-ref {expected_round}"
        )


def test_sdd_034_documents_schema_version_evolution():
    body = SDD_PATH.read_text(encoding="utf-8")
    assert "schema_version" in body.lower(), (
        "SDD-034 must document schema_version field"
    )
    assert "semver" in body.lower() or "1.0.0" in body, (
        "SDD-034 must document schema versioning rules"
    )
