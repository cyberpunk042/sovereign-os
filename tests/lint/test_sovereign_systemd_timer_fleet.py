"""sovereign-os systemd timer fleet contract.

sovereign-os ships 11 systemd timer files at systemd/system/*.timer.
Each pairs to its sibling .service to fire either on a fixed
calendar schedule (`OnCalendar=`) or on a relative cadence
(`OnBootSec=` + `OnUnitActiveSec=`). The contract is bidirectional:
silent regression of either cadence mechanism or the pairing breaks
the operator-promised behavior with no obvious error path.

Six invariants every timer MUST satisfy:

1. [Timer] section present
2. Pairs to a real on-disk sibling .service via `Unit=<stem>.service`
3. Has EITHER OnCalendar OR OnBootSec+OnUnitActiveSec (not neither)
4. Persistent=true (so missed schedules during host downtime fire on
   next boot — load-bearing for all 11 current timers)
5. WantedBy=timers.target (else timer doesn't auto-start with the
   timers target)
6. The paired .service file actually exists (catches one-sided
   commits + copy-paste renames)

Companion to selfdef's L1-textfile-observer-timer-fleet.sh +
L1-nonobserver-doctor-timer-fleet.sh from earlier this session.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_DIR = REPO_ROOT / "systemd" / "system"


def _timers() -> list[Path]:
    if not SYSTEMD_DIR.is_dir():
        return []
    return sorted(SYSTEMD_DIR.glob("*.timer"))


def test_systemd_dir_present():
    assert SYSTEMD_DIR.is_dir(), f"systemd/system/ not found at {SYSTEMD_DIR}"


def test_at_least_one_timer():
    timers = _timers()
    assert timers, f"no .timer files found under {SYSTEMD_DIR}"


def test_every_timer_has_timer_section():
    """The [Timer] section anchors all the cadence directives. A
    timer file without it would be rejected at systemd load time."""
    missing: list[str] = []
    for t in _timers():
        text = t.read_text(encoding="utf-8", errors="replace")
        if "[Timer]" not in text:
            missing.append(t.name)
    assert not missing, f"timers without [Timer] section: {missing}"


def test_every_timer_pairs_to_sibling_service():
    """Every <stem>.timer must declare Unit=<stem>.service in its
    [Timer] section AND the sibling .service must actually exist on
    disk (else timer fires nothing — operator silently has no
    invocation behind the schedule)."""
    violations: list[str] = []
    for t in _timers():
        stem = t.stem
        text = t.read_text(encoding="utf-8", errors="replace")
        expected_unit_line = f"Unit={stem}.service"
        if expected_unit_line not in text:
            violations.append(f"{t.name}: missing/wrong `{expected_unit_line}` declaration")
            continue
        sibling = SYSTEMD_DIR / f"{stem}.service"
        if not sibling.is_file():
            violations.append(
                f"{t.name}: paired {stem}.service does not exist on disk "
                f"(timer fires nothing)"
            )
    assert not violations, f"timer-service pairing violations: {violations}"


def test_every_timer_has_cadence_directive():
    """Every timer must have at least one cadence trigger: either
    OnCalendar (fixed schedule) OR OnBootSec+OnUnitActiveSec
    (relative cadence). A timer with neither has nothing scheduling
    it — useless artifact."""
    missing: list[str] = []
    for t in _timers():
        text = t.read_text(encoding="utf-8", errors="replace")
        has_calendar = any(
            line.startswith("OnCalendar=") for line in text.splitlines()
        )
        has_relative_pair = (
            any(line.startswith("OnBootSec=") for line in text.splitlines())
            and any(
                line.startswith("OnUnitActiveSec=") for line in text.splitlines()
            )
        )
        if not (has_calendar or has_relative_pair):
            missing.append(t.name)
    assert not missing, (
        f"timers without cadence trigger (OnCalendar OR OnBootSec+"
        f"OnUnitActiveSec): {missing}"
    )


def test_every_timer_has_persistent_true():
    """All 11 current sovereign-os timers carry Persistent=true so
    that schedules missed during host downtime fire on next boot.
    A silent regression would drop missed runs — operator-promised
    backup / log-rotate / security-update-check etc. silently fail
    to catch up after a power outage."""
    missing: list[str] = []
    for t in _timers():
        text = t.read_text(encoding="utf-8", errors="replace")
        has_persistent = any(
            line.strip() == "Persistent=true" for line in text.splitlines()
        )
        if not has_persistent:
            missing.append(t.name)
    assert not missing, (
        f"timers missing Persistent=true (missed schedules silently dropped "
        f"after downtime): {missing}"
    )


def test_every_timer_wanted_by_timers_target():
    """WantedBy=timers.target is what auto-starts the timer when
    systemd boots into multi-user.target. Without it the timer is
    inert until manually started."""
    missing: list[str] = []
    for t in _timers():
        text = t.read_text(encoding="utf-8", errors="replace")
        has_wantedby = any(
            line.strip() == "WantedBy=timers.target" for line in text.splitlines()
        )
        if not has_wantedby:
            missing.append(t.name)
    assert not missing, (
        f"timers missing WantedBy=timers.target (won't auto-start): "
        f"{missing}"
    )
