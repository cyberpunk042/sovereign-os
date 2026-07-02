"""R397 (E10.M41) — Trinity-side systemd unit Description pin.

Extends R387-R396 operational-artifact pinning to the 4 Trinity-side
systemd service units. Each unit's Description= string is operator-
readable identity content visible in `systemctl list-units` — the
operator-discovery surface for the running inference stack.

Per master spec §17.1 the runtime mapping is:
  Pulse        → ternary CPU inference (bitnet.cpp on CCD 0)
  Logic Engine → vLLM/llama.cpp on RTX 4090 (VFIO sandbox)
  Oracle Core  → vLLM + DFlash on Blackwell (host-resident)
  Router       → OpenAI-compatible front for the direct stack

If a future agent silently rewrites these Description strings, the
operator running `systemctl list-units --type=service` loses
operator-named architectural identity in the systemctl surface.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_DIR = REPO_ROOT / "systemd" / "system"

TRINITY_UNITS = {
    "sovereign-pulse.service": {
        "must_have": ["Pulse", "bitnet.cpp", "CCD 0"],
        "must_have_one_of": ["ternary", "CPU inference"],
        "spec_ref": "§17.1 + §19.2",
    },
    "sovereign-logic-engine.service": {
        "must_have": ["Logic Engine", "RTX 4090", "VFIO"],
        "must_have_one_of": ["vLLM", "llama.cpp"],
        "spec_ref": "§17.1",
    },
    "sovereign-oracle-core.service": {
        "must_have": ["Oracle Core", "Blackwell"],
        "must_have_one_of": ["vLLM", "DFlash"],
        "spec_ref": "§17.1 + dump-tail DFlash",
    },
    "sovereign-router.service": {
        "must_have": ["router"],
        "must_have_one_of": ["OpenAI", "inference"],
        "spec_ref": "§5 + §17.1",
    },
}


def _read_description(unit: Path) -> str:
    """Extract the Description= value from a systemd unit file."""
    if not unit.is_file():
        return ""
    for line in unit.read_text(encoding="utf-8").splitlines():
        if line.startswith("Description="):
            return line[len("Description="):]
    return ""


def test_all_trinity_units_exist():
    """All 4 Trinity-side service units exist."""
    missing = []
    for unit_name in TRINITY_UNITS:
        if not (SYSTEMD_DIR / unit_name).is_file():
            missing.append(unit_name)
    assert not missing, (
        f"Trinity-side service units missing: {missing}"
    )


def test_pulse_description_verbatim():
    """Pulse unit Description references bitnet.cpp + CCD 0 (§17.1
    operator-named CPU runtime on CCD 0)."""
    unit = SYSTEMD_DIR / "sovereign-pulse.service"
    desc = _read_description(unit)
    spec = TRINITY_UNITS["sovereign-pulse.service"]
    missing = [s for s in spec["must_have"] if s not in desc]
    assert not missing, (
        f"sovereign-pulse.service Description missing operator-verbatim "
        f"§17.1 keywords: {missing}; actual: {desc!r}"
    )
    has_one = any(s in desc for s in spec["must_have_one_of"])
    assert has_one, (
        f"sovereign-pulse.service Description missing one of "
        f"{spec['must_have_one_of']}; actual: {desc!r}"
    )


def test_logic_engine_description_verbatim():
    """Logic Engine unit Description references RTX 4090 + VFIO
    (§17.1 operator-named GPU 0 sandbox runtime)."""
    unit = SYSTEMD_DIR / "sovereign-logic-engine.service"
    desc = _read_description(unit)
    spec = TRINITY_UNITS["sovereign-logic-engine.service"]
    missing = [s for s in spec["must_have"] if s not in desc]
    assert not missing, (
        f"sovereign-logic-engine.service Description missing operator-"
        f"verbatim §17.1 keywords: {missing}; actual: {desc!r}"
    )
    has_one = any(s in desc for s in spec["must_have_one_of"])
    assert has_one, (
        f"sovereign-logic-engine.service Description missing one of "
        f"{spec['must_have_one_of']}; actual: {desc!r}"
    )


def test_oracle_core_description_verbatim():
    """Oracle Core unit Description references Blackwell (§17.1
    operator-named GPU 1 host-resident runtime)."""
    unit = SYSTEMD_DIR / "sovereign-oracle-core.service"
    desc = _read_description(unit)
    spec = TRINITY_UNITS["sovereign-oracle-core.service"]
    missing = [s for s in spec["must_have"] if s not in desc]
    assert not missing, (
        f"sovereign-oracle-core.service Description missing operator-"
        f"verbatim §17.1 keywords: {missing}; actual: {desc!r}"
    )
    has_one = any(s in desc for s in spec["must_have_one_of"])
    assert has_one, (
        f"sovereign-oracle-core.service Description missing one of "
        f"{spec['must_have_one_of']}; actual: {desc!r}"
    )


def test_router_description_verbatim():
    """Router unit Description references inference router."""
    unit = SYSTEMD_DIR / "sovereign-router.service"
    desc = _read_description(unit)
    spec = TRINITY_UNITS["sovereign-router.service"]
    missing = [s for s in spec["must_have"] if s not in desc]
    assert not missing, (
        f"sovereign-router.service Description missing keywords: "
        f"{missing}; actual: {desc!r}"
    )
    has_one = any(s in desc for s in spec["must_have_one_of"])
    assert has_one, (
        f"sovereign-router.service Description missing one of "
        f"{spec['must_have_one_of']}; actual: {desc!r}"
    )


def test_every_trinity_description_starts_with_sovereign_os():
    """Every Trinity unit Description should start with 'sovereign-os '
    (project-prefix convention for operator-friendly grouping in
    systemctl output)."""
    for unit_name in TRINITY_UNITS:
        unit = SYSTEMD_DIR / unit_name
        desc = _read_description(unit)
        assert desc.startswith("sovereign-os "), (
            f"{unit_name} Description should start with 'sovereign-os ' "
            f"(project prefix convention); actual: {desc!r}"
        )


def test_descriptions_have_em_dash_separator():
    """Operator-readable Description convention: 'sovereign-os <Name>
    — <runtime detail>' uses em-dash separator. Catches: drift to
    hyphen or colon."""
    for unit_name in TRINITY_UNITS:
        unit = SYSTEMD_DIR / unit_name
        desc = _read_description(unit)
        # Either em-dash OR parens for runtime detail
        has_separator = "—" in desc or "(" in desc
        assert has_separator, (
            f"{unit_name} Description missing em-dash or paren "
            f"separator (operator-readable convention); actual: {desc!r}"
        )


def test_descriptions_substantively_long():
    """Sanity floor: each Description ≥40 chars (substantive identity
    string, not a stub)."""
    for unit_name in TRINITY_UNITS:
        unit = SYSTEMD_DIR / unit_name
        desc = _read_description(unit)
        assert len(desc) >= 40, (
            f"{unit_name} Description too terse ({len(desc)} chars); "
            f"≥40 chars expected; actual: {desc!r}"
        )


def test_no_silent_trinity_renaming():
    """Catch silent Trinity module renaming: Pulse → Inference Server,
    Logic Engine → Engine, etc. Operator-named §17.1 module names
    are load-bearing identity."""
    body_all = "\n".join(
        _read_description(SYSTEMD_DIR / u) for u in TRINITY_UNITS
    )
    # Operator-named modules MUST appear across the 4 Descriptions
    operator_named = ["Pulse", "Logic Engine", "Oracle Core", "router"]
    missing = [m for m in operator_named if m not in body_all]
    assert not missing, (
        f"Operator-named §17.1 Trinity modules missing from unit "
        f"Descriptions: {missing}"
    )
