"""The disk inspector must READ the disk — and must never PASS on nothing.

This file builds a synthetic LVM disk with a real ext4 filesystem, writes known
content into it, and asserts on what the inspector says. It exists because the
inspector has now produced a FALSE PASS twice, and a checker that only ever
passes is worse than no checker at all:

  1. `rdump` into a directory that ALREADY EXISTS extracts nothing, silently.
     ${MNT}/etc/modprobe.d had been pre-created by mkdir, so the blacklist files
     were never staged, `_bl` came back empty, and the master-of-seat invariant
     — the single check the script exists for — reported PASS on a disk
     reproducing the 2026-07-28 dark screen.

  2. On a disk with NO grub.cfg and NO /etc/modprobe.d, the verdict fell through
     to "a route to a graphical seat exists": a PASS derived entirely from two
     absent files.

Both were caught only by NEGATIVE testing. So: negative cases first.

It also covers the LVM path. The Debian installer uses partman-auto/method=lvm
(VG `sovereign`, LV `root`), so the old "largest partition" rule picked the LVM
PV, debugfs found no superblock, and every assertion would have read nothing.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSPECT = REPO_ROOT / "scripts/build/lib/inspect-installed-disk.sh"

SS = 512
PART_START = 2048 * SS       # 1 MiB
EXTENT = 8192                # sectors = 4 MiB
PE_START = 2048              # sectors = 1 MiB into the PV
EXT_COUNT = 40               # a 160 MiB LV
LV_OFF = PART_START + PE_START * SS


def _tool(name: str) -> str | None:
    return shutil.which(name) or shutil.which(name, path="/sbin:/usr/sbin")


REQUIRED = ["mke2fs", "debugfs", "sfdisk", "qemu-img"]
missing = [t for t in REQUIRED if not _tool(t)]
pytestmark = pytest.mark.skipif(
    bool(missing), reason=f"needs {missing} to build a synthetic ext4/LVM disk"
)

VG_META = f"""
sovereign {{
id = "AAAAAA-0000-1111-2222-3333-4444-555555"
seqno = 2
format = "lvm2"
status = ["RESIZEABLE", "READ", "WRITE"]
extent_size = {EXTENT}

physical_volumes {{

pv0 {{
id = "BBBBBB-0000-1111-2222-3333-4444-666666"
device = "/dev/vda3"
status = ["ALLOCATABLE"]
dev_size = 1000000
pe_start = {PE_START}
pe_count = 500
}}
}}

logical_volumes {{

root {{
id = "CCCCCC-0000-1111-2222-3333-4444-777777"
status = ["READ", "WRITE", "VISIBLE"]
segment_count = 1

segment1 {{
start_extent = 0
extent_count = {EXT_COUNT}
type = "striped"
stripe_count = 1
stripes = [
"pv0", 0
]
}}
}}

home {{
id = "DDDDDD-0000-1111-2222-3333-4444-888888"
status = ["READ", "WRITE", "VISIBLE"]
segment_count = 1

segment1 {{
start_extent = {EXT_COUNT}
extent_count = 5
type = "striped"
stripe_count = 1
stripes = [
"pv0", {EXT_COUNT}
]
}}
}}
}}
}}
""".encode()


def build_disk(tmp: Path, files: dict[str, str]) -> Path:
    """A GPT disk whose single big partition is an LVM PV holding LV `root`."""
    tmp.mkdir(parents=True, exist_ok=True)
    raw = tmp / "disk.raw"
    total = PART_START + (PE_START + EXTENT * (EXT_COUNT + 8)) * SS
    raw.write_bytes(b"\0" * total)

    with raw.open("r+b") as fh:
        fh.seek(PART_START + SS)
        fh.write(b"LABELONE" + b"\0" * 24 + b"LVM2 001")
        fh.seek(PART_START + 4096)
        fh.write(VG_META)

    subprocess.run(
        [_tool("mke2fs"), "-q", "-t", "ext4", "-E", f"offset={LV_OFF}",
         str(raw), f"{EXTENT * EXT_COUNT * SS // 1024}k"],
        check=True, capture_output=True,
    )
    subprocess.run(
        [_tool("sfdisk"), "--no-reread", "--no-tell-kernel", str(raw)],
        input=f"label: gpt\nstart={PART_START // SS}, type=lvm\n",
        text=True, capture_output=True, check=True,
    )

    # Carve the LV out, populate it, splice it back — debugfs needs a bare fs.
    lv = tmp / "lv.img"
    with raw.open("rb") as src, lv.open("wb") as dst:
        src.seek(LV_OFF)
        dst.write(src.read(EXT_COUNT * EXTENT * SS))

    made: set[str] = set()
    for path, content in files.items():
        parts = Path(path).parts[1:-1]
        for i in range(len(parts)):
            d = "/" + "/".join(parts[: i + 1])
            if d not in made:
                subprocess.run([_tool("debugfs"), "-w", "-R", f"mkdir {d}", str(lv)],
                               capture_output=True)
                made.add(d)
        src_file = tmp / ("f" + str(abs(hash(path))))
        src_file.write_text(content)
        subprocess.run(
            [_tool("debugfs"), "-w", "-R", f"write {src_file} {path}", str(lv)],
            capture_output=True,
        )

    with raw.open("r+b") as dst:
        dst.seek(LV_OFF)
        dst.write(lv.read_bytes())

    qcow = tmp / "disk.qcow2"
    subprocess.run([_tool("qemu-img"), "convert", "-O", "qcow2", str(raw), str(qcow)],
                   check=True, capture_output=True)
    return qcow


def inspect(disk: Path) -> tuple[int, str]:
    out = subprocess.run(["bash", str(INSPECT), str(disk)],
                         capture_output=True, text=True, timeout=300)
    return out.returncode, re.sub(r"\x1b\[[0-9;]*m", "", out.stdout + out.stderr)


GRUB_DEB = "  linux /boot/vmlinuz-6.12.0 root=/dev/mapper/sovereign-root ro nomodeset quiet\n"
GRUB_UBU = "  linux /boot/vmlinuz-6.12.0 root=/dev/vda2 ro nvidia-drm.modeset=1 quiet\n"
OSREL_DEB = 'ID=debian\nPRETTY_NAME="Debian GNU/Linux 13 (trixie)"\n'
OSREL_UBU = 'ID=ubuntu\nPRETTY_NAME="Ubuntu 26.04 LTS"\n'


# ── the LVM path itself ─────────────────────────────────────────────────────

def test_it_finds_the_root_lv_inside_lvm(tmp_path):
    """The Debian layout. The old rule picked the PV and read nothing."""
    disk = build_disk(tmp_path, {"/etc/os-release": OSREL_DEB})
    _, out = inspect(disk)
    assert "LVM: LV root" in out, (
        "the inspector did not resolve the root LV inside the LVM PV — on a "
        f"Debian install every assertion would read nothing.\n{out}"
    )
    assert "cannot locate the root filesystem" not in out, out


# ── the negative cases, which are the point of this file ────────────────────

def test_an_empty_disk_never_reports_a_graphical_seat(tmp_path):
    """A PASS derived from two absent files is the bug, not the check."""
    disk = build_disk(tmp_path, {})
    rc, out = inspect(disk)
    assert "a route to a graphical seat exists" not in out, (
        "the inspector claimed a graphical seat on a disk with no grub.cfg and "
        f"no /etc/modprobe.d. Absence of evidence is not evidence.\n{out}"
    )
    assert "cannot be judged" in out, (
        f"it must say the invariant cannot be judged, not stay silent.\n{out}"
    )
    assert rc != 0, "an empty disk must not exit 0"


def test_nomodeset_on_ubuntu_is_reported_fatal(tmp_path):
    """The exact configuration that shipped a blinking cursor."""
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg": GRUB_DEB,     # nomodeset — wrong for Ubuntu
    })
    rc, out = inspect(disk)
    assert "FATAL" in out, (
        f"nomodeset on an Ubuntu install must be reported FATAL.\n{out}"
    )
    assert rc != 0


def test_ubuntu_without_the_drm_option_fails(tmp_path):
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg": "  linux /boot/vmlinuz-6.12.0 root=/dev/vda2 ro quiet\n",
    })
    rc, out = inspect(disk)
    assert "nvidia-drm.modeset=1 ABSENT" in out, out
    assert rc != 0


def test_a_blacklisted_nvidia_is_caught_on_ubuntu(tmp_path):
    """The option is inert if the module cannot bind."""
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg": GRUB_UBU,
        "/etc/modprobe.d/blacklist-nvidia.conf": "blacklist nvidia\n",
    })
    _, out = inspect(disk)
    assert "BLACKLISTED" in out, (
        f"a blacklisted nvidia module means no DRM device, so "
        f"nvidia-drm.modeset=1 does nothing.\n{out}"
    )


# ── the positive cases, so the checks are not merely always-fail ────────────

def test_a_correct_debian_install_passes_the_seat_check(tmp_path):
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_DEB,
        "/boot/grub/grub.cfg": GRUB_DEB,
    })
    _, out = inspect(disk)
    assert "nomodeset IS on the installed kernel command line" in out, out
    assert "FATAL" not in out, f"nomodeset is CORRECT on Debian.\n{out}"


def test_a_correct_ubuntu_install_passes_the_seat_check(tmp_path):
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg": GRUB_UBU,
        "/var/lib/dpkg/status": "Package: nvidia-driver-570-open\nStatus: install ok installed\n",
    })
    _, out = inspect(disk)
    assert "nomodeset correctly ABSENT" in out, out
    assert "nvidia-drm.modeset=1 on the installed kernel command line" in out, out
    assert "an nvidia-driver-* package is installed" in out, out


def test_the_distro_is_read_from_the_disk_not_assumed(tmp_path):
    for osrel, want in ((OSREL_DEB, "Debian"), (OSREL_UBU, "Ubuntu")):
        disk = build_disk(tmp_path / want, {"/etc/os-release": osrel})
        _, out = inspect(disk)
        assert want in out, (
            f"the inspector must read the distro off the disk; it did not see "
            f"{want}.\n{out}"
        )


# ── regressions from the FIRST REAL VM INSTALL (2026-07-29) ─────────────────
# Both of these were invisible to every synthetic test above and were found only
# by running a real Debian install to completion and reading the disk.

def test_os_release_is_read_through_the_symlink(tmp_path):
    """/etc/os-release is a SYMLINK to ../usr/lib/os-release on both distros.

    debugfs `dump` does not follow symlinks: it wrote the 21-byte link target,
    the distro read back "unknown", and the inspector silently defaulted to
    Debian. On an Ubuntu disk that means reporting the CORRECT configuration as
    a failure — the precise mistake the distro-awareness was added to prevent.
    """
    disk = build_disk(tmp_path, {
        "/usr/lib/os-release": OSREL_UBU,     # the real file; /etc is a symlink
        "/boot/grub/grub.cfg": GRUB_UBU,
    })
    _, out = inspect(disk)
    assert "Ubuntu" in out, (
        "the inspector did not read os-release from /usr/lib — it must not "
        f"depend on the /etc symlink that debugfs cannot follow.\n{out}"
    )
    assert "unknown" not in out.split("installed distro:")[1].split("\n")[0], out


def test_a_clean_self_check_is_not_reported_as_a_failure(tmp_path):
    """`grep -c` EXITS 1 when the count is zero, while still printing "0".

    The old `|| echo 0` fallback therefore appended a SECOND line, and the
    arithmetic test died with "[: 0\\n0: integer expression expected" — turning
    a clean install into a FAIL. Same trap as commit 440f65b8.
    """
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_DEB,
        "/usr/lib/os-release": OSREL_DEB,
        "/boot/grub/grub.cfg": GRUB_DEB,
        "/var/log/sovereign-os/install-verify.log":
            "== sovereign-os install self-check ==\n  OK: nomodeset present\n",
    })
    _, out = inspect(disk)
    assert "integer expression expected" not in out, (
        f"the grep -c exit-1 trap is back.\n{out}"
    )
    assert "self-check found no problems" in out, (
        f"a clean self-check log must report PASS, not a failure count.\n{out}"
    )


def test_real_problems_in_the_self_check_are_still_surfaced(tmp_path):
    """The counterpart: the fix must not make the check toothless."""
    disk = build_disk(tmp_path, {
        "/etc/os-release": OSREL_DEB,
        "/usr/lib/os-release": OSREL_DEB,
        "/boot/grub/grub.cfg": GRUB_DEB,
        "/var/log/sovereign-os/install-verify.log":
            "  PROBLEM: nomodeset ABSENT\n  MISSING firmware-amd-graphics\n",
    })
    _, out = inspect(disk)
    assert "self-check reported 2 problem(s)" in out, (
        f"real problems in the on-disk report must still be surfaced.\n{out}"
    )


# ── the GRUB recovery-entry trap (2026-07-29, first full Ubuntu install) ────
# Every Debian-family grub.cfg ends each menuentry group with a RECOVERY entry
# that carries `nomodeset` (Ubuntu) or `single` (Debian) — that is what recovery
# mode IS. Grepping all `linux` lines therefore finds nomodeset on a PERFECTLY
# CORRECT Ubuntu install and reports it FATAL. The real install read:
#     linux … ro nvidia-drm.modeset=1 quiet splash            <- what boots
#     linux … ro recovery nomodeset dis_ucode_ldr nvidia-drm.modeset=1
# Only the entry the machine actually boots counts.

GRUB_UBU_WITH_RECOVERY = (
    "  linux /boot/vmlinuz-7.0.0-28-generic root=UUID=x ro nvidia-drm.modeset=1 quiet splash\n"
    "  linux /boot/vmlinuz-7.0.0-28-generic root=UUID=x ro recovery nomodeset "
    "dis_ucode_ldr nvidia-drm.modeset=1\n"
)
GRUB_DEB_WITH_RECOVERY = (
    "  linux /boot/vmlinuz-6.12.0 root=/dev/mapper/sovereign-root ro quiet nomodeset\n"
    "  linux /boot/vmlinuz-6.12.0 root=/dev/mapper/sovereign-root ro single dis_ucode_ldr\n"
)


def test_grubs_recovery_entry_does_not_fake_a_fatal_on_ubuntu(tmp_path):
    """The exact grub.cfg produced by the first real Ubuntu install."""
    disk = build_disk(tmp_path, {
        "/usr/lib/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg": GRUB_UBU_WITH_RECOVERY,
        "/var/lib/dpkg/status": "Package: nvidia-driver-570-open\nStatus: install ok installed\n",
    })
    _, out = inspect(disk)
    assert "FATAL" not in out, (
        "the inspector read nomodeset out of GRUB's RECOVERY entry and called a "
        f"correct Ubuntu install fatal. Only the primary entry counts.\n{out}"
    )
    assert "nomodeset correctly ABSENT" in out, out
    assert "nvidia-drm.modeset=1 on the installed kernel command line" in out, out


def test_a_real_nomodeset_on_ubuntu_is_still_caught(tmp_path):
    """The counterpart — the fix must not blind the check.

    Here nomodeset is on the PRIMARY entry, which is the shipping failure.
    """
    disk = build_disk(tmp_path, {
        "/usr/lib/os-release": OSREL_UBU,
        "/boot/grub/grub.cfg":
            "  linux /boot/vmlinuz-7.0.0 root=UUID=x ro nomodeset quiet splash\n"
            "  linux /boot/vmlinuz-7.0.0 root=UUID=x ro recovery nomodeset dis_ucode_ldr\n",
    })
    rc, out = inspect(disk)
    assert "FATAL" in out, (
        f"nomodeset on the PRIMARY entry must still be reported fatal.\n{out}"
    )
    assert rc != 0


def test_debians_single_recovery_entry_is_ignored_too(tmp_path):
    """Debian's recovery entry uses `single` and carries no nomodeset.

    Counting it would make a correct Debian install look like it had lost
    nomodeset from half its entries.
    """
    disk = build_disk(tmp_path, {
        "/usr/lib/os-release": OSREL_DEB,
        "/boot/grub/grub.cfg": GRUB_DEB_WITH_RECOVERY,
    })
    _, out = inspect(disk)
    assert "nomodeset IS on the installed kernel command line" in out, (
        f"the primary Debian entry has nomodeset; the `single` recovery entry "
        f"must not confuse the verdict.\n{out}"
    )


# ── the APPLIANCE shape (2026-07-30, first Ubuntu mkosi image) ──────────────
# The inspector was written for installer-produced disks and reported FOUR
# failures on a complete, bootable appliance:
#
#   FAIL  no /boot/grub/grub.cfg — nothing will boot   (it boots systemd-boot)
#   FAIL  vmlinuz-6.12.0 NOT installed                 (it is a UKI on the ESP)
#   FAIL  no initrd.img-6.12.0                         (inside the UKI)
#   FAIL  active-profile missing                       (it is active-profile.env)
#
# The operator asked "did it really work?" — and the honest answer needed the
# image read, not the checker believed. A checker that condemns a working
# artifact is the same cry-wolf failure as the GRUB recovery-entry bug.

def _tool_or_skip(name):
    t = _tool(name)
    if not t:
        pytest.skip(f"needs {name}")
    return t


def build_appliance(tmp: Path) -> Path:
    """A GPT disk shaped like mkosi's: ESP with a UKI + ext4 root, no GRUB."""
    mformat, mcopy = _tool_or_skip("mformat"), _tool_or_skip("mcopy")
    tmp.mkdir(parents=True, exist_ok=True)
    esp_start, esp_len = 1 << 20, 64 << 20
    root_start, root_len = esp_start + esp_len, 160 << 20
    raw = tmp / "appliance.raw"
    # +1 MiB of slack: GPT keeps a BACKUP header in the last ~33 sectors, so a
    # disk sized exactly to its partitions fails with
    #   "The last usable GPT sector is N, but N+33 is requested".
    raw.write_bytes(b"\0" * (root_start + root_len + (1 << 20)))

    esp = tmp / "esp.img"
    esp.write_bytes(b"\0" * esp_len)
    subprocess.run([mformat, "-i", str(esp), "-F", "::"], check=True, capture_output=True)
    for d in ("::/EFI", "::/EFI/Linux", "::/EFI/systemd"):
        subprocess.run([_tool_or_skip("mmd"), "-i", str(esp), d], capture_output=True)
    uki = tmp / "sovereign-6.12.0.efi"
    uki.write_bytes(b"MZ" + b"\0" * 4096 + b"systemd-boot stub")
    subprocess.run([mcopy, "-i", str(esp), str(uki), "::/EFI/Linux/"],
                   check=True, capture_output=True)
    sdb = tmp / "systemd-bootx64.efi"
    sdb.write_bytes(b"MZ" + b"systemd-boot 259" + b"\0" * 512)
    subprocess.run([mcopy, "-i", str(esp), str(sdb), "::/EFI/systemd/"],
                   check=True, capture_output=True)

    root = tmp / "root.img"
    subprocess.run([_tool("mke2fs"), "-q", "-t", "ext4", str(root),
                    f"{root_len // 1024}k"], check=True, capture_output=True)
    for path, content in {
        "/usr/lib/os-release": 'ID=sovereign\nID_LIKE=debian\nPRETTY_NAME="Sovereign OS"\n',
        "/etc/sovereign-os/active-profile.env": "SOVEREIGN_OS_PROFILE=sain-01\n",
        "/var/lib/dpkg/status": "Package: sddm\nStatus: install ok installed\n",
    }.items():
        made = set()
        for i in range(len(Path(path).parts[1:-1])):
            d = "/" + "/".join(Path(path).parts[1:i + 2])
            if d not in made:
                subprocess.run([_tool("debugfs"), "-w", "-R", f"mkdir {d}", str(root)],
                               capture_output=True)
                made.add(d)
        f = tmp / ("x" + str(abs(hash(path))))
        f.write_text(content)
        subprocess.run([_tool("debugfs"), "-w", "-R", f"write {f} {path}", str(root)],
                       capture_output=True)

    with raw.open("r+b") as dst:
        dst.seek(esp_start); dst.write(esp.read_bytes())
        dst.seek(root_start); dst.write(root.read_bytes())
    subprocess.run(
        [_tool("sfdisk"), "--no-reread", "--no-tell-kernel", str(raw)],
        input=(f"label: gpt\n"
               f"start={esp_start // SS}, size={esp_len // SS}, "
               f"type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B\n"
               f"start={root_start // SS}, size={root_len // SS}, type=linux\n"),
        text=True, capture_output=True, check=True)
    return raw


