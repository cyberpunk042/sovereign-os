"""R389 (E10.M33) — bootstrap YAML operator-verbatim content lint.

Extends R387/R388 operational-artifact pinning pattern to:
  - `config/bootstrap/verify-grid.yaml` — master spec §22 6-check
    verification grid (operator-verbatim check names + thresholds)
  - `config/bootstrap/phases.yaml` — master spec §12 5-phase
    chronological pipeline (operator-verbatim Phase I-V names)

Existing R207/R203 lints check schema validity. R389 pins operator-
VERBATIM content. Silent drift would mean: agent renames Phase II
or removes the §22 ARC check, the bootstrap pipeline executes
content that no longer matches operator's master spec.
"""
from __future__ import annotations

from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_GRID = REPO_ROOT / "config" / "bootstrap" / "verify-grid.yaml"
PHASES = REPO_ROOT / "config" / "bootstrap" / "phases.yaml"


def _read_yaml(path: Path) -> dict:
    if yaml is None or not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_verify_grid_file_exists():
    assert VERIFY_GRID.is_file(), f"missing {VERIFY_GRID}"


def test_phases_file_exists():
    assert PHASES.is_file(), f"missing {PHASES}"


def test_verify_grid_has_6_checks_per_master_spec_22():
    """Master spec §22 specifies exactly 6 bootstrap checks. The
    verify-grid catalog MUST list all 6 (no more, no less)."""
    doc = _read_yaml(VERIFY_GRID)
    grid = doc.get("verify_grid", {})
    checks = grid.get("checks", [])
    assert len(checks) == 6, (
        f"§22 verify-grid MUST have exactly 6 checks; found {len(checks)}. "
        f"Master spec §22 specifies a 6-row 'Master Bootstrap Verification "
        f"Checklist' — any deviation is silent operator-intent drift."
    )


def test_verify_grid_check_ids_match_master_spec():
    """§22 checks are numbered 01..06 verbatim. IDs MUST match."""
    doc = _read_yaml(VERIFY_GRID)
    checks = doc.get("verify_grid", {}).get("checks", [])
    ids = [c.get("id") for c in checks]
    assert ids == ["01", "02", "03", "04", "05", "06"], (
        f"verify-grid check IDs MUST be 01..06 per master spec §22; "
        f"got {ids}"
    )


def test_verify_grid_check_names_match_master_spec_verbatim():
    """Each of the 6 §22 checks has an operator-verbatim NAME.
    Operator-stated names (from master spec §22 table):
      01: Microcode / ISA  → avx512_vnni + avx512_bf16 check
      02: Bus Geometry  → PCIe x8 dual slots
      03: Linux Memory  → ZFS ARC clamp
      04: Driver Fabric  → NVIDIA 560+ Open Kernel
      05: Security Core  → Tetragon socket
      06: Network Line  → MTU 9000 jumbo
    """
    doc = _read_yaml(VERIFY_GRID)
    checks = doc.get("verify_grid", {}).get("checks", [])
    by_id = {c.get("id"): c for c in checks}
    expected_keywords = {
        "01": ["Microcode", "ISA"],          # §22.1 Microcode / ISA
        "02": ["Bus", "Geometry"],            # §22.2 Bus Geometry
        "03": ["Linux", "Memory"],            # §22.3 Linux Memory
        "04": ["Driver", "Fabric"],           # §22.4 Driver Fabric (NVIDIA)
        "05": ["Security", "Core"],           # §22.5 Security Core (Tetragon)
        "06": ["Network", "Line"],            # §22.6 Network Line
    }
    missing: list[str] = []
    for cid, keywords in expected_keywords.items():
        name = by_id.get(cid, {}).get("name", "")
        for kw in keywords:
            if kw.lower() not in name.lower():
                missing.append(f"{cid}:'{kw}' not in '{name}'")
    assert not missing, (
        f"§22 verify-grid check names missing operator-verbatim keywords: "
        f"{missing}"
    )


