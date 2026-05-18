"""R414 (E10.M58) — cloud-init user-data templates operator-verbatim lint.

Extends R387-R413 operational-artifact pinning to:
  config/cloud-init/<profile>.user-data.example.yaml  (5 profiles)

Q-018 verbatim implementation: cloud-init user-data templates pre-supply
answers to the first-login assistant so operator can boot unattended.

Master spec invariants per-profile:
  - sain-01      — full hostname + Trinity workloads
  - developer    — dev-friendly toolchain pre-installed
  - headless     — bare-metal server, no GUI
  - minimal      — smallest viable footprint
  - old-workstation — degraded-hardware profile

Cross-template invariants (every cloud-init MUST):
  - First line: #cloud-config (cloud-init schema requirement)
  - YAML parses cleanly
  - hostname declared (operator-named identity at install time)
  - users[].sudo present (operator-discoverable elevation path)
  - users[].lock_passwd: true (SSH-key-only by default = §8 ZT posture)
  - write_files writes /etc/sovereign-os/active-profile (matches the
    profile id in the filename) — bidirectional consistency between
    filename and YAML content
  - /etc/sovereign-os/active-whitelabel: 'default' (operator-named
    baseline whitelabel)

If a future agent silently:
  - drops #cloud-config header = cloud-init refuses to parse the file
    = unattended install silently falls back to interactive prompts
  - changes active-profile content to mismatch the filename = installer
    boots with the wrong profile = wrong hardware tunings applied
  - removes lock_passwd: true = SSH password auth open by default =
    §8 ZT compromise
…unattended install + ZT posture silently break.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CLOUD_INIT_DIR = REPO_ROOT / "config" / "cloud-init"

EXPECTED_PROFILES = [
    "sain-01",
    "developer",
    "headless",
    "minimal",
    "old-workstation",
]


def _path(profile_id: str) -> Path:
    return CLOUD_INIT_DIR / f"{profile_id}.user-data.example.yaml"


def _read_text(profile_id: str) -> str:
    p = _path(profile_id)
    assert p.is_file(), f"missing cloud-init template: {p}"
    return p.read_text(encoding="utf-8")


def _load_yaml(profile_id: str) -> dict:
    """Load YAML body, skipping the #cloud-config first-line marker."""
    text = _read_text(profile_id)
    # cloud-init's #cloud-config is a YAML comment, so yaml.safe_load
    # handles it as-is.
    return yaml.safe_load(text) or {}


def test_all_five_templates_exist():
    """Operator-named 5-profile set: each MUST have a user-data
    template. Drift removing one = no unattended install path for
    that profile."""
    for pid in EXPECTED_PROFILES:
        assert _path(pid).is_file(), (
            f"cloud-init template missing for profile {pid!r}: "
            f"{_path(pid)} (no unattended install path)"
        )


def test_every_template_starts_with_cloud_config_header():
    """Cloud-init schema verbatim: '#cloud-config' MUST be the first
    line. Without it, cloud-init refuses to parse (and unattended
    install silently falls back to interactive prompts)."""
    for pid in EXPECTED_PROFILES:
        text = _read_text(pid)
        first_line = text.split("\n", 1)[0].strip()
        assert first_line == "#cloud-config", (
            f"cloud-init template for {pid} doesn't start with "
            f"'#cloud-config' (cloud-init schema requirement — drift "
            f"= unattended install silently fails)"
        )


def test_every_template_parses_as_yaml():
    """Every template MUST parse as valid YAML. Drift to syntax error
    breaks the entire unattended install path."""
    for pid in EXPECTED_PROFILES:
        try:
            _load_yaml(pid)
        except yaml.YAMLError as e:
            raise AssertionError(
                f"cloud-init template for {pid} has YAML syntax error: {e}"
            )


def test_every_template_has_hostname():
    """Every template MUST declare hostname (operator-named identity
    at install time)."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        assert data.get("hostname"), (
            f"cloud-init template for {pid} missing hostname "
            f"(operator-named install-time identity)"
        )


def test_every_template_has_users_with_sudo():
    """Every template MUST define a sudo-capable user (operator-
    discoverable elevation path). Drift = post-install operator can't
    privilege-escalate without console fallback."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        users = data.get("users") or []
        assert users and isinstance(users, list), (
            f"cloud-init template for {pid} missing users[] list"
        )
        # Find at least one user with sudo: ALL=(ALL)...
        has_sudo = any(
            isinstance(u, dict) and u.get("sudo")
            for u in users
        )
        assert has_sudo, (
            f"cloud-init template for {pid} has no sudo-capable user "
            f"(operator-discoverable elevation path missing)"
        )


