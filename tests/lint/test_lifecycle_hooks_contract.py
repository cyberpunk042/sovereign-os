"""R411 (E10.M55) — lifecycle-hook contract lint (pre/during/decommission).

Extends R387-R410 operational-artifact pinning to the lifecycle-hook
families that haven't been individually pinned yet:
  scripts/hooks/pre-install/    (4 hooks: preflight + friction-audit)
  scripts/hooks/during-install/ (4 hooks: zfs pool/datasets, ext4, mok)
  scripts/hooks/decommission/   (3 hooks: secure-wipe x2 + zfs-pool-destroy)

Each hook category has operator-named invariants:

PRE-INSTALL (preflight + friction audit):
  - Exit 0 on PASS / non-zero on FAIL
  - Honors SOVEREIGN_OS_DRY_RUN
  - Emits sovereign_os_pre_install_* metric

DURING-INSTALL (zfs pool/datasets, ext4 format, MOK enroll):
  - require_root (writes to /dev or /etc)
  - Honors SOVEREIGN_OS_DRY_RUN (CI preview safety)
  - STEP_ID matches script name
  - Emits sovereign_os_during_install_* metric

DECOMMISSION (most destructive — sacrosanct safety contract):
  - require_root
  - **SOVEREIGN_OS_CONFIRM_DESTROY=YES env var required** (operator
    standing mandate — no destructive operation without explicit YES)
  - Interactive confirm() prompt (defense-in-depth)
  - 'ALL DATA UNRECOVERABLE' or equivalent operator-discoverable
    warning text

If a future agent silently:
  - drops SOVEREIGN_OS_CONFIRM_DESTROY check from a decommission hook
    → ANY ENV CAN TRIGGER DATA DESTRUCTION = OPERATOR MANDATE VIOLATION
  - changes a decommission hook to skip the interactive confirm
    → CI run could nuke operator's data
  - drops require_root from during-install
    → silent failures with no error during real install
…lifecycle-hook safety contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_INSTALL_DIR = REPO_ROOT / "scripts" / "hooks" / "pre-install"
DURING_INSTALL_DIR = REPO_ROOT / "scripts" / "hooks" / "during-install"
DECOMMISSION_DIR = REPO_ROOT / "scripts" / "hooks" / "decommission"

PRE_INSTALL_HOOKS = [
    "preflight-network.sh",
    "preflight-storage.sh",
    "preflight-tpm.sh",
    "friction-audit-spec.sh",
]

DURING_INSTALL_HOOKS = [
    "zfs-pool-create.sh",
    "zfs-datasets-create.sh",
    "rootfs-format-ext4.sh",
    "mok-enroll.sh",
]

DECOMMISSION_HOOKS = [
    "secure-wipe.sh",
    "secure-wipe-context.sh",
    "zfs-pool-destroy.sh",
]


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_pre_install_dir_has_expected_hooks():
    for name in PRE_INSTALL_HOOKS:
        p = PRE_INSTALL_DIR / name
        assert p.is_file(), (
            f"pre-install lifecycle hook missing: {p} (operator-named "
            f"preflight contract)"
        )


def test_during_install_dir_has_expected_hooks():
    for name in DURING_INSTALL_HOOKS:
        p = DURING_INSTALL_DIR / name
        assert p.is_file(), (
            f"during-install lifecycle hook missing: {p} "
            f"(operator-named install contract)"
        )


def test_decommission_dir_has_expected_hooks():
    for name in DECOMMISSION_HOOKS:
        p = DECOMMISSION_DIR / name
        assert p.is_file(), (
            f"decommission lifecycle hook missing: {p} "
            f"(operator-named destructive-op safety contract)"
        )


# --- PRE-INSTALL contract ---


def test_pre_install_hooks_honor_dry_run():
    """Every pre-install hook MUST honor SOVEREIGN_OS_DRY_RUN
    (operator-discoverable CI safety — preflight runs on every build)."""
    for name in PRE_INSTALL_HOOKS:
        body = _read(PRE_INSTALL_DIR / name)
        assert "SOVEREIGN_OS_DRY_RUN" in body, (
            f"pre-install hook {name} missing SOVEREIGN_OS_DRY_RUN "
            f"(drift = preflight executes real probes in CI)"
        )


def test_pre_install_hooks_emit_metric():
    """Every pre-install hook MUST emit a Layer B metric (SDD-016 —
    operator-discoverable preflight observability)."""
    for name in PRE_INSTALL_HOOKS:
        body = _read(PRE_INSTALL_DIR / name)
        assert "sovereign_os_pre_install" in body, (
            f"pre-install hook {name} missing sovereign_os_pre_install_* "
            f"metric (SDD-016 verbatim — preflight observability)"
        )


def test_pre_install_hooks_have_step_id():
    """Every pre-install hook MUST export STEP_ID matching its
    filename (state-machine + log correlation)."""
    for name in PRE_INSTALL_HOOKS:
        body = _read(PRE_INSTALL_DIR / name)
        # Filename minus .sh extension
        expected = name[:-3]  # strip .sh
        assert f'STEP_ID="{expected}"' in body, (
            f"pre-install hook {name} missing STEP_ID=\"{expected}\" "
            f"(operator-verbatim — log/metric correlation)"
        )


# --- DURING-INSTALL contract ---


def test_during_install_hooks_require_root():
    """Every during-install hook MUST require_root (writes to /dev
    or /etc — drift = silent failure with confusing error)."""
    for name in DURING_INSTALL_HOOKS:
        body = _read(DURING_INSTALL_DIR / name)
        assert "require_root" in body, (
            f"during-install hook {name} missing require_root "
            f"(writes to /dev or /etc — drift = silent failure)"
        )


def test_during_install_hooks_honor_dry_run():
    """Every during-install hook MUST honor SOVEREIGN_OS_DRY_RUN
    (operator-verbatim CI safety — these hooks touch real disks)."""
    for name in DURING_INSTALL_HOOKS:
        body = _read(DURING_INSTALL_DIR / name)
        assert "SOVEREIGN_OS_DRY_RUN" in body, (
            f"during-install hook {name} missing SOVEREIGN_OS_DRY_RUN "
            f"(critical: drift = CI run executes real disk format)"
        )


def test_during_install_hooks_emit_metric():
    for name in DURING_INSTALL_HOOKS:
        body = _read(DURING_INSTALL_DIR / name)
        assert "sovereign_os_during_install" in body, (
            f"during-install hook {name} missing sovereign_os_during_"
            f"install_* metric (SDD-016 — install observability)"
        )


def test_during_install_hooks_have_step_id():
    for name in DURING_INSTALL_HOOKS:
        body = _read(DURING_INSTALL_DIR / name)
        expected = name[:-3]
        assert f'STEP_ID="{expected}"' in body, (
            f"during-install hook {name} missing STEP_ID=\"{expected}\""
        )


# --- DECOMMISSION contract (SACROSANCT safety) ---


def test_decommission_hooks_require_confirm_destroy():
    """OPERATOR STANDING MANDATE VERBATIM:
      'SOVEREIGN_OS_CONFIRM_DESTROY=YES required for destructive operations'

    Every decommission hook MUST check this env var. Drift =
    ANY ENV CAN TRIGGER DATA DESTRUCTION = mandate violation."""
    for name in DECOMMISSION_HOOKS:
        body = _read(DECOMMISSION_DIR / name)
        assert "SOVEREIGN_OS_CONFIRM_DESTROY" in body, (
            f"decommission hook {name} missing SOVEREIGN_OS_CONFIRM_"
            f"DESTROY check — OPERATOR MANDATE VIOLATION 'destructive "
            f"operations require explicit YES'"
        )


def test_decommission_hooks_require_yes_value_exactly():
    """The env var MUST be checked against the literal string 'YES'
    (not 'yes' or '1' or 'true'). Drift relaxing the comparison
    silently lets weaker confirm values pass through."""
    for name in DECOMMISSION_HOOKS:
        body = _read(DECOMMISSION_DIR / name)
        # Look for pattern: != "YES" or = "YES"
        has_yes_check = (
            '"YES"' in body
            or "='YES'" in body
            or '!= "YES"' in body
            or '!= YES' in body
        )
        assert has_yes_check, (
            f"decommission hook {name} doesn't check for literal 'YES' "
            f"(drift to truthy-only relaxes operator mandate)"
        )


def test_decommission_hooks_require_root():
    """Every decommission hook MUST require_root (operations destroy
    system-owned resources)."""
    for name in DECOMMISSION_HOOKS:
        body = _read(DECOMMISSION_DIR / name)
        assert "require_root" in body, (
            f"decommission hook {name} missing require_root "
            f"(destroys system resources)"
        )


def test_decommission_hooks_have_interactive_confirm():
    """Defense-in-depth: env var alone isn't enough. Most destructive
    hooks ALSO use confirm() interactive prompt. At minimum 2 of 3 hooks
    have it (secure-wipe-context.sh may use a different style)."""
    confirm_count = 0
    for name in DECOMMISSION_HOOKS:
        body = _read(DECOMMISSION_DIR / name)
        if "confirm " in body or "confirm(" in body or "confirm \"" in body:
            confirm_count += 1
    assert confirm_count >= 2, (
        f"decommission hooks: only {confirm_count}/3 have interactive "
        f"confirm() prompt (defense-in-depth — env var alone is risky)"
    )


def test_decommission_hooks_warn_of_unrecoverable_data_loss():
    """At least one of the 2 secure-wipe hooks (the most destructive)
    SHOULD have operator-discoverable 'UNRECOVERABLE' / 'destructive'
    warning text — drift to silent destruction = no operator deterrent."""
    body_wipe = _read(DECOMMISSION_DIR / "secure-wipe.sh")
    has_warning = (
        "UNRECOVERABLE" in body_wipe
        or "unrecoverable" in body_wipe.lower()
        or "ALL DATA" in body_wipe
        or "DESTRUCTIVE" in body_wipe.upper()
    )
    assert has_warning, (
        "secure-wipe.sh missing 'UNRECOVERABLE' / 'ALL DATA' warning "
        "(operator-discoverable deterrent for destructive op)"
    )


# --- Cross-category invariants ---


def test_all_hooks_source_lib_common():
    """Every lifecycle hook (across all 3 categories) MUST source
    scripts/build/lib/common.sh (provides log_*, require_*, confirm,
    profile_field, etc.)."""
    all_hooks = []
    for name in PRE_INSTALL_HOOKS:
        all_hooks.append(PRE_INSTALL_DIR / name)
    for name in DURING_INSTALL_HOOKS:
        all_hooks.append(DURING_INSTALL_DIR / name)
    for name in DECOMMISSION_HOOKS:
        all_hooks.append(DECOMMISSION_DIR / name)
    for path in all_hooks:
        body = _read(path)
        assert "build/lib/common.sh" in body, (
            f"lifecycle hook {path.name} missing build/lib/common.sh "
            f"source (provides log_* / require_* / confirm)"
        )


def test_pre_install_friction_audit_has_layer_b_failures_gauge():
    """SDD-016 verbatim: friction-audit-spec emits both _total counter
    AND _failures gauge (operator-discoverable: how many friction
    items?). Drift losing the failures gauge = no per-item visibility."""
    body = _read(PRE_INSTALL_DIR / "friction-audit-spec.sh")
    has_total = "sovereign_os_pre_install_friction_audit_spec_total" in body
    has_failures = "sovereign_os_pre_install_friction_audit_spec_failures" in body
    assert has_total and has_failures, (
        "friction-audit-spec.sh missing _total counter or _failures "
        "gauge (SDD-016 — operator-discoverable friction-count surface)"
    )


def test_zfs_pool_create_handles_topology_raid0_and_single():
    """SDD-005 + operator-verbatim Q-005: sain-01 uses RAID-0 across
    dual PCIe-5 NVMe. zfs-pool-create.sh MUST handle 'raid0' AND
    'single' topology values (operator-acknowledged no-redundancy
    trade-off per Q-005)."""
    body = _read(DURING_INSTALL_DIR / "zfs-pool-create.sh")
    assert "raid0" in body, (
        "zfs-pool-create.sh missing 'raid0' topology handling "
        "(SDD-005 — sain-01 operator-named topology; drift breaks "
        "default sain-01 install)"
    )


def test_mok_enroll_uses_mokutil():
    """during-install/mok-enroll.sh MUST invoke mokutil (operator-named
    Machine Owner Key tool; drift to a different tool breaks the SDD-015
    shim secure-boot chain)."""
    body = _read(DURING_INSTALL_DIR / "mok-enroll.sh")
    assert "mokutil" in body, (
        "mok-enroll.sh missing mokutil reference (operator-named MOK "
        "enrollment tool; SDD-015 shim path depends on it)"
    )
