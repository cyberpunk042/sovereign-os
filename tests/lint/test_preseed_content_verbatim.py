"""R429 (E10.M73) — Debian preseed config Phase-I install entry surface lint.

Extends R387-R428 + R414/R425 operational-artifact pinning to:
  config/preseed/sain-01.preseed.example.cfg

R414 covered cloud-init user-data templates (NoCloud path); R425
covered the § 12 5-phase pipeline. R429 covers the alternate install
entry — Debian preseed (operator-named Phase I § 12 alternative when
cloud-init isn't appropriate).

Operator-discoverable install path: 2 entry points:
  - cloud-init NoCloud (R414 — pre-installed image)
  - Debian preseed (R429 — net-install / interactive media)

Both MUST converge on the same post-install state:
  /etc/sovereign-os/active-profile = sain-01
  /etc/sovereign-os/active-whitelabel = default
  /etc/sovereign-os/active-profile.env carries SOVEREIGN_OS_PROFILE
  sovereign-firstboot.target enabled

§ 8 ZT verbatim:
  - operator account, NOT root
  - passwd/root-login = false (no root login)
  - allow-password-weak = false (operator-named password strength)
  - popularity-contest disabled (sovereignty deny-list)

If a future agent silently:
  - enables root login = ZT violation
  - allows weak passwords = brute-force surface
  - sets popularity-contest=true = phone-home enabled
  - drops the late_command sovereign-os marker = profile silently not set
    on installed system = sovereign-firstboot.target never fires
…the operator-named install contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESEED = REPO_ROOT / "config" / "preseed" / "sain-01.preseed.example.cfg"


def _read() -> str:
    assert PRESEED.is_file(), f"missing {PRESEED}"
    return PRESEED.read_text(encoding="utf-8")


# --- Structural ---


def test_preseed_file_exists():
    assert PRESEED.is_file(), f"missing {PRESEED}"


def test_preseed_has_locale_utf8():
    """Operator-named baseline: en_US.UTF-8 (matches cloud-init R414).
    Drift to C locale breaks non-ASCII downstream."""
    body = _read()
    assert "en_US.UTF-8" in body, (
        "preseed missing en_US.UTF-8 locale (R414 cloud-init match)"
    )


def test_preseed_clock_setup_utc():
    """Operator-named: UTC clock (reproducibility + log uniformity)."""
    body = _read()
    has_utc = (
        "clock-setup/utc boolean true" in body
        or "Etc/UTC" in body
    )
    assert has_utc, (
        "preseed missing UTC clock setup (drift = local-time-dependent "
        "log timestamps)"
    )


def test_preseed_hostname_sain01():
    """Hostname MUST match sain-01 profile baseline."""
    body = _read()
    assert "get_hostname string sain-01" in body, (
        "preseed missing 'get_hostname string sain-01' "
        "(operator-named hostname; drift = profile/host mismatch)"
    )


# --- § 8 ZT account setup ---


def test_preseed_root_login_disabled():
    """§ 8 ZT verbatim: passwd/root-login boolean false. Drift =
    root SSH/console login enabled."""
    body = _read()
    assert "passwd/root-login boolean false" in body, (
        "preseed missing 'passwd/root-login boolean false' "
        "(§ 8 ZT verbatim — no root login)"
    )


def test_preseed_creates_operator_user():
    """Operator account name = 'operator' (matches cloud-init R414)."""
    body = _read()
    assert "passwd/make-user boolean true" in body, (
        "preseed missing 'passwd/make-user boolean true'"
    )
    assert "passwd/username string operator" in body, (
        "preseed missing 'passwd/username string operator' "
        "(operator-named account; matches cloud-init)"
    )


def test_preseed_rejects_weak_password():
    """user-setup/allow-password-weak boolean false. Drift to true =
    operator's initial password can be 'password' / '1234'."""
    body = _read()
    assert "allow-password-weak boolean false" in body, (
        "preseed missing 'allow-password-weak boolean false' "
        "(operator-named password strength gate)"
    )


def test_preseed_initial_password_placeholder():
    """Initial password MUST be a clear placeholder (operator MUST
    replace). Drift to a real-looking string = operator might miss
    replacing it."""
    body = _read()
    has_placeholder = (
        "REPLACE-WITH" in body.upper()
        or "<replace" in body.lower()
    )
    assert has_placeholder, (
        "preseed initial password missing obvious placeholder "
        "(operator might ship with example password)"
    )


# --- Sovereignty deny-list ---


