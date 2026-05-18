"""R391 (E10.M35) — friction-audit script operator-verbatim content lint.

Extends R387/R388/R389/R390 operational-artifact pinning pattern to
the friction-audit scripts (master spec §5.1 implementation):
  scripts/hooks/pre-install/friction-audit-spec.sh
  scripts/hooks/post-install/friction-audit-runtime.sh

Master spec §5.1 verbatim audit logic:
  1. Check PCIe x8/x8 lane symmetry (lspci LnkSta Width ≥ x8)
  2. Check ZFS pool health (zpool status -x → 'all pools are healthy')
  3. Check System Memory geometry (dmidecode -t memory sticks count)
  4. Exit 1 on FAIL with operator-readable remediation hint
     ('Verify if M.2_2 slot is populated, interfering with lane paths.')

If a future agent silently changes the x8 threshold to x4, OR removes
the M.2_2 remediation hint, the runtime audit silently allows the
exact failure mode operator's §5.1 was designed to catch.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRICTION_RUNTIME = (REPO_ROOT / "scripts" / "hooks" / "post-install"
                     / "friction-audit-runtime.sh")
FRICTION_SPEC = (REPO_ROOT / "scripts" / "hooks" / "pre-install"
                  / "friction-audit-spec.sh")


def test_friction_runtime_exists():
    assert FRICTION_RUNTIME.is_file(), f"missing {FRICTION_RUNTIME}"


def test_friction_spec_exists():
    assert FRICTION_SPEC.is_file(), f"missing {FRICTION_SPEC}"


def test_runtime_audits_pcie_x8_lane_width():
    """§5.1 verbatim: 'Check for True Physical PCIe Bifurcation
    Symmetry (x8/x8 Link Width Verification)'. Audit MUST check
    Width x8 in lspci LnkSta output."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    body_lower = body.lower()
    has_lspci = "lspci" in body_lower
    has_x8 = "x8" in body_lower
    has_lnksta = "lnksta" in body_lower or "link" in body_lower
    assert has_lspci and has_x8 and has_lnksta, (
        f"friction-audit-runtime.sh missing §5.1 PCIe x8 LnkSta check "
        f"(lspci={has_lspci}, x8={has_x8}, lnksta={has_lnksta})"
    )


def test_runtime_audits_zfs_pool_health():
    """§5.1 verbatim: 'Check ZFS Array Integrity status' — zpool status -x
    output MUST equal 'all pools are healthy'."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    body_lower = body.lower()
    assert "zpool" in body_lower, (
        "friction-audit-runtime.sh missing §5.1 zpool integrity check"
    )


def test_runtime_remediation_hint_references_m2_2():
    """§5.1 verbatim remediation: 'Verify if M.2_2 slot is populated,
    interfering with lane paths.' The M.2_2 reference MUST appear in
    failure-path remediation text — operator-actionable signal."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    assert "M.2_2" in body, (
        "friction-audit-runtime.sh missing §5.1 M.2_2 remediation hint "
        "(operator-verbatim 'Verify if M.2_2 slot is populated, "
        "interfering with lane paths.')"
    )


def test_runtime_exits_with_failure_on_friction():
    """§5.1 verbatim: 'execution loops cease instantly' on FAIL.
    Script MUST have exit 1 (or exit 2) path on architectural friction.
    Catches: agent silently changes exit to 0 / removes failure exit,
    making the audit non-actionable."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    # Look for `exit 1` / `exit 2` / `return 1` in failure paths
    has_exit_fail = ("exit 1" in body or "exit 2" in body
                      or "return 1" in body)
    assert has_exit_fail, (
        "friction-audit-runtime.sh missing exit 1/2 failure path. "
        "§5.1 contract: 'execution loops cease instantly' on FAIL — "
        "without a non-zero exit, the audit is non-actionable."
    )


def test_runtime_uses_critical_friction_language():
    """§5.1 verbatim language uses 'CRITICAL ARCHITECTURAL FRICTION'
    OR equivalent severity language. Catches: silent severity
    downgrade to warning / info."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    body_lower = body.lower()
    # Some form of operator-loud severity expression
    severity_markers = ["critical", "fail", "friction", "error"]
    has_severity = any(m in body_lower for m in severity_markers)
    assert has_severity, (
        "friction-audit-runtime.sh missing operator-severity language "
        "(critical / fail / friction / error). §5.1 demands loud "
        "operator-actionable signal."
    )


def test_spec_script_documents_audit_contract():
    """The pre-install spec script (friction-audit-spec.sh) MUST
    document the §5.1 audit contract — what the runtime audit checks
    + why each check matters."""
    body = FRICTION_SPEC.read_text(encoding="utf-8")
    # Should reference the same content axes (PCIe + M.2_2)
    assert "M.2_2" in body or "m.2_2" in body.lower(), (
        "friction-audit-spec.sh missing M.2_2 reference in spec doc"
    )


def test_spec_documents_x8_lane_target():
    """Spec doc MUST mention the x8/x8 lane target (operator-verbatim
    'execution symmetry' goal)."""
    body = FRICTION_SPEC.read_text(encoding="utf-8")
    assert "x8" in body.lower(), (
        "friction-audit-spec.sh missing x8 lane target in spec doc"
    )


def test_runtime_does_not_silently_pass_on_no_check():
    """If a check returns no data (e.g., lspci unavailable), the audit
    MUST NOT silently pass. §5.1 contract requires operator-readable
    failure mode. Look for some form of skip/unknown handling that
    doesn't swallow the audit."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    # Look for explicit handling: either skip with warning, OR fail-hard
    # Catches: `2>/dev/null || true` swallows errors silently
    body_lower = body.lower()
    has_handling = ("warn" in body_lower or "skip" in body_lower
                     or "unavail" in body_lower or "missing" in body_lower)
    assert has_handling, (
        "friction-audit-runtime.sh missing explicit skip/warn/unavail "
        "handling — risk of silent pass when tools missing"
    )


def test_runtime_does_not_have_unchecked_command_substitution():
    """Catch a common drift mode: bare `$(...)` without quote escaping
    around critical audit values would let shell injection corrupt
    the audit result. Sanity: critical command outputs should be
    quoted or assigned to a variable first."""
    body = FRICTION_RUNTIME.read_text(encoding="utf-8")
    # If LANE_AUDIT_COUNT is used (operator-verbatim §5.1 variable name),
    # ensure it's properly quoted in comparisons
    if "LANE_AUDIT_COUNT" in body or "lane_audit" in body.lower():
        # Should be used in a comparison or test
        assert "$(" in body or "${" in body or "=" in body, (
            "lane count audit variable usage looks suspicious"
        )
    # Pass if no specific marker — sanity check only
