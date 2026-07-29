"""Step 09 must actually check the ISO the operator is about to flash.

2026-07-29, doing the Ubuntu flash-readiness pass. Three defects, each of which
made the step report success about something it had not examined:

  1. The installer branch `exit 0`'d BEFORE the sha256sums + build-provenance
     emission at the bottom of the file. So the one artifact an operator writes
     to a physical disk was the only one with no recorded checksum, and the
     flash panel showed "(no recorded sha256)" for every installer ISO ever
     built.

  2. The "vintage" cross-check — does this ISO carry the answer file the tree
     currently defines — only understood /simple-cdd/default.preseed. For a
     Subiquity ISO it silently did nothing, so Ubuntu had no such check at all.
     That is the 2026-07-26 stale-artifact failure one installer over.

  3. The handoff `export`s SOVEREIGN_OS_IMAGE_DIR and overrode the caller, so
     the step silently verified whatever step 07 last built. It is the same
     stale-handoff trap step 07 documents for SOVEREIGN_OS_SUBSTRATE — and it
     made a NEGATIVE test of (2) pass, because the doctored ISO was never the
     file being read.

And a fourth, in the fix for (2): the first cut GREPPED the answer file for
"nvidia-driver-", which matches a COMMENT mentioning nvidia-driver-install.sh.
It passed an ISO with the driver package removed. A check that reads comments
as configuration is worse than no check, so it parses the YAML instead.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts/build/09-image-verify.sh"
FLASH_API = REPO_ROOT / "scripts/operator/flash-api.py"


@pytest.fixture(scope="module")
def body() -> str:
    return VERIFY.read_text(encoding="utf-8")


def test_the_installer_path_reaches_the_provenance_emission(body):
    """It must not exit before sha256sums.txt is written."""
    head = body[: body.index("# Emit sha256sums.txt")]
    installer = head[head.index('= "installer" ]; then'):]
    # Strip comments first. A first cut asserted against the raw text and
    # failed on the COMMENT that explains why the exit was removed — the same
    # read-a-comment-as-code mistake this file exists to police.
    installer = "\n".join(
        l for l in installer.splitlines() if not l.lstrip().startswith("#")
    )
    assert "exit 0" not in installer, (
        "the installer branch exits before the checksum/provenance emission. "
        "The artifact the operator actually flashes would have no recorded "
        "sha256, which is exactly the one that needs it."
    )
    assert "_installer_done" in body, (
        "the installer path must fall through to provenance while skipping the "
        "whole-disk QEMU boot (an ISO is not a disk to boot)"
    )


def test_the_whole_disk_boot_is_skipped_for_an_iso(body):
    assert 'if [ -z "${_installer_done:-}" ]; then' in body, (
        "falling through must not attempt to QEMU-boot an ISO as a disk image"
    )


def test_the_ubuntu_answer_file_is_checked_at_all(body):
    """Debian had a vintage check; Ubuntu had none."""
    assert "/autoinstall/user-data" in body, (
        "step 09 must cross-check the SHIPPED autoinstall against this tree. "
        "Without it, an Ubuntu ISO whose answer file predates the current tree "
        "flashes silently — the 2026-07-26 stale-artifact failure."
    )


def test_the_answer_file_is_parsed_not_grepped(body):
    """A comment is not configuration.

    Grepping for "nvidia-driver-" passed an ISO with the driver package
    REMOVED, because the file's own comment mentions nvidia-driver-install.sh.
    """
    seg = body[body.index("/autoinstall/user-data"):]
    seg = seg[: seg.index("rm -rf")]
    assert "yaml.safe_load" in seg, (
        "the autoinstall check must PARSE the YAML. Grepping raw text reads "
        "comments as configuration and passed a stale ISO."
    )
    for probe in ("packages", "late-commands"):
        assert probe in seg, f"the check must inspect {probe!r}"


@pytest.mark.parametrize("condition", [
    "nvidia-driver",          # the driver that provides the DRM device
    "nvidia-drm.modeset=1",   # the cmdline option that activates it
    "nomodeset",              # fatal on Ubuntu
    "select-display-manager", # gdm3 otherwise keeps the alias
    "linux-image-6.12.0",     # the custom znver5 kernel
])
def test_each_fatal_condition_is_checked(body, condition):
    seg = body[body.index("/autoinstall/user-data"):]
    seg = seg[: seg.index("rm -rf")]
    assert condition in seg, (
        f"the ISO check must verify {condition!r} — every one of these has "
        "produced a black screen or a missing payload on real hardware"
    )


def test_an_explicit_image_dir_wins_over_the_handoff(body):
    """Otherwise the step verifies a file the caller never named."""
    assert "_image_dir_requested" in body, (
        "step 09 must honour an explicitly-set SOVEREIGN_OS_IMAGE_DIR. The "
        "handoff exports it, so sourcing the handoff silently redirected the "
        "step to whatever step 07 last built — the same stale-handoff trap "
        "step 07 documents for SOVEREIGN_OS_SUBSTRATE."
    )
    idx = body.index("_image_dir_requested")
    seg = body[idx: idx + 900]
    assert "log_warn" in seg, "the override must be reported, not silent"


def test_the_flash_panel_can_actually_read_the_checksums():
    """sha256sum's output is `<hash>  ./name`; the panel compared bare names.

    So even once the file existed, the panel still said "(no recorded sha256)".
    """
    src = FLASH_API.read_text(encoding="utf-8")
    seg = src[src.index("sums.is_file()"):]
    seg = seg[: seg.index("kind =")]
    assert 'split("/")' in seg or "os.path.basename" in seg or "Path(" in seg, (
        "flash-api must normalise the filename field from sha256sums.txt — "
        "step 09 generates it with `find .`, so every entry reads './name' and "
        "a bare-name comparison never matches"
    )
    assert 'lstrip("*")' in seg, (
        "sha256sum's binary-mode marker ('*name') must also be stripped"
    )
