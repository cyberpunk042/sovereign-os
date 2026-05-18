"""R419 (E10.M63) — Tetragon policy LOAD + VERIFY operator-verbatim
contract + 9th bidirectional-consistency lint (policy content ↔
verifier journal grep).

Extends R387-R418 + R390 operational-artifact pinning to:
  scripts/hooks/post-install/tetragon-policy-load.sh    (writes policy)
  scripts/hooks/recurrent/tetragon-policy-verify.sh     (verifies policy)

R390 covered the operator-verbatim Tetragon policy CONTENT pinning
(the inline YAML allowlist). R419 covers the LOAD + VERIFY scripts
that emit + check that policy at runtime.

Operator-verbatim §5 + E104 (SAIN-01 milestone) Tetragon contract:
  - apiVersion: cilium.io/v1alpha1
  - kind: TracingPolicy
  - name: sovereign-kernel-fence
  - kprobe: __x64_sys_execve
  - 4-binary allowlist: python3 + nvidia-smi + vllm + podman
  - matchActions: Sigkill (operator-named — KILL not log on violation)
  - PID 1 excluded (NotIn [1])
  - followForks: true (catches fork-spawned children)

9th bidirectional-consistency lint:
  The verify.sh greps `journalctl -u tetragon` for the string
  "sovereign-kernel-fence" (the policy NAME). load.sh emits that same
  policy name in the YAML metadata.name field. If load.sh renames the
  policy (drift to "sovereign-perimeter" or similar), verify.sh's
  journal grep silently never matches = perimeter forever reports
  "drift" status = false alarm fatigue.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOAD_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "tetragon-policy-load.sh"
VERIFY_HOOK = REPO_ROOT / "scripts" / "hooks" / "recurrent" / "tetragon-policy-verify.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_both_tetragon_hooks_exist():
    for p in (LOAD_HOOK, VERIFY_HOOK):
        assert p.is_file(), f"Tetragon hook missing: {p}"


# --- Operator-verbatim policy content (LOAD side) ---


def test_load_hook_uses_cilium_v1alpha1():
    """Operator-verbatim Tetragon contract: apiVersion = cilium.io/v1alpha1.
    Drift to v1 or different group breaks Tetragon CRD schema."""
    body = _read(LOAD_HOOK)
    assert "cilium.io/v1alpha1" in body, (
        "tetragon-policy-load.sh missing 'cilium.io/v1alpha1' "
        "(Tetragon CRD apiVersion — drift breaks policy load)"
    )


def test_load_hook_uses_tracing_policy_kind():
    body = _read(LOAD_HOOK)
    assert "kind: TracingPolicy" in body, (
        "tetragon-policy-load.sh missing 'kind: TracingPolicy' "
        "(Tetragon CRD kind verbatim)"
    )


def test_load_hook_policy_named_sovereign_kernel_fence():
    """OPERATOR-NAMED: policy name MUST be sovereign-kernel-fence
    (this name is what verify.sh greps for — bidirectional consistency
    surface)."""
    body = _read(LOAD_HOOK)
    assert "sovereign-kernel-fence" in body, (
        "tetragon-policy-load.sh missing 'sovereign-kernel-fence' "
        "policy name (operator-named §5 perimeter)"
    )


def test_load_hook_targets_sys_execve():
    """Operator-named target: __x64_sys_execve kprobe. Drift to a
    different syscall = perimeter doesn't catch process spawn."""
    body = _read(LOAD_HOOK)
    assert "__x64_sys_execve" in body, (
        "tetragon-policy-load.sh missing '__x64_sys_execve' kprobe "
        "(operator-named §5 — drift = no execve perimeter)"
    )


def test_load_hook_has_4_binary_allowlist():
    """R390 covered this for the YAML content as authored.
    R419 reasserts the 4-binary set is in the LOAD HOOK's heredoc.
    Operator-named: python3 + nvidia-smi + vllm + podman."""
    body = _read(LOAD_HOOK)
    expected = ["python3", "nvidia-smi", "vllm", "podman"]
    for binary in expected:
        assert binary in body, (
            f"tetragon-policy-load.sh missing '{binary}' in allowlist "
            f"(operator-named §5 4-binary set)"
        )


