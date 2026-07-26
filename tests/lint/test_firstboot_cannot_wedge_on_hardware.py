"""First boot must not wedge when the hardware isn't the reference SAIN-01.

Operator, 2026-07-26, booting the flashed NVMe: stuck for minutes on
"Job systemd-udev-settle.service/start running", then stopped at
"Reached target sovereign-firstboot.target" with several units failed. Ctrl+Alt+F3
gave a working console — the box was up; first boot simply never completed.

Two independent causes, both structural:

1. Debian's ZFS units carry `Requires=systemd-udev-settle.service` — a DEPRECATED
   unit with a 120s default timeout. On real hardware udev took the full timeout,
   and because it is Requires=, the timeout FAILED zfs-load-module and cascaded.
   The appliance root is ext4 by design and ships no pool (the tank pool is made
   at install time), so the wait bought an import with nothing to import.

2. `sovereign-firstboot.service` used `Requires=` on four HARDWARE-CONDITIONAL
   hooks. Each legitimately fails off-reference: tetragon-policy-load exits 1
   when tetragon isn't installed yet (it is downloaded during this same first
   boot); zfs-arc-clamp needs the zfs module; network-vlan exits 1 without the
   profile's NIC layout. One failure meant the completion marker never ran.

Neither was caught by the QEMU smoke test, because every one of those units is
`ConditionVirtualization=no` — they do not run in a VM at all. Emulator-only
verification is structurally blind to this whole class.

Failures must stay LOUD (metrics + journal). They must not be able to block boot.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIRSTBOOT_SVC = REPO_ROOT / "systemd" / "system" / "sovereign-firstboot.service"
PROVISION_BAKE = REPO_ROOT / "scripts" / "build" / "provision-bake.sh"

# The hardware-conditional hooks that legitimately fail off-reference.
CONDITIONAL = (
    "sovereign-friction-audit.service",
    "sovereign-network-vlan.service",
    "sovereign-tetragon-policy-load.service",
    "sovereign-zfs-arc-clamp.service",
)


def _directive(unit_text: str, key: str) -> list[str]:
    """All values of a [Unit] directive, comments stripped."""
    vals: list[str] = []
    for line in unit_text.splitlines():
        s = line.strip()
        if s.startswith("#") or not s.startswith(f"{key}="):
            continue
        vals.extend(s.split("=", 1)[1].split())
    return vals


def test_completion_marker_does_not_hard_require_hardware_hooks():
    text = FIRSTBOOT_SVC.read_text(encoding="utf-8")
    required = _directive(text, "Requires")
    offenders = [u for u in CONDITIONAL if u in required]
    assert not offenders, (
        "sovereign-firstboot.service Requires= these hardware-conditional hooks: "
        f"{offenders}. One failing unit then makes the completion marker "
        "unreachable and first boot can never finish on any box that is not the "
        "exact SAIN-01 reference. Use Wants= — the failures stay visible in "
        "`systemctl --failed` and in each hook's result=\"fail\" metric."
    )


def test_completion_marker_still_orders_after_them():
    """Non-blocking must not mean unordered — the marker still runs last."""
    text = FIRSTBOOT_SVC.read_text(encoding="utf-8")
    after = _directive(text, "After")
    missing = [u for u in CONDITIONAL if u not in after]
    assert not missing, (
        f"the marker must still be ordered After= {missing} so it records the "
        "end of first boot, not the middle of it"
    )
    wanted = _directive(text, "Wants")
    assert all(u in wanted for u in CONDITIONAL), (
        "the hooks must still be pulled in by the marker (Wants=), or dropping "
        "Requires= would stop them running at all"
    )


def test_udev_settle_stall_is_bounded_and_non_fatal():
    """ZFS must not be able to fail because a deprecated unit timed out."""
    bake = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "systemd-udev-settle.service.d" in bake, (
        "the image must bound systemd-udev-settle's timeout — its 120s default "
        "stalls first boot on real hardware"
    )
    assert "TimeoutStartSec" in bake, "the settle timeout must actually be set"
    for unit in ("zfs-load-module", "zfs-import-cache", "zfs-import-scan"):
        assert f"{unit}.service.d" in bake or "zfs-load-module zfs-import-cache zfs-import-scan" in bake, (
            f"{unit} must get a drop-in demoting the settle dependency"
        )
    # the reset-then-want idiom is what makes it non-fatal
    assert re.search(r"Requires=\\n.*Wants=systemd-udev-settle", bake), (
        "the drop-in must RESET Requires= (empty assignment) and re-add settle "
        "as Wants=, or a timed-out settle still fails zfs"
    )


def test_bake_reports_what_it_changed():
    """A silent systemd override is how the next operator loses an hour."""
    bake = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "zfs/udev-settle" in bake, (
        "provision-bake must log that it altered the zfs/udev-settle wiring"
    )


def test_dns_actually_resolves_on_first_boot():
    """networkd alone gives no resolver — glibc needs /etc/resolv.conf.

    The image enabled systemd-networkd but not systemd-resolved, and shipped no
    /etc/resolv.conf. network-vlan-config.sh writes DNS= into the .network
    files, but that only reaches applications through resolved's stub. So every
    hostname lookup failed on first boot — "curl: (6) Could not resolve host" —
    which is what actually failed the NVIDIA >=570 download, the Tetragon
    download and the UPS connection (operator, 2026-07-26). Those looked like
    three separate bugs and were one.
    """
    bake = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "systemd-resolved" in bake, (
        "the bake must enable systemd-resolved — networkd's DNS= is invisible "
        "to glibc without it"
    )
    assert "/etc/resolv.conf" in bake, (
        "glibc reads /etc/resolv.conf; the image shipped none at all"
    )
    assert "nameserver" in bake, (
        "there must be a static fallback for images without resolved, rather "
        "than shipping a box that cannot resolve any hostname"
    )
