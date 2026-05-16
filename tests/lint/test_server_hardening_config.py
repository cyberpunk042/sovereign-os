"""Layer 1 lint — pin the SHAPE of sovereign-os server-hardening
config drop-ins (Round 96).

Why a lint test for IaC config content? Because the dropped-in files
ARE the IaC. If someone weakens the audit ruleset, loosens the
fail2ban jail to allow more retries, or sets Automatic-Reboot=true
in unattended-upgrades, the change must be deliberate AND visible
in a diff. This test pins load-bearing invariants so an accidental
weakening fails CI.

Add an explicit waiver comment in the file
('# HARDENING-WAIVER: <reason>') if a future change deliberately
relaxes one of these invariants.
"""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRV_DIR = REPO_ROOT / "config" / "server"


def _waived(text: str) -> bool:
    return "# HARDENING-WAIVER:" in text or "// HARDENING-WAIVER:" in text


def test_dir_present():
    assert SRV_DIR.is_dir(), f"config/server/ missing"


def test_auditd_rules_present_and_locked():
    p = SRV_DIR / "auditd.rules"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    # The ruleset MUST end with -e 2 (immutable lock) unless waived.
    if _waived(text):
        return
    assert "-e 2" in text, (
        "auditd.rules MUST set immutable mode (-e 2) so the ruleset "
        "cannot be tampered with at runtime by an attacker with root. "
        "Remove this assertion only via explicit '# HARDENING-WAIVER:'."
    )
    # Failure mode MUST be panic-on-loss (-f 2), not silent (-f 0) or just-log (-f 1)
    assert "-f 2" in text, "auditd.rules MUST set failure mode panic (-f 2)"
    # Sovereign-os surfaces MUST be watched
    for path in ("/etc/sovereign-os/", "/var/lib/sovereign-os/", "/etc/tetragon/"):
        assert path in text, f"auditd.rules missing watch on load-bearing path: {path}"
    # Privilege escalation surfaces MUST be watched
    for path in ("/etc/sudoers", "/etc/passwd", "/etc/shadow", "/etc/ssh/sshd_config"):
        assert path in text, f"auditd.rules missing watch on auth surface: {path}"


