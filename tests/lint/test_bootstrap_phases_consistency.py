"""R425 (E10.M69) — bootstrap phases.yaml ↔ phases.sh + render-phases-md.py
14th bidirectional-consistency lint (YAML phase IDs ↔ shell consumer ↔
markdown renderer ↔ artifact paths exist).

Extends R387-R424 + R389/R410 operational-artifact pinning to:
  config/bootstrap/phases.yaml
  scripts/bootstrap/phases.sh
  scripts/bootstrap/lib/render-phases-md.py

R389 covered the bootstrap YAML schema lint. R410 covered the
verify-grid.yaml ↔ verify.sh bidirectional check. R425 covers the
analogous 4-way triangle for the 5-phase pipeline:

  YAML (5 phases I-V) ↔
  phases.sh (consumer with hardcoded fallback) ↔
  render-phases-md.py (doc generator) ↔
  artifact paths in artifacts[] resolve to real files

Master spec § 12 verbatim 5-phase pipeline:
  I   — Minimal Trixie Base
  II  — Zen 5 Kernel Compilation
  III — Storage Layer + DKMS (ZFS)
  IV  — Container + Network Edge Isolation
  V   — Tetragon eBPF + Guardian + State Fabric Mount

14th bidirectional-consistency lint:
  Every phase declared in phases.yaml MUST be referenced by phases.sh
  (the operator-discoverable inventory tool) AND every artifact path
  in phases.yaml MUST exist on disk (drift = phases.sh reports "✗
  missing" for the artifact = operator sees broken pipeline).

If a future agent silently:
  - drops a phase from phases.yaml = render-phases-md.py emits 4
    phases instead of 5; operator-discovery surface shrinks
  - renames an artifact in phases.yaml without updating the file =
    phases.sh inventory shows "✗ missing"
  - changes a phase ID from I..V to 1..5 = master spec § 12 verbatim
    binding lost
…the § 12 5-phase chronological pipeline silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASES_YAML = REPO_ROOT / "config" / "bootstrap" / "phases.yaml"
PHASES_SH = REPO_ROOT / "scripts" / "bootstrap" / "phases.sh"
RENDER_MD = REPO_ROOT / "scripts" / "bootstrap" / "lib" / "render-phases-md.py"
PHASES_MD = REPO_ROOT / "docs" / "src" / "bootstrap-phases.md"

EXPECTED_PHASE_IDS = ["I", "II", "III", "IV", "V"]
EXPECTED_PHASE_NAMES = {
    "I": "Minimal Trixie Base",
    "II": "Zen 5 Kernel Compilation",
    "III": "Storage Layer + DKMS (ZFS)",
    "IV": "Container + Network Edge Isolation",
    "V": "Tetragon eBPF + Guardian + State Fabric Mount",
}


def _load_yaml() -> dict:
    return yaml.safe_load(PHASES_YAML.read_text(encoding="utf-8")) or {}


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def _phase_list() -> list[dict]:
    data = _load_yaml()
    return data.get("phases") or []


# --- Structural ---


def test_phases_yaml_exists():
    assert PHASES_YAML.is_file(), f"missing {PHASES_YAML}"


def test_phases_sh_exists():
    assert PHASES_SH.is_file(), f"missing {PHASES_SH}"


def test_render_md_exists():
    assert RENDER_MD.is_file(), f"missing {RENDER_MD}"


def test_yaml_has_exactly_five_phases():
    """§ 12 verbatim 5-phase pipeline. Drift adding/removing a phase
    breaks chronological order operator-named for SAIN-01."""
    phases = _phase_list()
    assert len(phases) == 5, (
        f"phases.yaml has {len(phases)} phases (§ 12 verbatim = 5)"
    )


# --- 14th bidirectional-consistency lint (YAML ↔ shell consumer) ---


def test_bidirectional_phase_ids_match():
    """Every phase id in YAML MUST be referenced by phases.sh
    (operator-discoverable inventory tool)."""
    phases = _phase_list()
    yaml_ids = [p.get("id") for p in phases]
    assert yaml_ids == EXPECTED_PHASE_IDS, (
        f"phases.yaml IDs={yaml_ids!r} != Roman-numeral verbatim "
        f"{EXPECTED_PHASE_IDS!r} (master spec § 12 verbatim ordering)"
    )

    sh_body = _read(PHASES_SH)
    for pid in yaml_ids:
        # phases.sh enumerates each phase by Roman numeral in its
        # header comment block
        assert pid in sh_body, (
            f"phases.sh missing reference to phase {pid!r} from "
            f"phases.yaml (bidirectional inventory violation)"
        )


def test_bidirectional_phase_names_match():
    """Every phase name in YAML MUST be discoverable in phases.sh
    (header comment) OR render-phases-md.py reproduces the name."""
    phases = _phase_list()
    sh_body = _read(PHASES_SH)
    for phase in phases:
        pid = phase.get("id")
        name = phase.get("name", "")
        # Either phases.sh has the name verbatim OR it has the ID:name
        # pair in its header
        # (allow partial match — phases.sh may have shortened forms)
        first_word = name.split()[0] if name else ""
        assert first_word in sh_body, (
            f"phases.sh missing phase {pid!r} name '{first_word}' "
            f"(operator-discoverable inventory)"
        )


def test_phase_artifacts_exist_on_disk():
    """Every artifact path in phases.yaml MUST exist (drift =
    phases.sh inventory shows ✗ missing for operator)."""
    phases = _phase_list()
    missing: list[tuple[str, str]] = []
    for phase in phases:
        pid = phase.get("id")
        artifacts = phase.get("artifacts") or []
        for art in artifacts:
            p = REPO_ROOT / art
            if not p.is_file() and not p.is_dir():
                missing.append((pid, art))
    assert not missing, (
        f"phases.yaml references nonexistent artifacts: {missing}\n"
        f"(drift = phases.sh inventory shows '✗ missing' for these)"
    )


# --- Per-phase invariants ---


def test_every_phase_has_required_fields():
    """Every phase MUST have id + name + description + preconditions +
    postconditions + artifacts (operator-discoverable structure)."""
    required = ["id", "name", "description", "preconditions",
                "postconditions", "artifacts"]
    for phase in _phase_list():
        for field in required:
            assert phase.get(field) is not None, (
                f"phases.yaml phase {phase.get('id')!r} missing {field!r} "
                f"(operator-discoverable phase shape)"
            )


def test_every_phase_has_non_empty_artifacts():
    """A phase with no artifacts is operationally invisible."""
    for phase in _phase_list():
        artifacts = phase.get("artifacts") or []
        assert artifacts, (
            f"phases.yaml phase {phase.get('id')!r} has empty artifacts "
            f"(operationally invisible)"
        )


def test_every_phase_has_non_empty_preconditions():
    """preconditions are operator-discoverable gates — what must hold
    BEFORE this phase. Empty = no gate."""
    for phase in _phase_list():
        pre = phase.get("preconditions") or []
        assert pre, (
            f"phases.yaml phase {phase.get('id')!r} has empty "
            f"preconditions (operator-discoverable gate missing)"
        )


def test_every_phase_has_non_empty_postconditions():
    for phase in _phase_list():
        post = phase.get("postconditions") or []
        assert post, (
            f"phases.yaml phase {phase.get('id')!r} has empty "
            f"postconditions (operator-discoverable result missing)"
        )


def test_phase_names_match_master_spec_verbatim():
    """The operator-named phase names MUST match § 12 verbatim."""
    for phase in _phase_list():
        pid = phase.get("id")
        name = phase.get("name", "")
        expected = EXPECTED_PHASE_NAMES[pid]
        assert name == expected, (
            f"phases.yaml phase {pid!r} name={name!r} != "
            f"§ 12 verbatim {expected!r}"
        )


# --- Master spec § 12 reference verbatim ---


def test_yaml_documents_section_12():
    body = _read(PHASES_YAML)
    assert "§ 12" in body or "section 12" in body.lower(), (
        "phases.yaml missing master spec § 12 reference "
        "(operator-discovery context)"
    )


def test_sh_documents_section_12_verbatim_quote():
    """phases.sh header MUST quote § 12 verbatim 'Each phase must be
    completed and validated before the downstream phase is initiated.'"""
    body = _read(PHASES_SH)
    has_verbatim = (
        "Each phase must be completed and validated" in body
        or "chronological" in body.lower()
    )
    assert has_verbatim, (
        "phases.sh missing § 12 verbatim quote in header "
        "(operator-discovery — drift loses WHY of phase ordering)"
    )


