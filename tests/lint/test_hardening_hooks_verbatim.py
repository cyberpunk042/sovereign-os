"""R415 (E10.M59) — server + workstation hardening hooks + SDD-023 verbatim.

Extends R387-R414 operational-artifact pinning to:
  scripts/hooks/post-install/apply-server-hardening.sh
  scripts/hooks/post-install/apply-workstation-hardening.sh
  config/server/*  (5 hardening drop-ins for role-server)
  config/workstation/*

SDD-023 verbatim sovereignty posture + operator IaC bar:
  > "observable and operable, at all stages of lifecycle"

Server hardening drops in 5 config files when profile composes role-server:
  /etc/audit/rules.d/sovereign-os.rules                    — auditd
  /etc/fail2ban/jail.d/sovereign-os.local                  — fail2ban
  /etc/apt/apt.conf.d/52sovereign-os-unattended.conf       — unattended-upgrades
  /etc/ssh/sshd_config.d/50sovereign-os.conf               — SSH hardening
  /etc/security/pwquality.conf.d/50sovereign-os.conf       — password quality

Each hardening config carries operator-named contract:
  - sshd: PermitRootLogin=no + PasswordAuthentication=no + PubkeyAuthentication=yes
    (§8 ZT verbatim — drift = SSH password auth open)
  - sshd config validation BEFORE reload (sshd -t — drift = lockout
    risk during install)
  - auditd: -f 2 (panic on disk-full — drift = silent audit loss)

If a future agent silently:
  - flips PermitRootLogin to yes = root SSH access open
  - flips PasswordAuthentication to yes = §8 ZT compromise
  - drops sshd -t pre-reload check = bad config locks operator out
  - changes the 5-file drop-in list = hardening surface shrinks
…the SDD-023 sovereignty posture silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "apply-server-hardening.sh"
WS_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "apply-workstation-hardening.sh"
SERVER_CFG = REPO_ROOT / "config" / "server"
WS_CFG = REPO_ROOT / "config" / "workstation"

SERVER_HARDENING_FILES = [
    "auditd.rules",
    "fail2ban-jail.local",
    "unattended-upgrades.conf",
    "sshd.conf",
    "pwquality.conf",
]


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural: hooks + config dirs ---


def test_server_hook_exists():
    assert SERVER_HOOK.is_file(), f"missing {SERVER_HOOK}"


def test_workstation_hook_exists():
    assert WS_HOOK.is_file(), f"missing {WS_HOOK}"


def test_server_config_dir_has_all_5_drop_ins():
    """Every server hardening drop-in MUST exist. Drift removing one
    silently shrinks the §8 ZT + SDD-023 surface."""
    for name in SERVER_HARDENING_FILES:
        p = SERVER_CFG / name
        assert p.is_file(), (
            f"config/server/{name} missing (SDD-023 hardening drop-in)"
        )


# --- Server hook contract ---


def test_server_hook_detects_role_server_mixin():
    body = _read(SERVER_HOOK)
    assert "role-server" in body, (
        "apply-server-hardening.sh missing role-server mixin detection "
        "(operator-named profile-class differentiator)"
    )


def test_server_hook_skips_non_role_server_profiles():
    """Profiles NOT composing role-server MUST SKIP with explanatory
    log (operator-discoverable — not silently apply server config to
    workstations)."""
    body = _read(SERVER_HOOK)
    has_skip = (
        "SKIP" in body
        and "role-server" in body
    )
    assert has_skip, (
        "apply-server-hardening.sh missing role-server SKIP path "
        "(drift = workstation profiles get server config silently)"
    )


def test_server_hook_honors_dry_run():
    body = _read(SERVER_HOOK)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "apply-server-hardening.sh missing SOVEREIGN_OS_DRY_RUN handling"
    )


def test_server_hook_validates_sshd_before_reload():
    """OPERATOR-CRITICAL: 'sshd -t' MUST run BEFORE 'systemctl reload ssh'.
    Drift = bad sshd_config locks operator out of their own system."""
    body = _read(SERVER_HOOK)
    # 'sshd -t' must appear AND must precede systemctl reload ssh
    sshd_t_pos = body.find("sshd -t")
    reload_pos = body.find("reload ssh")
    assert sshd_t_pos != -1, (
        "apply-server-hardening.sh missing 'sshd -t' validation "
        "(operator-critical: bad sshd_config locks operator out)"
    )
    assert reload_pos != -1, (
        "apply-server-hardening.sh missing 'reload ssh' — no service "
        "restart path"
    )
    assert sshd_t_pos < reload_pos, (
        "apply-server-hardening.sh has 'reload ssh' BEFORE 'sshd -t' "
        "validation (operator-critical ordering — lock-out risk)"
    )


def test_server_hook_supports_dest_prefix():
    """Operator can apply hardening to chroot/container/image tree
    via SOVEREIGN_OS_HARDENING_DEST_PREFIX. Drift = no offline-apply
    path = hardening can only be applied to running system."""
    body = _read(SERVER_HOOK)
    assert "SOVEREIGN_OS_HARDENING_DEST_PREFIX" in body, (
        "apply-server-hardening.sh missing DEST_PREFIX support "
        "(operator can't apply to image/chroot/container)"
    )


def test_server_hook_idempotent_via_cmp():
    """Operator-verbatim IaC bar: idempotent re-run. Hook MUST cmp
    source against destination to avoid no-op churn (drift = every
    re-run touches mtimes, breaks cache layer hashes)."""
    body = _read(SERVER_HOOK)
    assert "cmp -s" in body or "cmp " in body, (
        "apply-server-hardening.sh missing cmp idempotency check "
        "(drift = every re-run touches mtimes)"
    )


def test_server_hook_emits_metric():
    body = _read(SERVER_HOOK)
    assert "sovereign_os_post_install_server_hardening" in body, (
        "apply-server-hardening.sh missing per-result metric (SDD-016)"
    )


# --- Workstation hook contract ---


def test_workstation_hook_detects_role_workstation_mixin():
    body = _read(WS_HOOK)
    assert "role-workstation" in body, (
        "apply-workstation-hardening.sh missing role-workstation "
        "mixin detection (operator-named profile-class differentiator)"
    )


def test_workstation_hook_skips_non_role_workstation_profiles():
    body = _read(WS_HOOK)
    has_skip = (
        "SKIP" in body
        and "role-workstation" in body
    )
    assert has_skip, (
        "apply-workstation-hardening.sh missing role-workstation SKIP"
    )


def test_workstation_hook_honors_dry_run():
    body = _read(WS_HOOK)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "apply-workstation-hardening.sh missing SOVEREIGN_OS_DRY_RUN"
    )


# --- SDD-023 + §8 ZT verbatim in sshd.conf ---


def test_sshd_conf_permit_root_login_no():
    """§8 ZT verbatim: PermitRootLogin=no. Drift = root SSH open."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"PermitRootLogin\s+no\b", body), (
        "config/server/sshd.conf missing 'PermitRootLogin no' "
        "(§8 ZT verbatim — drift = root SSH access open)"
    )


