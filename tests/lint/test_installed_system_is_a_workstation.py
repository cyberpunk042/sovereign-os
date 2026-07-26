"""`install system` must produce a machine a person can actually use.

Operator, 2026-07-26, after booting the flashed appliance: "it did load some GUI
but it was buggy and there was not even a console tool installed and a lot was
missing." Then: "Lets work on the installer instead, on fixing it."

The from-host installer is the right foundation — it debootstraps a MUTABLE
Debian (apt works, so nothing is a dead end) and installs the custom znver5
kernel. But its package list was the minimum needed to BOOT:

    lvm2 grub-efi-amd64 efibootmgr initramfs-tools sudo locales console-setup
    keyboard-configuration systemd-resolved netbase iproute2 isc-dhcp-client
    python3 python3-yaml python3-jsonschema prometheus-node-exporter
    ca-certificates curl nano less

No terminal emulator. A KDE session with no way to open a shell is not a
workstation, and it would have reproduced the operator's complaint exactly.

Two further faults this locks down:

  * X FALLBACK DRIVERS. `modesetting` needs a DRM device that `nomodeset`
    prevents, and `nvidia` will not bind on Blackwell — so without fbdev/vesa
    the X server cannot start AT ALL and the desktop is a black screen on a
    perfectly healthy system (the appliance's `sddm: Failed to read display
    number from pipe`).
  * THE KERNEL CMDLINE. The installer hardcoded `root=… rw` and ignored the
    profile, so the installed system would boot with KMS enabled — nouveau
    binds the Blackwell cards, fails, and the screen goes dark. The operator's
    own working Debian on this board boots with `nomodeset`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"
ROOTFS_BUILDER = REPO_ROOT / "scripts" / "build" / "build-target-rootfs.sh"
SHARED_LIB = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
# The two installer surfaces from the 2026-07-25 directive.
SURFACES = (INSTALLER, ROOTFS_BUILDER)


def _vars(gui: int = 1) -> dict[str, str]:
    """Resolve the shared definition exactly as the installers do."""
    script = (f"SOVEREIGN_OS_INSTALL_GUI={gui}\n"
              f'. "{SHARED_LIB}"\n'
              'sovereign_os_installed_packages\n'
              'echo "$SOVEREIGN_OS_KERNEL_CMDLINE"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                         cwd=REPO_ROOT).stdout.strip().splitlines()
    return {"packages": out[0] if out else "", "cmdline": out[-1] if out else ""}


def test_a_terminal_emulator_is_installed():
    """The complaint, in one assertion."""
    pkgs = _vars()["packages"].split()
    assert "konsole" in pkgs or "xterm" in pkgs, (
        "the installed desktop has no terminal emulator — a KDE session with no "
        f"way to open a shell is not a usable machine. got: {pkgs}"
    )


def test_x_can_start_without_a_gpu_driver():
    pkgs = _vars()["packages"].split()
    for p in ("xserver-xorg-video-fbdev", "xserver-xorg-video-vesa"):
        assert p in pkgs, (
            f"{p} missing — with nomodeset there is no DRM device for "
            "`modesetting` and nvidia will not bind on Blackwell, so X cannot "
            "start at all and the desktop is a black screen"
        )


def test_basic_hardware_and_filesystem_tooling_is_present():
    """Diagnosing this box over a framebuffer console with no lspci is misery."""
    pkgs = set(_vars()["packages"].split())
    for p in ("pciutils", "lshw", "nvme-cli", "htop", "rsync", "git", "vim"):
        assert p in pkgs, f"{p} missing from the installed workstation"


def test_headless_install_drops_the_gui_only_packages():
    """INSTALL_GUI=0 must not drag in konsole/xterm/X drivers."""
    out = _vars(gui=0)["packages"].split()
    for p in ("konsole", "xterm", "xserver-xorg-video-fbdev", "xserver-xorg-video-vesa"):
        assert p not in out, f"headless install must not pull {p}"
    assert "htop" in out, "headless still needs its console tooling"


def test_the_kernel_cmdline_is_not_hardcoded_bare():
    """`root=… rw` alone means KMS on, which is a black screen on this hardware."""
    text = INSTALLER.read_text(encoding="utf-8")
    writers = re.findall(r'GRUB_CMDLINE_LINUX="([^"]*)"', text)
    assert writers, "no GRUB cmdline writer found"
    for w in writers:
        assert "SOVEREIGN_OS_KERNEL_CMDLINE" in w, (
            f"GRUB cmdline {w!r} is hardcoded — it must carry the configurable "
            "cmdline so nomodeset (and anything else the hardware needs) applies"
        )
    assert "nomodeset" in _vars()["cmdline"], (
        "the default cmdline must include nomodeset: with KMS enabled nouveau "
        "binds the Blackwell cards and fails, and the screen goes dark"
    )


def test_no_console_override_sends_output_to_a_serial_port():
    """The appliance's frozen-cursor bug must not be reintroduced here."""
    cmdline = _vars()["cmdline"]
    if "console=" in cmdline:
        assert cmdline.split("console=")[-1].split()[0].startswith("tty0"), (
            "if console= is set at all, tty0 must be LAST — the kernel gives "
            "/dev/console to the last one listed, and `console=ttyS0` alone "
            "sends every message to a serial port nobody has plugged in"
        )