def test_an_appliance_is_recognised_as_one(tmp_path):
    disk = build_appliance(tmp_path)
    _, out = inspect(disk)
    assert "artifact shape: appliance" in out, (
        "the inspector must tell a mkosi appliance from an installer-produced "
        f"disk; they boot completely differently.\n{out}"
    )


def test_an_appliance_is_not_condemned_for_having_no_grub(tmp_path):
    """It boots systemd-boot + a UKI. There is no GRUB by design."""
    disk = build_appliance(tmp_path)
    _, out = inspect(disk)
    assert "nothing will boot" not in out, (
        f"a complete appliance was reported unbootable for lacking GRUB.\n{out}"
    )
    assert "no /boot/grub/grub.cfg" not in out, out


def test_the_uki_is_found_on_the_esp(tmp_path):
    """FAT long filenames are UTF-16 — `strings` cannot see them.

    A first cut grepped the raw image for "sovereign-6.12.0.efi" and reported
    "the appliance has no kernel" on an image that had one.
    """
    disk = build_appliance(tmp_path)
    _, out = inspect(disk)
    assert "UKI on the ESP" in out and "sovereign-6.12.0.efi" in out, (
        f"the inspector did not find the UKI that is on the ESP.\n{out}"
    )
    assert "has no kernel" not in out, out


def test_the_appliance_profile_marker_is_accepted(tmp_path):
    """provision-bake writes active-profile.env, not active-profile."""
    disk = build_appliance(tmp_path)
    _, out = inspect(disk)
    assert "active-profile missing" not in out, (
        f"active-profile.env is the appliance's marker and must count.\n{out}"
    )