def test_sshd_conf_password_authentication_no():
    """§8 ZT verbatim: PasswordAuthentication=no (SSH-key-only).
    Drift = SSH password auth open = brute-force attack surface."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"PasswordAuthentication\s+no\b", body), (
        "config/server/sshd.conf missing 'PasswordAuthentication no' "
        "(§8 ZT verbatim — SSH-key-only enforcement)"
    )


def test_sshd_conf_pubkey_authentication_yes():
    """§8 ZT verbatim: PubkeyAuthentication=yes (the only allowed
    auth method)."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"PubkeyAuthentication\s+yes\b", body), (
        "config/server/sshd.conf missing 'PubkeyAuthentication yes'"
    )


def test_sshd_conf_authentication_methods_publickey_only():
    """§8 ZT verbatim: AuthenticationMethods=publickey. Drift to
    'publickey,password' silently re-enables password auth."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"AuthenticationMethods\s+publickey\b", body), (
        "config/server/sshd.conf missing 'AuthenticationMethods "
        "publickey' (drift re-enables password auth silently)"
    )


def test_sshd_conf_permit_empty_passwords_no():
    """Defense-in-depth: PermitEmptyPasswords=no (even if password
    auth somehow on, empty-password login blocked)."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"PermitEmptyPasswords\s+no\b", body), (
        "config/server/sshd.conf missing 'PermitEmptyPasswords no' "
        "(defense-in-depth)"
    )


def test_sshd_conf_no_x11_forwarding():
    """§8 ZT default: X11Forwarding=no. Drift = X11-over-SSH attack
    surface opened by default."""
    body = _read(SERVER_CFG / "sshd.conf")
    assert re.search(r"X11Forwarding\s+no\b", body), (
        "config/server/sshd.conf missing 'X11Forwarding no' (§8 ZT)"
    )


def test_sshd_conf_max_auth_tries_capped():
    """MaxAuthTries should be ≤ 6 (default Debian 6). Cap reduces
    brute-force surface; fail2ban handles repeat IPs."""
    body = _read(SERVER_CFG / "sshd.conf")
    m = re.search(r"MaxAuthTries\s+(\d+)\b", body)
    assert m, (
        "config/server/sshd.conf missing MaxAuthTries"
    )
    n = int(m.group(1))
    assert n <= 6, (
        f"config/server/sshd.conf MaxAuthTries={n} > 6 "
        f"(brute-force surface exposure; cap drift)"
    )


# --- Auditd panic-on-full ---


def test_auditd_rules_panic_on_disk_full():
    """SDD-023 verbatim: '-f 2' = panic on disk full (audit silence
    is worse than denial of service). Drift to -f 1 / -f 0 silently
    loses audit events."""
    body = _read(SERVER_CFG / "auditd.rules")
    has_panic = re.search(r"^-f\s+2\b", body, re.M)
    assert has_panic, (
        "config/server/auditd.rules missing '-f 2' (SDD-023 verbatim — "
        "panic on disk-full; drift = silent audit loss)"
    )


def test_auditd_rules_buffer_size_sufficient():
    """SDD-023 + operator-named server-class: -b 16384 (≥ 8192 Debian
    default). Drift to a smaller buffer = audit drops under burst."""
    body = _read(SERVER_CFG / "auditd.rules")
    m = re.search(r"^-b\s+(\d+)\b", body, re.M)
    assert m, (
        "config/server/auditd.rules missing '-b <size>' buffer "
        "(operator-named server-class baseline)"
    )
    size = int(m.group(1))
    assert size >= 8192, (
        f"config/server/auditd.rules -b {size} < 8192 (drift below "
        f"Debian default; audit drops under burst)"
    )