def test_installer_parses():
    proc = subprocess.run(["bash", "-n", str(INSTALLER)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_both_installer_surfaces_share_one_definition():
    """The bug this library exists to prevent.

    `install system` and the bootable installer USB each debootstrap a root, and
    each carried its OWN hand-copied package list — byte-identical, and both
    missing a terminal emulator. Fixing one would have left the other building
    exactly the same unusable machine, and every future fix would have to be
    made twice. Neither may re-inline a list.
    """
    assert SHARED_LIB.is_file(), "the shared definition must exist"
    for surface in SURFACES:
        text = surface.read_text(encoding="utf-8")
        assert "installed-system.sh" in text, (
            f"{surface.name} must source the shared definition, not carry its own list"
        )
        # the old duplicated list must be gone from both
        assert "lvm2 grub-efi-amd64 efibootmgr initramfs-tools" not in text, (
            f"{surface.name} still inlines the base package list — that is the "
            "duplication that let the two installers drift apart"
        )


def test_shared_packages_all_exist_in_the_archive():
    """A wrong name fails the whole apt-get at INSTALL time, on the operator's box.

    `dnsutils` was already wrong — transitional, trixie ships bind9-dnsutils.
    """
    import shutil
    if not shutil.which("apt-cache"):
        return
    missing = []
    for pkg in _vars()["packages"].split():
        out = subprocess.run(["apt-cache", "policy", pkg],
                             capture_output=True, text=True).stdout
        if "Candidate: (none)" in out or not out.strip():
            missing.append(pkg)
    assert not missing, f"packages not in the archive: {missing}"


def _verifier() -> str:
    t = INSTALLER.read_text(encoding="utf-8")
    return t[t.index("sovereign_verify_install() {"):t.index("\n}\n", t.index("sovereign_verify_install() {"))]


def test_the_installer_verifies_before_claiming_success():
    """It printed claims it never checked.

    "install complete" · "a new firmware boot entry now exists" · "boots to
    graphical.target" · "uname -r → 6.12.0" — none were verified. Every failure
    the operator hit in 2026-07 was discovered by rebooting into a black screen,
    never by the tool that had just declared success.
    """
    text = INSTALLER.read_text(encoding="utf-8")
    assert "sovereign_verify_install() {" in text, "the installer must verify its own output"
    # called on BOTH success paths (offline squashfs + online debootstrap)
    assert text.count("sovereign_verify_install || exit 1") == 2, (
        "verification must gate BOTH install paths, and a failure must be fatal"
    )
    # and it must run while the target is still mounted
    for marker in ('umount "${MNT}/boot/efi" || true', 'umount "${MNT}/boot/efi" 2>/dev/null || true'):
        i = text.index(marker)
        assert "sovereign_verify_install" in text[max(0, i - 200):i], (
            "verification must run BEFORE the unmount, while the root is readable"
        )


def test_the_verifier_covers_every_failure_this_project_actually_hit():
    """Each check maps to a real incident, not a hypothetical."""
    fn = _verifier()
    required = {
        "ESP has NO .efi":            "flashed disk with no bootloader",
        "NO kernel in /boot":         "kernel never installed",
        "usable password":            "operator account shipped LOCKED",
        "display-manager":            "GUI requested, image shipped headless",
        "fbdev/vesa":                 "X could not start → black screen",
        "resolv.conf":                "no DNS → every first-boot download failed",
    }
    for needle, incident in required.items():
        assert needle in fn, f"verifier must check: {incident} ({needle!r})"


def test_verifier_distinguishes_blocking_from_advisory():
    """A missing terminal is bad; an unbootable disk is worse. Don't conflate."""
    fn = _verifier()
    assert "_v_bad" in fn and "_v_warn" in fn, "must separate blocking from advisory"
    assert "return 1" in fn, "blocking problems must fail the install"


TUI = REPO_ROOT / "scripts" / "install" / "installer-tui.sh"
LIVE_BUILD = REPO_ROOT / "scripts" / "build" / "adapters" / "live-build-emit.sh"


def test_installer_usb_never_ships_a_default_credential():
    """Every installer-USB install went out with root:sovereign.

    live-build-emit.sh bakes SOVEREIGN_OS_{ROOT,USER}_PASS=sovereign into
    /opt/sovereign-os/install-answers.env, and installer-tui.sh asked only for
    the target DISK — no password prompt existed anywhere, despite its own
    header claiming the answers were "pre-filled into a whiptail form the
    operator confirms" (audited 2026-07-26).
    """
    tui = TUI.read_text(encoding="utf-8")
    assert "passwordbox" in tui, (
        "the installer must PROMPT for a password — the baked answers file is a "
        "placeholder, not a credential"
    )
    assert "SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD" in tui, (
        "shipping the built-in default must be possible only as a deliberate, "
        "named opt-in"
    )
    # unattended must refuse rather than quietly ship the default
    blk = tui[tui.index("_DEFAULT_PASS="):]
    assert "refusing to install with the built-in default password" in blk, (
        "a non-interactive install on the default password must FAIL, not warn"
    )


def test_the_tui_header_does_not_describe_a_form_it_lacks():
    """The header asserted a whiptail answers form that did not exist."""
    tui = TUI.read_text(encoding="utf-8")
    header = tui[:tui.index("set -euo pipefail")]
    if "pre-filled into a whiptail form" in header:
        assert "No such form existed" in header, (
            "the header claims a form the TUI does not implement"
        )


def test_password_confirmation_and_validation():
    """Empty locks the account; an apostrophe breaks the downstream chroot script."""
    tui = TUI.read_text(encoding="utf-8")
    blk = tui[tui.index("_DEFAULT_PASS="):]
    assert "Confirm the password" in blk, "a typed password must be confirmed"
    assert "empty password locks the account" in blk.lower(), (
        "an empty password must be rejected — it locks the account"
    )
    assert "apostrophe" in blk.lower(), (
        "the chroot setup interpolates the password into a single-quoted string; "
        "an apostrophe would break the install midway"
    )


def test_baked_answers_marks_the_password_as_a_placeholder():
    lb = LIVE_BUILD.read_text(encoding="utf-8")
    i = lb.index("SOVEREIGN_OS_USER_PASS=")
    assert "PLACEHOLDER" in lb[max(0, i - 400):i], (
        "the baked answers file must say the password is a placeholder, or the "
        "next person reads it as a supported default"
    )