def test_load_hook_action_is_sigkill():
    """Operator-named action: Sigkill (NOT log-only). Drift to log-only
    silently weakens the perimeter from kill-on-violation to
    record-on-violation."""
    body = _read(LOAD_HOOK)
    assert "Sigkill" in body, (
        "tetragon-policy-load.sh missing 'Sigkill' action "
        "(operator-named §5 — drift to log-only = weakened perimeter)"
    )


def test_load_hook_excludes_pid_1():
    """Operator-named exclusion: PID 1 (systemd / init) MUST be
    excluded from kill action. Drift = killing PID 1 reboots host."""
    body = _read(LOAD_HOOK)
    # PID 1 exclusion via matchPIDs operator NotIn values [1]
    has_pid_1_exclude = (
        re.search(r"matchPIDs.*\n.*NotIn.*\n.*values.*\[1\]",
                  body, re.DOTALL)
        or re.search(r"values:\s*\[\s*1\s*\]", body)
    )
    assert has_pid_1_exclude, (
        "tetragon-policy-load.sh missing PID 1 exclusion "
        "(operator-named — drift = killing PID 1 reboots host)"
    )


def test_load_hook_follow_forks():
    """followForks: true catches child processes (drift to false =
    fork-spawned binaries bypass perimeter)."""
    body = _read(LOAD_HOOK)
    assert "followForks: true" in body, (
        "tetragon-policy-load.sh missing 'followForks: true' "
        "(drift = fork-spawned children bypass perimeter)"
    )


def test_load_hook_targets_correct_policy_dir():
    """Operator-named install path: /etc/tetragon/tracing-policies
    (Tetragon's standard location). Drift = Tetragon doesn't pick up
    the policy file."""
    body = _read(LOAD_HOOK)
    assert "/etc/tetragon/tracing-policies" in body, (
        "tetragon-policy-load.sh missing /etc/tetragon/tracing-policies "
        "(Tetragon-standard policy dir; drift = silent non-load)"
    )


def test_load_hook_requires_root():
    """Writes to /etc/tetragon + restarts service = needs root."""
    body = _read(LOAD_HOOK)
    assert "require_root" in body, (
        "tetragon-policy-load.sh missing require_root"
    )


def test_load_hook_restarts_tetragon():
    """After writing policy, MUST restart tetragon to pick up new
    policy. Drift = policy file present but daemon still serves old
    policy."""
    body = _read(LOAD_HOOK)
    assert ("systemctl restart tetragon" in body
            or "systemctl reload tetragon" in body), (
        "tetragon-policy-load.sh missing tetragon service restart "
        "(drift = policy file ignored until next boot)"
    )


def test_load_hook_emits_metric():
    body = _read(LOAD_HOOK)
    assert "sovereign_os_post_install_tetragon_policy_load_total" in body, (
        "tetragon-policy-load.sh missing per-result metric (SDD-016)"
    )


# --- VERIFY side ---


def test_verify_hook_emits_perimeter_status_gauge():
    """SDD-016 verbatim: sovereign_os_perimeter_status (1=loaded/healthy,
    0=drift/down/missing). Operator-discoverable Grafana stat surface."""
    body = _read(VERIFY_HOOK)
    assert "sovereign_os_perimeter_status" in body, (
        "tetragon-policy-verify.sh missing sovereign_os_perimeter_status "
        "gauge (SDD-016 verbatim — perimeter health surface)"
    )


def test_verify_hook_emits_last_run_timestamp():
    """SDD-016 verbatim: last_run_timestamp metric — catches 'verifier
    overdue' (drift = verifier silently stops; metric stale)."""
    body = _read(VERIFY_HOOK)
    assert "sovereign_os_perimeter_verify_last_run_timestamp" in body, (
        "tetragon-policy-verify.sh missing perimeter_verify_last_run_"
        "timestamp gauge (catches 'verifier overdue')"
    )