def test_preseed_disables_popularity_contest():
    """Sovereignty deny-list verbatim: popularity-contest opt-out."""
    body = _read()
    assert "popularity-contest" in body, (
        "preseed missing popularity-contest reference"
    )
    # Specifically, participate=false
    assert "participate boolean false" in body, (
        "preseed has popularity-contest but doesn't opt-out "
        "(sovereignty drift — phone-home enabled by default)"
    )


# --- Bootloader ---


def test_preseed_grub_install_to_nvme():
    """SAIN-01 hardware-named: grub installs to nvme0n1 (first
    NVMe). Drift to /dev/sda = wrong device on real hardware."""
    body = _read()
    assert "/dev/nvme0n1" in body, (
        "preseed missing /dev/nvme0n1 bootdev (SAIN-01 NVMe target)"
    )


def test_preseed_grub_only_debian():
    """grub-installer/only_debian boolean true (don't probe for
    other OSes; clean install). Drift = wastes time probing on
    fresh install."""
    body = _read()
    assert "grub-installer/only_debian boolean true" in body, (
        "preseed missing grub-installer/only_debian=true"
    )


# --- Package selection ---


def test_preseed_includes_ssh_server():
    """ssh-server task MUST be selected (operator's remote-management
    surface)."""
    body = _read()
    has_ssh = "ssh-server" in body
    assert has_ssh, (
        "preseed missing ssh-server task (operator can't manage "
        "post-install)"
    )


def test_preseed_no_pkgsel_upgrade():
    """pkgsel/upgrade select none — operator runs upgrade later via
    sovereign-osctl maintenance. Drift = preseed runs apt upgrade
    during install (slow + non-deterministic state)."""
    body = _read()
    assert "pkgsel/upgrade select none" in body, (
        "preseed missing 'pkgsel/upgrade select none' "
        "(drift = non-deterministic install)"
    )


def test_preseed_disables_source_repositories():
    """apt-setup/enable-source-repositories boolean false — operator
    doesn't need source repos on the installed system (apt-src for
    debugging only)."""
    body = _read()
    has_disabled = (
        "enable-source-repositories boolean false" in body
    )
    assert has_disabled, (
        "preseed missing 'enable-source-repositories boolean false' "
        "(operator-named: no source repos on installed system)"
    )


# --- Bidirectional consistency with cloud-init R414 ---


def test_late_command_sets_active_profile():
    """preseed late_command MUST write /etc/sovereign-os/active-profile
    with content sain-01 (matches cloud-init R414 write_files entry).
    Drift = installed system has no profile set = sovereign-firstboot
    can't determine which profile to apply."""
    body = _read()
    assert "/etc/sovereign-os/active-profile" in body, (
        "preseed late_command missing /etc/sovereign-os/active-profile "
        "write (drift = installed system has no profile)"
    )
    assert 'echo "sain-01"' in body or "echo sain-01" in body, (
        "preseed late_command doesn't write 'sain-01' as active profile "
        "(BIDIRECTIONAL CONSISTENCY VIOLATION with cloud-init R414)"
    )


def test_late_command_sets_active_whitelabel():
    """preseed late_command MUST write active-whitelabel=default
    (matches cloud-init R414)."""
    body = _read()
    assert "active-whitelabel" in body, (
        "preseed late_command missing active-whitelabel write "
        "(matches cloud-init R414 entry)"
    )


def test_late_command_writes_profile_env():
    """preseed MUST write SOVEREIGN_OS_PROFILE to active-profile.env
    (consumed by downstream sovereign-osctl)."""
    body = _read()
    assert "SOVEREIGN_OS_PROFILE=sain-01" in body, (
        "preseed late_command missing SOVEREIGN_OS_PROFILE=sain-01 env"
    )


def test_late_command_enables_firstboot_target():
    """sovereign-firstboot.target MUST be enabled (this fires the
    VFIO + ZFS-ARC + other ConditionFirstBoot=yes hooks). Drift =
    none of those hooks run on first boot."""
    body = _read()
    assert "systemctl enable sovereign-firstboot.target" in body, (
        "preseed late_command missing sovereign-firstboot.target enable "
        "(drift = ConditionFirstBoot=yes services never fire)"
    )


# --- Documentation ---


def test_preseed_documents_usage():
    """Operator-discovery: preseed header MUST document how to use
    (auto url=file:///preseed/sain-01.cfg or similar)."""
    body = _read()
    has_usage = (
        "preseed" in body.lower() and "url=" in body
    )
    assert has_usage, (
        "preseed missing operator-discoverable usage instructions"
    )


def test_preseed_references_canonical_debian_docs():
    """Operator-discovery: link to canonical Debian preseed reference."""
    body = _read()
    has_canonical = (
        "debian.org" in body
        or "https://" in body
    )
    assert has_canonical, (
        "preseed missing canonical Debian docs reference"
    )
