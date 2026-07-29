"""No first-boot hook may block indefinitely.

2026-07-28. `Type=oneshot` DISABLES the start timeout by default
(systemd.service(5): "except when Type=oneshot is used, in which case the
timeout is disabled by default"). Every member of sovereign-firstboot.target is
oneshot, and 12 of 13 set no TimeoutStartSec at all — so each one could block
forever with no failure, no timeout and no recovery.

That is the shape the cockpit postinst already warns about: enabling the target
is what "hung a boot at Reached Target sovereign-firstboot.target" (2026-07-26),
and an earlier appliance had ~130 services in restart loops.

A bound converts an indefinite hang into a failed unit — something `systemctl
--failed` shows and an operator can act on. Silence is the enemy; this repo has
lost days to installs that reported success and did nothing.

ONE unit is exempt, and the exemption is explicit rather than implied — see
EXEMPT below.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UNITS = REPO_ROOT / "systemd" / "system"
TARGET = UNITS / "sovereign-firstboot.target"

# Unit -> why an unbounded start is correct for it specifically.
EXEMPT = {
    "sovereign-inference-model-provision": (
        "a multi-GB model pull over a slow link can legitimately run for hours "
        "and cutting it corrupts the fetch; the target is After=multi-user.target "
        "so login is already available, and the hook exits 0 on every failure path"
    ),
}


def members() -> list[str]:
    """Every sovereign-*.service the target Wants=.

    Collect ALL Wants= lines, not the first one. The target carries
    `Wants=zfs.target` in [Unit] before the member list, so a single re.search
    matched that, returned zero services, and this whole parametrised suite
    silently tested NOTHING — it reported "2 passed, 1 skipped" while a
    deliberately broken unit sailed through (caught while proving the guard
    bites, 2026-07-28).
    """
    text = TARGET.read_text(encoding="utf-8")
    found: set[str] = set()
    for line in re.findall(r"^Wants=(.+)$", text, re.M):
        found.update(m[: -len(".service")] for m in line.split()
                     if m.endswith(".service"))
    assert found, "sovereign-firstboot.target must declare its members via Wants="
    return sorted(found)


def test_the_member_list_is_actually_discovered():
    """Guard the guard: an empty member list makes every check below vacuous."""
    found = members()
    assert len(found) >= 10, (
        f"only {len(found)} first-boot members discovered ({found}) — the target "
        "declares more than that, so the parser is broken and every "
        "parametrised check below is silently passing on nothing"
    )


@pytest.mark.parametrize("unit", members())
def test_every_firstboot_hook_has_a_bounded_start_timeout(unit: str):
    path = UNITS / f"{unit}.service"
    if not path.exists():
        pytest.skip(f"{unit}.service not present")
    body = path.read_text(encoding="utf-8")

    m = re.search(r"^TimeoutStartSec=(.+)$", body, re.M)
    is_oneshot = re.search(r"^Type=oneshot$", body, re.M) is not None

    if unit in EXEMPT:
        assert m and m.group(1).strip() in ("0", "infinity"), (
            f"{unit} is listed as EXEMPT but no longer declares an unbounded "
            "timeout — remove it from EXEMPT, or restore the value"
        )
        # An exemption must carry its reasoning in the unit, not just in this file.
        assert "EXEMPTION" in body or "exempt" in body.lower(), (
            f"{unit} takes an unbounded start timeout; the unit itself must say WHY, "
            "so the next reader does not 'fix' it into a hang"
        )
        return

    assert m, (
        f"{unit} is Type=oneshot with no TimeoutStartSec. systemd DISABLES the "
        f"start timeout for oneshot units, so this hook can block first boot "
        f"forever — no failure, no timeout, nothing in `systemctl --failed`. "
        f"Set a finite bound, or add it to EXEMPT with a reason."
        if is_oneshot else
        f"{unit} must declare a finite TimeoutStartSec"
    )
    val = m.group(1).strip()
    assert val not in ("0", "infinity"), (
        f"{unit} sets TimeoutStartSec={val}, which systemd treats as INFINITE. "
        f"That is an unrecoverable hang, not a long-running task. If it is "
        f"genuinely unbounded, add it to EXEMPT with the reason."
    )
    assert re.fullmatch(r"\d+", val), (
        f"{unit} TimeoutStartSec={val!r} — use a plain number of seconds so the "
        "bound is obvious at a glance"
    )
    assert 0 < int(val) <= 7200, (
        f"{unit} TimeoutStartSec={val}s is outside the sane 1..7200 range; a "
        "first-boot hook that needs more than two hours should be an exemption "
        "with a written reason, not a very large number"
    )


def test_the_exemption_list_has_not_quietly_grown():
    """Exemptions are the dangerous case — keep them few and deliberate."""
    assert len(EXEMPT) <= 1, (
        f"{len(EXEMPT)} units now claim an unbounded first-boot timeout. Each one "
        "can hang first boot; adding more should be a conscious operator decision, "
        "not a convenient way to silence this test."
    )


def test_the_target_still_declares_its_members():
    """PartOf/WantedBy do not start members — only Wants= does (SDD-998 G1).

    Guards the other half of the same failure: a target that starts nothing at
    all, so first boot silently does NOTHING and the box comes up bare.
    """
    text = TARGET.read_text(encoding="utf-8")
    assert re.search(r"^Wants=.*\.service", text, re.M), (
        "sovereign-firstboot.target must Wants= its member oneshots; enabling the "
        "target alone does not process the members' [Install] sections"
    )
