"""R417 (E10.M61) — profile mixin operator-verbatim content lint.

Extends R387-R416 operational-artifact pinning to:
  profiles/mixins/*.yaml  (6 mixins composing into profiles)

R385 covered config example files broadly. R417 covers the MIXIN
COMPOSITION layer that produces effective profiles.

Operator-named 6-mixin set:
  observability-tier-1   — basic observability (R171 + SDD-016)
  role-developer         — dev toolchain (compilers, debuggers)
  role-headless          — VM/embedded minimal baseline
  role-server            — bare-metal server hardening surface
  role-workstation       — interactive GPU-bearing host
  whitelabel-default     — default whitelabel composition

Per-mixin invariants:
  - schema_version pinned (1.0.0)
  - mixin.id matches filename (e.g., 'role-server' ↔ role-server.yaml)
  - mixin.description non-empty (operator-discovery context)
  - packages.deny includes operator-named phone-home + GUI bits
    for role-server / role-headless (sovereignty deny-list)
  - role-server includes auditd + fail2ban + unattended-upgrades
    (matches the apply-server-hardening.sh drop-ins from R415)
  - role-workstation differs from role-headless (vim + build-essential
    + podman vs minimal base — operator-named differentiator)

If a future agent silently:
  - removes auditd from role-server packages = R415 apply-server-
    hardening.sh drops auditd rules to a system without auditd installed
  - adds a phone-home package to role-server.packages.deny = sovereignty
    violation
  - drifts mixin.id from filename = composition reference fails silently
…the mixin composition layer silently breaks.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MIXINS_DIR = REPO_ROOT / "profiles" / "mixins"

EXPECTED_MIXINS = [
    "observability-tier-1",
    "role-developer",
    "role-headless",
    "role-server",
    "role-workstation",
    "whitelabel-default",
]


def _load_mixin(mixin_id: str) -> dict:
    p = MIXINS_DIR / f"{mixin_id}.yaml"
    assert p.is_file(), f"missing mixin: {p}"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


# --- Structural ---


def test_all_six_mixins_exist():
    for mid in EXPECTED_MIXINS:
        p = MIXINS_DIR / f"{mid}.yaml"
        assert p.is_file(), (
            f"profile mixin missing: {p} (operator-named 6-mixin set)"
        )


def test_mixin_count_matches_expected():
    actual = sorted(p.stem for p in MIXINS_DIR.glob("*.yaml"))
    expected = sorted(EXPECTED_MIXINS)
    assert actual == expected, (
        f"profiles/mixins/ drift: actual={actual} vs expected={expected}"
    )


def test_every_mixin_has_schema_version():
    for mid in EXPECTED_MIXINS:
        data = _load_mixin(mid)
        assert data.get("schema_version") == "1.0.0", (
            f"mixin {mid}.yaml missing schema_version: 1.0.0 "
            f"(operator-named composition contract pin)"
        )


def test_every_mixin_id_matches_filename():
    """Bidirectional consistency: mixin.id MUST equal filename stem.
    Drift = composition reference fails silently when profile lists
    the mixin id."""
    for mid in EXPECTED_MIXINS:
        data = _load_mixin(mid)
        m = data.get("mixin") or {}
        assert m.get("id") == mid, (
            f"mixin {mid}.yaml has mixin.id={m.get('id')!r} != "
            f"filename {mid!r} (bidirectional consistency violation; "
            f"profile composition silently fails)"
        )


def test_every_mixin_has_description():
    for mid in EXPECTED_MIXINS:
        data = _load_mixin(mid)
        m = data.get("mixin") or {}
        desc = (m.get("description") or "").strip()
        assert desc, (
            f"mixin {mid}.yaml missing mixin.description "
            f"(operator-discovery context)"
        )


# --- role-server contract (matches R415 apply-server-hardening drop-ins) ---


def test_role_server_packages_include_auditd():
    """R415 apply-server-hardening.sh drops /etc/audit/rules.d/...
    auditd MUST be installed by the same role-server mixin (else the
    rules drop into a system without the auditd daemon)."""
    data = _load_mixin("role-server")
    pkgs = (data.get("packages") or {}).get("role", {}).get("server") or []
    assert "auditd" in pkgs, (
        "role-server.yaml packages missing 'auditd' "
        "(R415 apply-server-hardening.sh expects it installed; "
        "drift = audit rules drop on system without daemon)"
    )


def test_role_server_packages_include_fail2ban():
    data = _load_mixin("role-server")
    pkgs = (data.get("packages") or {}).get("role", {}).get("server") or []
    assert "fail2ban" in pkgs, (
        "role-server.yaml packages missing 'fail2ban' "
        "(R415 apply-server-hardening.sh expects it installed)"
    )


def test_role_server_packages_include_unattended_upgrades():
    data = _load_mixin("role-server")
    pkgs = (data.get("packages") or {}).get("role", {}).get("server") or []
    assert "unattended-upgrades" in pkgs, (
        "role-server.yaml packages missing 'unattended-upgrades' "
        "(R415 apply-server-hardening.sh expects it installed)"
    )


def test_role_server_packages_include_chrony():
    """Operator-named: chrony for time sync (critical for any server).
    Drift loses time-correctness = audit log timestamps unreliable."""
    data = _load_mixin("role-server")
    pkgs = (data.get("packages") or {}).get("role", {}).get("server") or []
    assert "chrony" in pkgs, (
        "role-server.yaml packages missing 'chrony' "
        "(operator-named time-sync — audit timestamp correctness)"
    )


def test_role_server_packages_include_openssh_server():
    """role-server MUST include openssh-server (operator's primary
    remote-management surface). Drift = no SSH = server unmanageable."""
    data = _load_mixin("role-server")
    base = (data.get("packages") or {}).get("base") or []
    role = (data.get("packages") or {}).get("role", {}).get("server") or []
    pkgs = base + role
    assert "openssh-server" in pkgs, (
        "role-server.yaml missing openssh-server (no SSH = unmanageable)"
    )


# --- Sovereignty deny-list (operator-named phone-home + GUI) ---


def test_role_server_denies_phone_home_packages():
    """Operator sovereignty mandate: phone-home defaults must be denied.
    Each operator-named package MUST appear in role-server.packages.deny."""
    data = _load_mixin("role-server")
    deny = (data.get("packages") or {}).get("deny") or []
    operator_named_phone_home = [
        "popularity-contest",   # Debian usage telemetry
        "apport",               # Ubuntu crash reporter
        "whoopsie",             # Ubuntu error tracker
        "snapd",                # Canonical store
        "ubuntu-advantage-tools",  # Canonical advantage
    ]
    missing = [p for p in operator_named_phone_home if p not in deny]
    assert not missing, (
        f"role-server.yaml deny-list missing phone-home packages "
        f"{missing} (operator sovereignty violation)"
    )


def test_role_server_denies_gui_packages():
    """Headless server MUST deny GUI bits (X server, GDM, plymouth
    themes). Drift = headless server pulls X11 dependency tree."""
    data = _load_mixin("role-server")
    deny = (data.get("packages") or {}).get("deny") or []
    gui_packages = ["xserver-common", "gdm3", "plymouth-themes"]
    missing = [p for p in gui_packages if p not in deny]
    assert not missing, (
        f"role-server.yaml deny-list missing GUI packages {missing} "
        f"(headless server drift — pulls X11)"
    )


def test_role_server_denies_network_manager():
    """Operator-named choice: server-class uses systemd-networkd (R401
    §8.1). NetworkManager drift = networkd config silently ignored."""
    data = _load_mixin("role-server")
    deny = (data.get("packages") or {}).get("deny") or []
    assert "network-manager" in deny, (
        "role-server.yaml deny missing 'network-manager' "
        "(R401 §8.1 — systemd-networkd is the operator-named choice)"
    )


# --- role-workstation differentiator ---


def test_role_workstation_includes_podman():
    """Operator-named differentiator: workstation has container runtime."""
    data = _load_mixin("role-workstation")
    base = (data.get("packages") or {}).get("base") or []
    workstation = (data.get("packages") or {}).get(
        "role", {}).get("workstation") or []
    pkgs = base + workstation
    assert "podman" in pkgs, (
        "role-workstation.yaml missing podman (operator-named "
        "workstation differentiator — container runtime)"
    )


# --- role-developer differentiator ---


def test_role_developer_id_matches_filename():
    """role-developer mixin ID consistency."""
    data = _load_mixin("role-developer")
    m = data.get("mixin") or {}
    assert m.get("id") == "role-developer", (
        f"role-developer.yaml mixin.id mismatch (got {m.get('id')!r})"
    )


# --- observability-tier-1 ---


def test_observability_tier_1_id():
    data = _load_mixin("observability-tier-1")
    m = data.get("mixin") or {}
    assert m.get("id") == "observability-tier-1", (
        "observability-tier-1.yaml mixin.id mismatch"
    )


# --- whitelabel-default ---


def test_whitelabel_default_id():
    data = _load_mixin("whitelabel-default")
    m = data.get("mixin") or {}
    assert m.get("id") == "whitelabel-default", (
        "whitelabel-default.yaml mixin.id mismatch"
    )


# --- Bidirectional consistency: hooks referenced ↔ scripts exist ---


def test_role_server_hook_scripts_exist():
    """role-server may declare hooks (e.g., friction-audit-runtime).
    Every referenced hook script MUST exist on disk. Drift = profile
    composes a mixin that references missing scripts = install fails."""
    data = _load_mixin("role-server")
    hooks_section = data.get("hooks") or {}
    for phase, hooks in hooks_section.items():
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            script = hook.get("script")
            if script:
                p = REPO_ROOT / script
                assert p.is_file(), (
                    f"role-server.yaml hooks.{phase} references "
                    f"missing script: {script}"
                )


def test_no_mixin_has_phone_home_in_required_packages():
    """Operator sovereignty: phone-home packages MUST NOT appear in
    ANY mixin's required package list (sovereignty floor enforcement).
    Drift = mixin silently installs phone-home (defeating deny-list)."""
    phone_home = [
        "popularity-contest",
        "apport",
        "whoopsie",
        "snapd",
    ]
    for mid in EXPECTED_MIXINS:
        data = _load_mixin(mid)
        pkgs_section = data.get("packages") or {}
        # Flatten all package keys EXCEPT 'deny' (where phone-home BELONGS)
        all_pkgs: list[str] = []
        for key, val in pkgs_section.items():
            if key == "deny":
                continue
            if isinstance(val, list):
                all_pkgs.extend(val)
            elif isinstance(val, dict):
                for v in val.values():
                    if isinstance(v, list):
                        all_pkgs.extend(v)
        for ph in phone_home:
            assert ph not in all_pkgs, (
                f"mixin {mid}.yaml has phone-home package {ph!r} in "
                f"required packages (sovereignty violation — phone-home "
                f"belongs only in deny:)"
            )