def test_every_template_locks_password_by_default():
    """§8 Zero-Trust posture: SSH-key-only by default. lock_passwd:
    true on the operator user. Drift = SSH password auth open at
    install time = ZT violation."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        users = data.get("users") or []
        # At least one user MUST have lock_passwd: true (operator's
        # ZT default; password-enabled users would override this)
        has_locked = any(
            isinstance(u, dict) and u.get("lock_passwd") is True
            for u in users
        )
        assert has_locked, (
            f"cloud-init template for {pid} doesn't lock_passwd: true "
            f"on any user (§8 ZT — SSH-key-only by default)"
        )


def test_active_profile_matches_filename():
    """Bidirectional consistency: every template MUST write
    /etc/sovereign-os/active-profile with content matching the
    template's filename profile id. Drift = installer boots with
    wrong profile (e.g., sain-01.user-data.example.yaml installs
    'minimal' profile)."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        write_files = data.get("write_files") or []
        # Find the active-profile file entry
        ap_entry = next(
            (f for f in write_files
             if isinstance(f, dict)
             and f.get("path") == "/etc/sovereign-os/active-profile"),
            None,
        )
        assert ap_entry, (
            f"cloud-init template for {pid} missing "
            f"/etc/sovereign-os/active-profile write_files entry"
        )
        content = (ap_entry.get("content") or "").strip()
        assert content == pid, (
            f"cloud-init template for {pid} writes active-profile "
            f"content={content!r} (bidirectional consistency: filename "
            f"profile {pid!r} ↔ active-profile content)"
        )


def test_every_template_sets_default_whitelabel():
    """Operator-named baseline: active-whitelabel = 'default'.
    Drift here = wrong whitelabel applied at install. (Operator-
    specific whitelabels are operator-named and not in repo —
    'default' is the only safe baseline.)"""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        write_files = data.get("write_files") or []
        wl_entry = next(
            (f for f in write_files
             if isinstance(f, dict)
             and f.get("path") == "/etc/sovereign-os/active-whitelabel"),
            None,
        )
        assert wl_entry, (
            f"cloud-init template for {pid} missing "
            f"/etc/sovereign-os/active-whitelabel write_files entry"
        )
        assert (wl_entry.get("content") or "").strip() == "default", (
            f"cloud-init template for {pid} active-whitelabel "
            f"!= 'default' (operator-named baseline)"
        )


def test_every_template_documents_noCloud_usage():
    """Operator-discovery: each template SHOULD reference the NoCloud
    datasource (USB stick, ISO, or HTTP at first boot). Drift =
    operator can't tell HOW to use the template."""
    for pid in EXPECTED_PROFILES:
        text = _read_text(pid)
        has_doc = (
            "NoCloud" in text
            or "user-data" in text.lower()
            or "unattended" in text.lower()
        )
        assert has_doc, (
            f"cloud-init template for {pid} missing NoCloud / "
            f"unattended-install documentation (operator-discovery)"
        )


def test_active_profile_env_file_present():
    """Operator-named env path: /etc/sovereign-os/active-profile.env
    MUST be written with SOVEREIGN_OS_PROFILE= line (env var that
    downstream sovereign-osctl reads)."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        write_files = data.get("write_files") or []
        env_entry = next(
            (f for f in write_files
             if isinstance(f, dict)
             and f.get("path") == "/etc/sovereign-os/active-profile.env"),
            None,
        )
        assert env_entry, (
            f"cloud-init template for {pid} missing "
            f"/etc/sovereign-os/active-profile.env write_files entry"
        )
        env_content = env_entry.get("content") or ""
        assert "SOVEREIGN_OS_PROFILE" in env_content, (
            f"cloud-init template for {pid} active-profile.env missing "
            f"SOVEREIGN_OS_PROFILE= line"
        )


def test_ssh_key_placeholder_clearly_marked():
    """The ssh_authorized_keys placeholder MUST be obviously a
    placeholder ('<REPLACE-WITH-...>' or similar). Drift to a real-
    looking key string = operator might miss replacing it = installed
    system with example template key."""
    for pid in EXPECTED_PROFILES:
        text = _read_text(pid)
        if "ssh_authorized_keys" not in text:
            continue  # template doesn't declare keys (acceptable)
        has_placeholder_marker = (
            "REPLACE" in text.upper()
            or "<your-" in text.lower()
            or "example.com" in text
            or "example@" in text
            or "operator@example" in text
        )
        assert has_placeholder_marker, (
            f"cloud-init template for {pid} has ssh_authorized_keys "
            f"without an obvious placeholder marker "
            f"(operator might miss replacing it)"
        )


def test_locale_set_to_utf8():
    """Operator-named locale: UTF-8 baseline (the whole sovereign-os
    stack assumes UTF-8). Drift to POSIX/C locale breaks downstream
    Python (yaml + json with non-ASCII content) silently."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        locale = data.get("locale", "")
        if locale:
            assert "UTF-8" in locale or "utf8" in locale.lower(), (
                f"cloud-init template for {pid} locale={locale!r} "
                f"isn't UTF-8 (operator-named baseline; drift breaks "
                f"non-ASCII content downstream)"
            )


def test_timezone_set_to_utc():
    """Operator-discoverable + reproducibility-friendly: UTC default.
    Drift to a local timezone makes log timestamps profile-dependent."""
    for pid in EXPECTED_PROFILES:
        data = _load_yaml(pid)
        tz = data.get("timezone", "")
        if tz:
            assert tz == "UTC", (
                f"cloud-init template for {pid} timezone={tz!r} != UTC "
                f"(operator-named reproducibility-friendly default)"
            )