def test_fail2ban_jail_locked_to_nftables_and_systemd():
    p = SRV_DIR / "fail2ban-jail.local"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    if _waived(text):
        return
    # MUST use nftables (sovereign-os ships nftables-only, no iptables-legacy)
    assert "nftables" in text, "fail2ban jail MUST use nftables backend"
    # MUST NOT reference iptables in non-comment lines (comments may
    # mention "no iptables-legacy fallback" — that's documentation,
    # not configuration)
    non_comment_lines = [
        l for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    for line in non_comment_lines:
        assert "iptables" not in line.lower(), \
            f"fail2ban jail MUST NOT reference iptables in active config: {line!r}"
    # MUST use systemd journal (no fail2ban log file parsing)
    assert "backend  = systemd" in text or "backend = systemd" in text, \
        "fail2ban jail MUST use backend=systemd"
    # sshd MUST be enabled
    assert "[sshd]" in text and "enabled  = true" in text, \
        "[sshd] jail must be enabled"
    # Recidive (long-term repeat-offender) jail MUST be enabled
    assert "[recidive]" in text, "[recidive] jail must exist"


def test_unattended_upgrades_security_only_no_reboot():
    p = SRV_DIR / "unattended-upgrades.conf"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    if _waived(text):
        return
    # Security origin MUST be the only auto-applied one (no auto-apply of
    # main/updates without operator opt-in)
    assert "Debian-Security" in text, "must auto-apply Debian-Security"
    # The non-security origins MUST be commented out (line starting with //)
    for non_sec in ("origin=Debian,codename=${distro_codename},label=Debian",):
        # Either absent OR commented
        for line in text.splitlines():
            stripped = line.strip()
            if non_sec in stripped and not stripped.startswith("//"):
                raise AssertionError(
                    f"non-security origin '{non_sec}' is uncommented; sovereign-os "
                    f"MUST NOT auto-apply main-channel updates without operator opt-in"
                )
    # Automatic-Reboot MUST be false (sovereign-os will not surprise-restart a server)
    assert 'Automatic-Reboot "false"' in text, \
        'Unattended-Upgrade::Automatic-Reboot MUST be "false" — operator owns reboot windows'


def test_sshd_hardening_locked():
    p = SRV_DIR / "sshd.conf"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    if _waived(text):
        return
    # Helper: scan non-comment lines for an exact "key value" match
    def has_directive(key: str, expected_value: str) -> bool:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # sshd_config uses whitespace separation
            parts = stripped.split(None, 1)
            if len(parts) == 2 and parts[0] == key and parts[1].strip() == expected_value:
                return True
        return False

    # Load-bearing invariants — silent weakening would defeat every
    # other hardening layer
    assert has_directive("PermitRootLogin", "no"), \
        "sshd.conf MUST set PermitRootLogin no"
    assert has_directive("PasswordAuthentication", "no"), \
        "sshd.conf MUST set PasswordAuthentication no"
    assert has_directive("PubkeyAuthentication", "yes"), \
        "sshd.conf MUST enable PubkeyAuthentication"
    assert has_directive("AuthenticationMethods", "publickey"), \
        "sshd.conf MUST restrict AuthenticationMethods to publickey"
    assert has_directive("X11Forwarding", "no"), "sshd.conf MUST disable X11Forwarding"
    assert has_directive("PermitEmptyPasswords", "no"), \
        "sshd.conf MUST disable PermitEmptyPasswords"
    # NO sha1, NO cbc-mode ciphers in any algorithm directive
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        lower = stripped.lower()
        if any(lower.startswith(k.lower()) for k in
               ("kexalgorithms", "ciphers", "macs", "pubkeyacceptedalgorithms",
                "hostkeyalgorithms")):
            assert "sha1" not in lower, \
                f"sshd.conf MUST NOT enable sha1-based algorithm: {line!r}"
            # cbc-mode ciphers are MAC-then-encrypt — vulnerable. Modern
            # configs use AEAD (gcm, chacha20-poly1305) or etm MACs.
            if lower.startswith("ciphers"):
                assert "-cbc" not in lower, \
                    f"sshd.conf MUST NOT enable cbc-mode ciphers: {line!r}"


def test_pwquality_locked():
    p = SRV_DIR / "pwquality.conf"
    assert p.is_file(), f"missing: {p}"
    text = p.read_text()
    if _waived(text):
        return

    def get_int(key: str) -> int | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if "=" in stripped:
                k, _, v = stripped.partition("=")
                if k.strip() == key:
                    try:
                        return int(v.strip())
                    except ValueError:
                        return None
        return None

    # CIS Debian 12 § 5.4.1 minimum
    minlen = get_int("minlen")
    assert minlen is not None and minlen >= 14, \
        f"pwquality minlen MUST be ≥14 (got {minlen})"

    # All four character classes REQUIRED (negative-credit semantics:
    # value <= -1 means "must have at least 1")
    for credit in ("lcredit", "ucredit", "dcredit", "ocredit"):
        v = get_int(credit)
        assert v is not None and v <= -1, \
            f"pwquality {credit} MUST be ≤ -1 (require ≥1 of that class); got {v}"

    # enforce_for_root MUST be present (no root exemption)
    assert "enforce_for_root" in text, \
        "pwquality MUST set enforce_for_root (no root exemption from policy)"


def test_hook_present_and_executable():
    h = REPO_ROOT / "scripts" / "hooks" / "post-install" / "apply-server-hardening.sh"
    assert h.is_file(), f"missing hook: {h}"
    import os
    assert os.access(h, os.X_OK), f"hook not executable: {h}"


def test_headless_profile_registers_hook():
    import yaml
    p = REPO_ROOT / "profiles" / "headless.yaml"
    data = yaml.safe_load(p.read_text())
    hooks = (data.get("hooks") or {}).get("post_install_first_boot") or []
    ids = {h.get("id") for h in hooks}
    assert "apply-server-hardening" in ids, \
        "headless.yaml must register apply-server-hardening in post_install_first_boot"
