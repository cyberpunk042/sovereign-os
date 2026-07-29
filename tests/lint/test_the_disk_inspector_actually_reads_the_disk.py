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