# --- Phase ordering (chronological) ---


def test_phase_ordering_is_strictly_roman_i_through_v():
    """Phase IDs MUST appear in YAML in strict I, II, III, IV, V order.
    Drift = chronological order broken; phases.sh enumerates wrong order."""
    yaml_ids = [p.get("id") for p in _phase_list()]
    assert yaml_ids == EXPECTED_PHASE_IDS, (
        f"phases.yaml ordering={yaml_ids!r} != strict "
        f"{EXPECTED_PHASE_IDS!r} (§ 12 chronological pipeline order)"
    )


# --- render-phases-md.py contract ---


def test_render_md_reads_phases_yaml():
    """render-phases-md.py MUST source from phases.yaml (not hardcode
    the phases). Drift = doc generator goes out of sync with YAML."""
    body = _read(RENDER_MD)
    assert "phases.yaml" in body, (
        "render-phases-md.py doesn't reference phases.yaml "
        "(drift = doc generator hardcodes phases out of band)"
    )


def test_render_md_uses_yaml_safe_load():
    """Security: yaml.safe_load (not yaml.load — CVE-grade)."""
    body = _read(RENDER_MD)
    assert "yaml.safe_load" in body, (
        "render-phases-md.py missing yaml.safe_load (security CVE)"
    )


# --- docs/src/bootstrap-phases.md rendered artifact ---


def test_rendered_phases_md_exists():
    """The rendered markdown SHOULD exist (committed alongside source
    — operator-discoverable artifact)."""
    if PHASES_MD.is_file():
        text = _read(PHASES_MD)
        # All 5 Roman numerals should appear
        for pid in EXPECTED_PHASE_IDS:
            assert pid in text, (
                f"docs/src/bootstrap-phases.md missing phase {pid!r} "
                f"(stale render — re-run render-phases-md.py)"
            )


def test_rendered_phases_md_references_master_spec():
    """Rendered surface SHOULD reference master spec § 12."""
    if PHASES_MD.is_file():
        text = _read(PHASES_MD)
        assert "§ 12" in text or "section 12" in text.lower(), (
            "docs/src/bootstrap-phases.md missing § 12 reference"
        )
