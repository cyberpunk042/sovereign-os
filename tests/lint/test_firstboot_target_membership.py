"""first-boot target membership lint (G1 / SDD-998).

`sovereign-firstboot.target` groups the first-boot oneshot hooks. Every install
path enables ONLY the target (`systemctl enable sovereign-firstboot.target` in the
bake + preseed). Per systemd semantics that does **not** pull in the member units:
`systemctl enable <target>` never processes the members' own `[Install]
WantedBy=<target>`, and `PartOf=` propagates stop/restart only — so unless the
target itself declares `Wants=` (or `Upholds=`) each member, the members never
start and first boot silently does nothing (the box comes up as bare Debian:
no network/VLAN, no nvidia/VFIO bind, no ZFS ARC clamp, no Tetragon policy).

This is exactly the failure G1 caught: 10 units declared `WantedBy=` the target,
0 were reachable. This lint keeps the target's `Wants=` set == the set of units
that declare `WantedBy=sovereign-firstboot.target`, in both directions — a new
first-boot hook that isn't wired into the target, or a target that drops a
member, fails CI. The prior `test_preseed_content_verbatim` only checked the
enable *string* was present, which stayed green while first-boot was dead.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNITS = REPO_ROOT / "systemd" / "system"
TARGET = UNITS / "sovereign-firstboot.target"
TARGET_NAME = "sovereign-firstboot.target"


def _directive_values(path: Path, key: str) -> set[str]:
    """All space-separated values across every `key=` line in a unit file."""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        if k.strip() == key:
            out.update(tok for tok in re.split(r"\s+", v.strip()) if tok)
    return out


def _members_by_wantedby() -> set[str]:
    members: set[str] = set()
    for unit in UNITS.glob("sovereign-*.service"):
        if TARGET_NAME in _directive_values(unit, "WantedBy"):
            members.add(unit.name)
    return members


def test_target_exists():
    assert TARGET.is_file(), f"missing {TARGET}"


def test_target_wants_every_member():
    wants = _directive_values(TARGET, "Wants") | _directive_values(TARGET, "Upholds")
    members = _members_by_wantedby()
    missing = members - wants  # declared WantedBy the target but target doesn't Wants= them → never start
    assert not missing, (
        "sovereign-firstboot.target does NOT pull in these member units — they "
        "declare WantedBy=sovereign-firstboot.target but the target has no "
        "Wants=/Upholds= for them, so `systemctl enable` the target leaves them "
        f"dead on first boot: {sorted(missing)}. Add them to the target's Wants=."
    )


def test_target_wants_are_real_members():
    wants = _directive_values(TARGET, "Wants") | _directive_values(TARGET, "Upholds")
    wants_services = {w for w in wants if w.startswith("sovereign-") and w.endswith(".service")}
    members = _members_by_wantedby()
    extra = wants_services - members  # target Wants= a service that isn't a declared member (typo/stale)
    assert not extra, (
        "sovereign-firstboot.target Wants= services that do not declare "
        f"WantedBy=sovereign-firstboot.target (stale/typo): {sorted(extra)}"
    )


def test_at_least_the_known_hooks_are_members():
    """Floor guard: the hardware/network/security first-boot hooks must be wired,
    so a refactor can't quietly empty the target."""
    members = _members_by_wantedby()
    for required in (
        "sovereign-network-vlan.service",
        "sovereign-nvidia-driver-bind.service",
        "sovereign-vfio-bind.service",
        "sovereign-zfs-arc-clamp.service",
        "sovereign-tetragon-policy-load.service",
    ):
        assert required in members, f"{required} lost its WantedBy=sovereign-firstboot.target"
        assert required in (_directive_values(TARGET, "Wants") | _directive_values(TARGET, "Upholds")), (
            f"{required} is not pulled in by the target"
        )