def test_verify_grid_check_03_arc_max_bytes_verbatim():
    """§22.3 specifies ZFS ARC max = 137438953472 bytes (= 128 GiB).
    Operator-verbatim exact integer MUST be referenced somewhere in
    the verify-grid yaml (either checks_what field OR doc text)."""
    body = VERIFY_GRID.read_text(encoding="utf-8")
    assert "137438953472" in body or "128 GiB" in body or "BOOTSTRAP_VERIFY_ARC_MAX_BYTES" in body, (
        f"verify-grid.yaml missing §22.3 ZFS ARC max value (operator-"
        f"verbatim 137438953472 bytes / 128 GiB)"
    )


def test_verify_grid_check_06_jumbo_mtu_9000():
    """§22.6 specifies MTU = 9000 jumbo frames on data NIC (enp5s0).
    Operator-verbatim value MUST appear."""
    body = VERIFY_GRID.read_text(encoding="utf-8")
    assert "9000" in body, (
        "verify-grid.yaml missing §22.6 jumbo MTU=9000 verbatim value"
    )


def test_phases_yaml_has_5_phases_per_master_spec_12():
    """Master spec §12 specifies exactly 5 phases (I, II, III, IV, V)."""
    doc = _read_yaml(PHASES)
    phases = doc.get("phases", [])
    assert len(phases) == 5, (
        f"§12 phases MUST be exactly 5 (I, II, III, IV, V); got {len(phases)}"
    )


def test_phases_ids_match_master_spec_roman_numerals():
    """§12 phases use Roman numerals I-V verbatim."""
    doc = _read_yaml(PHASES)
    phases = doc.get("phases", [])
    ids = [p.get("id") for p in phases]
    assert ids == ["I", "II", "III", "IV", "V"], (
        f"§12 phase IDs MUST be Roman I..V verbatim; got {ids}"
    )


def test_phase_ii_references_zen5_kernel_compilation():
    """§12 Phase II verbatim: 'The Zen 5 Kernel Compilation Engine'."""
    body = PHASES.read_text(encoding="utf-8")
    # Phase II should mention kernel + Zen 5 / znver5
    body_lower = body.lower()
    assert ("zen 5" in body_lower or "znver5" in body_lower), (
        "phases.yaml Phase II missing 'Zen 5' or 'znver5' operator-"
        "verbatim reference (§12 Phase II is 'The Zen 5 Kernel "
        "Compilation Engine')"
    )
    assert "kernel" in body_lower, (
        "phases.yaml missing 'kernel' reference (§12 Phase II)"
    )


def test_phase_v_references_tetragon_guardian():
    """§12 Phase V verbatim: 'Multi-Agent Mission Control & Guardian
    Loop Activation' — features Tetragon + Guardian."""
    body = PHASES.read_text(encoding="utf-8")
    body_lower = body.lower()
    has_tetragon = "tetragon" in body_lower
    has_guardian = "guardian" in body_lower
    assert has_tetragon or has_guardian, (
        "phases.yaml Phase V missing 'tetragon' OR 'guardian' "
        "operator-verbatim reference (§12 Phase V)"
    )


def test_phases_preconditions_postconditions_present():
    """Each phase MUST have preconditions + postconditions (operator
    invariant per §12: each phase gates the next via preconditions)."""
    doc = _read_yaml(PHASES)
    phases = doc.get("phases", [])
    missing: list[str] = []
    for p in phases:
        pid = p.get("id")
        if not p.get("preconditions") and pid != "I":
            # Phase I has no preconditions (it's the entry)
            missing.append(f"{pid}:preconditions")
        if not p.get("postconditions"):
            missing.append(f"{pid}:postconditions")
    assert not missing, (
        f"phases missing preconditions/postconditions: {missing}. "
        f"Per §12 'Each phase must be completed and validated before "
        f"the downstream phase is initiated' — all phases need state "
        f"contracts."
    )
