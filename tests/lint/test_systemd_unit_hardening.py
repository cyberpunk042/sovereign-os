"""Layer 1 lint — every systemd service unit MUST declare defense-in-depth
sandbox flags (ProtectSystem, NoNewPrivileges, PrivateTmp) or carry an
explicit '# HARDENING-WAIVER: <reason>' comment.

Catches regressions where a new service unit lands without sandboxing.
"""

from __future__ import annotations

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "systemd" / "system"

REQUIRED_KEYS = ("ProtectSystem", "NoNewPrivileges", "PrivateTmp")


def _service_units() -> list[pathlib.Path]:
    return sorted(UNIT_DIR.glob("*.service"))


def test_unit_dir_exists():
    assert UNIT_DIR.is_dir(), f"systemd unit dir missing: {UNIT_DIR}"


def test_service_units_present():
    units = _service_units()
    assert len(units) >= 10, f"expected ≥10 service units, found {len(units)}"


@pytest.mark.parametrize("unit", _service_units(), ids=lambda p: p.name)
def test_unit_is_hardened(unit: pathlib.Path):
    """Every service unit declares the three sandbox keys OR has a waiver."""
    text = unit.read_text()

    if "# HARDENING-WAIVER:" in text:
        # Explicit waiver — accept (reason recorded in the unit file)
        return

    missing = [k for k in REQUIRED_KEYS if f"{k}=" not in text]
    assert not missing, (
        f"{unit.name} missing sandbox keys: {missing}. "
        f"Add them under [Service] or add a '# HARDENING-WAIVER: <reason>' "
        f"comment if the unit legitimately cannot be sandboxed."
    )
