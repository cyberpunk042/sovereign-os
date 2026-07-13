"""Per-unit systemd coverage contract (F-2026-054 / SDD-966).

The fleet-wide hardening lints (test_sovereign_systemd_fleet_hardening etc.) check
the units in aggregate, and ~70 unit names appear in bespoke tests — but ~41 of the
111 units had no name-specific assertion, so a single orphaned or malformed unit
could slip through. This lint gives EVERY unit its own parametrized test case
(generated from the systemd/system/ listing, so new units are covered automatically):

  * reachability — the unit is not a dead file: it has an [Install] section
    (directly enableable), OR it is a .service paired with a same-stem .timer
    (timer-triggered), OR it is named in another unit's dependency directive
    (Wants/Requires/Before/After/PartOf/BindsTo/…), OR it is referenced in
    config/bootstrap/phases.yaml or a scripts/install/*.sh installer.
  * structural validity — a .service has [Service] + an Exec*; a .timer has [Timer]
    + a schedule (OnCalendar/OnBootSec/OnUnitActiveSec/…); a .target has [Unit].

So an orphaned unit (nobody can enable/trigger it — the F-2026-021 pattern, at the
unit level) or a malformed unit (a service with no ExecStart, a timer with no
schedule) fails CI with a name-specific test id. Complements the install-coverage
contract (SDD-964), which checks the units' ExecStart scripts exist + install-wire.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "systemd" / "system"
PHASES = REPO_ROOT / "config" / "bootstrap" / "phases.yaml"
INSTALL_DIR = REPO_ROOT / "scripts" / "install"

_DEP_DIRECTIVES = (
    "Wants", "Requires", "Requisite", "BindsTo", "PartOf", "Before", "After",
    "WantedBy", "RequiredBy", "Also", "Upholds", "Conflicts",
)


def _units() -> list[Path]:
    return sorted(
        [*UNIT_DIR.glob("*.service"), *UNIT_DIR.glob("*.timer"), *UNIT_DIR.glob("*.target")]
    )


_UNITS = _units()
_BODIES = {u.name: u.read_text(encoding="utf-8") for u in _UNITS}
_PHASES_TEXT = PHASES.read_text(encoding="utf-8") if PHASES.exists() else ""
_INSTALL_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in INSTALL_DIR.glob("*.sh")) if INSTALL_DIR.exists() else ""


def _is_reachable(name: str) -> bool:
    body = _BODIES[name]
    stem = name.rsplit(".", 1)[0]
    if "[Install]" in body:
        return True
    if name.endswith(".service") and f"{stem}.timer" in _BODIES:
        return True
    dep_re = re.compile(
        r"(?m)^(?:" + "|".join(_DEP_DIRECTIVES) + r")=.*\b" + re.escape(name) + r"\b"
    )
    for other, ob in _BODIES.items():
        if other != name and dep_re.search(ob):
            return True
    return name in _PHASES_TEXT or name in _INSTALL_TEXT


def _is_structurally_valid(name: str) -> tuple[bool, str]:
    body = _BODIES[name]
    if name.endswith(".service"):
        if "[Service]" not in body:
            return False, "no [Service] section"
        if not re.search(r"(?m)^Exec(Start|StartPre|Stop)=", body):
            return False, "no ExecStart/ExecStartPre/ExecStop"
        return True, ""
    if name.endswith(".timer"):
        if "[Timer]" not in body:
            return False, "no [Timer] section"
        if not re.search(r"(?m)^(OnCalendar|OnBootSec|OnUnitActiveSec|OnActiveSec|OnStartupSec)=", body):
            return False, "no schedule (OnCalendar/OnBootSec/OnUnitActiveSec/…)"
        return True, ""
    if name.endswith(".target"):
        return ("[Unit]" in body), ("no [Unit] section" if "[Unit]" not in body else "")
    return False, "unknown unit type"


def test_units_exist():
    assert _UNITS, "no systemd units found under systemd/system/"


@pytest.mark.parametrize("unit", [u.name for u in _UNITS])
def test_unit_is_reachable(unit: str):
    assert _is_reachable(unit), (
        f"{unit} is orphaned — nothing enables, triggers, depends on, or installs it "
        "(no [Install], no same-stem .timer, no dependency directive in another unit, "
        "not in phases.yaml or scripts/install/*.sh). Wire it in or remove it."
    )


@pytest.mark.parametrize("unit", [u.name for u in _UNITS])
def test_unit_is_structurally_valid(unit: str):
    ok, reason = _is_structurally_valid(unit)
    assert ok, f"{unit} is malformed: {reason}"