def test_verify_hook_checks_tetragon_installed():
    """If tetragon binary not present, MUST emit perimeter_status=0
    + exit non-zero (operator-discoverable: perimeter has no daemon)."""
    body = _read(VERIFY_HOOK)
    assert "tetragon" in body and "not installed" in body, (
        "tetragon-policy-verify.sh missing 'not installed' check "
        "(drift = no signal when daemon missing)"
    )


def test_verify_hook_checks_tetragon_active():
    """If daemon installed but not active, MUST emit perimeter_status=0
    + log to security audit log."""
    body = _read(VERIFY_HOOK)
    assert "is-active --quiet tetragon" in body, (
        "tetragon-policy-verify.sh missing systemctl is-active check "
        "for tetragon (drift = false-positive 'healthy' when daemon dead)"
    )


def test_verify_hook_writes_audit_log_on_drift():
    """Operator-named audit log: /mnt/vault/context/security_audit.log
    (tank/context dataset — state-fabric durability per R393)."""
    body = _read(VERIFY_HOOK)
    assert "security_audit.log" in body, (
        "tetragon-policy-verify.sh missing security_audit.log write "
        "on perimeter drift (operator-discoverable forensic record)"
    )


def test_verify_hook_audit_log_on_tank_context():
    """Audit log MUST land on tank/context (state-fabric durability —
    R393 verbatim). Drift to /var/log = loses cross-reboot persistence."""
    body = _read(VERIFY_HOOK)
    assert "/mnt/vault/context" in body, (
        "tetragon-policy-verify.sh audit log not on /mnt/vault/context "
        "(tank/context state-fabric dataset per R393)"
    )


# --- 9th bidirectional-consistency lint ---


def test_bidirectional_policy_name_consistency():
    """9th bidirectional-consistency lint:
      load.sh writes policy with metadata.name=sovereign-kernel-fence
      verify.sh greps journalctl for 'sovereign-kernel-fence'
    Both MUST agree on the string. Drift = verifier never finds policy
    in journal = false 'drift' alarms forever."""
    load_body = _read(LOAD_HOOK)
    verify_body = _read(VERIFY_HOOK)

    # Extract the metadata.name from load.sh
    name_match = re.search(r"name:\s*(sovereign-\S+)", load_body)
    assert name_match, (
        "tetragon-policy-load.sh missing 'name: <policy-name>' "
        "in metadata section"
    )
    policy_name = name_match.group(1)
    assert policy_name == "sovereign-kernel-fence", (
        f"tetragon-policy-load.sh metadata.name={policy_name!r} != "
        f"'sovereign-kernel-fence' (operator-named §5 perimeter)"
    )

    # verify.sh MUST grep for the same name
    assert policy_name in verify_body, (
        f"tetragon-policy-verify.sh doesn't grep for policy name "
        f"{policy_name!r} (bidirectional consistency violation — "
        f"verifier never finds policy in journal = false alarms)"
    )


def test_bidirectional_policy_dir_consistency():
    """The policy dir path MUST match between load + verify hooks.
    load.sh writes to /etc/tetragon/tracing-policies/...
    verify.sh checks /etc/tetragon/tracing-policies/sovereign-...yaml
    Drift between the two = verify checks wrong path = false alarm."""
    load_body = _read(LOAD_HOOK)
    verify_body = _read(VERIFY_HOOK)
    common_dir = "/etc/tetragon/tracing-policies"
    assert common_dir in load_body, (
        f"tetragon-policy-load.sh missing common dir {common_dir}"
    )
    assert common_dir in verify_body, (
        f"tetragon-policy-verify.sh missing common dir {common_dir} "
        f"(bidirectional path consistency violation)"
    )


def test_e104_sain01_milestone_reference():
    """Operator-discovery: load hook header SHOULD reference E104
    (info-hub epic) so a reader sees the binding to the operator-named
    SAIN-01 milestone."""
    body = _read(LOAD_HOOK)
    assert "E104" in body or "SAIN-01" in body or "sain-01" in body, (
        "tetragon-policy-load.sh missing E104/SAIN-01 reference "
        "(operator-discovery: missing milestone binding)"
    )
