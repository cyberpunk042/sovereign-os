"""Both installers must be provable in a VM, and neither may leak a credential.

2026-07-29. The Debian installer had NO way to be exercised past the disk pick.
Three installs booted on the operator's real machine — custom kernel, 24 CPUs,
261 GB RAM, zero failed units — and showed nothing, at 18 minutes a try. The
fourth attempt corrupted the other NVMe's bootloader. Every one of those was a
question a VM could have answered in an hour, unattended.

Ubuntu got such a harness first. This file makes it structural for BOTH, and
pins the safety properties, because the harnesses must answer exactly the two
things the shipped installers deliberately leave open:

  * the destructive disk write — a device name is not an identity; the preseed
    once hardcoded "skip nvme0n1" and that assumption expired and selected the
    very disk it was written to protect (2026-07-27)
  * the password — the preseed once carried `root-password sovereign` inside
    every ISO, world-readable at /simple-cdd/default.preseed (SDD-015)

Answering those at RUNTIME into scratch is correct. Answering them in a tracked
file, or writing the generated credential anywhere but scratch, is the exact
failure they were removed to prevent.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSPECTOR = REPO_ROOT / "scripts/build/lib/inspect-installed-disk.sh"

HARNESSES = {
    "debian": REPO_ROOT / "scripts/build/installer-cdd/verify-full-install-in-vm.sh",
    "ubuntu": REPO_ROOT / "scripts/build/ubuntu-autoinstall/verify-full-install-in-vm.sh",
}
SHIPPED_ANSWER_FILES = [
    REPO_ROOT / "scripts/build/installer-cdd/profiles/default.preseed",
    REPO_ROOT / "scripts/build/ubuntu-autoinstall/autoinstall/user-data",
]


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_each_installer_has_a_full_install_harness(distro):
    p = HARNESSES[distro]
    assert p.is_file(), (
        f"{distro} has no full-install VM harness. Without one, everything "
        "downstream of the disk pick is only ever exercised on the operator's "
        "real hardware — which is how three 18-minute black-screen boots "
        "happened before anyone knew why."
    )


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_the_harness_inspects_the_installed_disk(distro):
    """Running the installer is not the check. Reading the result is."""
    body = HARNESSES[distro].read_text(encoding="utf-8")
    assert "inspect-installed-disk.sh" in body, (
        f"the {distro} harness must inspect the INSTALLED disk. An install that "
        "exits 0 is not evidence — the 2026-07-28 install exited 0, reported "
        "zero failed units, and showed nothing."
    )


def test_both_harnesses_share_one_inspector():
    """Two inspectors would drift, and the assertions are the whole point."""
    assert INSPECTOR.is_file(), "the shared inspector must exist"
    for distro, p in HARNESSES.items():
        body = p.read_text(encoding="utf-8")
        assert "scripts/build/lib/inspect-installed-disk.sh" in body, (
            f"the {distro} harness must use the SHARED inspector at "
            "scripts/build/lib/, not a private copy. The installers differ; "
            "what counts as a working install does not."
        )


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_the_harness_starts_from_the_shipped_artifact(distro):
    """Testing a hand-built answer file proves nothing about what ships."""
    body = HARNESSES[distro].read_text(encoding="utf-8")
    assert "-extract" in body and "xorriso" in body, (
        f"the {distro} harness must EXTRACT the answer file from the built ISO "
        "and modify that, so it tests what is actually shipped"
    )


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_the_generated_credential_never_leaves_scratch(distro):
    """The credential is minted per run; it must land in WORK and nowhere else."""
    body = HARNESSES[distro].read_text(encoding="utf-8")
    creds = [
        line for line in body.splitlines()
        if "vm-credentials" in line and not line.lstrip().startswith("#")
    ]
    assert creds, f"the {distro} harness should record its throwaway credential"
    for line in creds:
        assert "${WORK}" in line, (
            f"the {distro} harness writes a credential outside scratch:\n  {line!r}\n"
            "It must go under ${WORK} — never the repo, never the ISO (SDD-015)."
        )
    assert re.search(r'chmod 0600 "\$\{WORK\}/vm-credentials', body), (
        f"the {distro} harness must chmod 0600 the credential file"
    )


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_the_password_is_minted_not_hardcoded(distro):
    body = HARNESSES[distro].read_text(encoding="utf-8")
    assert "openssl rand" in body, (
        f"the {distro} harness must MINT a throwaway password per run. A "
        "constant in a tracked file is the SDD-015 failure regardless of it "
        "being 'only for tests'."
    )


@pytest.mark.parametrize("path", SHIPPED_ANSWER_FILES, ids=lambda p: p.name)
def test_the_shipped_answer_files_still_answer_neither(path):
    """The harnesses must not have quietly made the real installers unattended."""
    text = path.read_text(encoding="utf-8")
    body = "\n".join(
        l for l in text.splitlines()
        if not l.lstrip().startswith("#")
    )
    for pat, what in (
        (r"partman/confirm\s+boolean\s+true", "the destructive write confirmation"),
        (r"partman-auto/disk\s+string", "a hardcoded target disk"),
        (r"passwd/root-password(-crypted)?\s+password\s+\S", "a root password"),
        (r"^\s*password:\s*\S", "an identity password"),
    ):
        m = re.search(pat, body, re.M)
        assert not m, (
            f"{path.name} now contains {what} ({m.group(0)!r}). That belongs "
            "ONLY in the runtime-generated VM preseed. The operator picks and "
            "confirms the disk, and no password ships inside an ISO."
        )


@pytest.mark.parametrize("distro", sorted(HARNESSES))
def test_the_harness_refuses_to_report_on_an_empty_disk(distro):
    """A disk that never grew means the install never ran.

    Handing that to the inspector produces a wall of confusing failures that
    look like install bugs instead of "it stopped at a dialog".
    """
    body = HARNESSES[distro].read_text(encoding="utf-8")
    assert re.search(r"actual-size|qemu-img info|disk.*empty", body), (
        f"the {distro} harness should detect a disk the install never wrote to "
        "and say so, rather than inspecting an empty filesystem"
    )


def test_the_inspector_refuses_to_pass_without_evidence():
    """The property that two false PASSes were traced to."""
    body = INSPECTOR.read_text(encoding="utf-8")
    assert "cannot be judged" in body, (
        "the inspector must refuse to report a graphical-seat verdict when "
        "grub.cfg is absent. It previously derived a PASS from two missing "
        "files — the same false-PASS class as the rdump bug."
    )


def test_the_inspector_handles_both_disk_layouts():
    """direct-ext4 (Ubuntu) and LVM (Debian) are not interchangeable."""
    body = INSPECTOR.read_text(encoding="utf-8")
    assert "LABELONE" in body and "logical_volumes" in body, (
        "the inspector must resolve the root LV inside an LVM PV — the Debian "
        "installer uses partman-auto/method=lvm, and the old 'largest "
        "partition' rule picked the PV and read nothing at all"
    )
