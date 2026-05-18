"""R390 (E10.M34) — Tetragon policy operator-verbatim structure lint.

Extends R387/R388/R389 operational-artifact pinning pattern to:
  scripts/hooks/post-install/tetragon-policy-load.sh

R367 covered the 4-binary allowlist bidirectional (C-14 concept ↔
shipped policy script). R390 pins the FULL TracingPolicy structure
operator-verbatim from master spec §4.1:

  apiVersion: cilium.io/v1alpha1
  kind: TracingPolicy
  metadata:
    name: "sovereign-kernel-fence"
  spec:
    kprobes:
    - call: <sys_execve OR architecture-specific equivalent>
      syscall: true
      …
      matchActions:
      - action: Sigkill

If the shipped policy silently drifts (e.g., kind: TracingPolicyNamespaced
instead of TracingPolicy, OR action: NoOp instead of Sigkill), the
container perimeter is silently broken.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_SCRIPT = (REPO_ROOT / "scripts" / "hooks" / "post-install"
                  / "tetragon-policy-load.sh")


def _read_policy_script() -> str:
    assert POLICY_SCRIPT.is_file(), f"missing {POLICY_SCRIPT}"
    return POLICY_SCRIPT.read_text(encoding="utf-8")


def test_policy_script_exists():
    assert POLICY_SCRIPT.is_file(), f"missing {POLICY_SCRIPT}"


def test_apiversion_cilium_v1alpha1_verbatim():
    """Master spec §4.1 verbatim: apiVersion: cilium.io/v1alpha1.
    Catches: silent upgrade to v1beta1 without operator approval."""
    body = _read_policy_script()
    assert "apiVersion: cilium.io/v1alpha1" in body, (
        "Tetragon policy missing operator-verbatim §4.1 "
        "'apiVersion: cilium.io/v1alpha1'. Either operator approved "
        "a version upgrade (update this lint) OR silent drift."
    )


def test_kind_tracingpolicy_verbatim():
    """Master spec §4.1: kind: TracingPolicy (NOT TracingPolicyNamespaced
    NOT NetworkPolicy NOT anything else). Catches silent kind drift."""
    body = _read_policy_script()
    assert "kind: TracingPolicy" in body, (
        "Tetragon policy missing operator-verbatim §4.1 "
        "'kind: TracingPolicy'"
    )
    # Catches silent drift to TracingPolicyNamespaced
    import re
    other_kinds = re.findall(r"^kind:\s+(\w+)", body, re.M)
    bad_kinds = [k for k in other_kinds if k != "TracingPolicy"]
    assert not bad_kinds, (
        f"Tetragon policy script has non-TracingPolicy kinds: {bad_kinds}"
    )


def test_metadata_name_sovereign_kernel_fence_verbatim():
    """Master spec §4.1: metadata.name: 'sovereign-kernel-fence'."""
    body = _read_policy_script()
    assert "sovereign-kernel-fence" in body, (
        "Tetragon policy missing operator-verbatim metadata.name "
        "'sovereign-kernel-fence' (§4.1)"
    )


def test_kprobes_execve_call_present():
    """Master spec §4.1: kprobes call sys_execve (or architecture-
    specific equivalent like __x64_sys_execve). MUST monitor execve
    syscalls — the load-bearing security gate."""
    body = _read_policy_script()
    has_call = ("sys_execve" in body or "__x64_sys_execve" in body)
    assert has_call, (
        "Tetragon policy missing kprobes call for sys_execve / "
        "__x64_sys_execve (§4.1 — load-bearing security gate that "
        "intercepts container execve)"
    )


def test_syscall_true_flag_present():
    """§4.1 verbatim: syscall: true on the kprobe."""
    body = _read_policy_script()
    assert "syscall: true" in body, (
        "Tetragon policy missing 'syscall: true' flag (§4.1 verbatim)"
    )


def test_match_actions_sigkill_verbatim():
    """§4.1 verbatim: matchActions - action: Sigkill. The kernel-level
    SIGKILL on unauthorized binary is the operator's reject-not-bridge
    contract."""
    body = _read_policy_script()
    # Either matchActions block OR a Sigkill action mention
    assert "Sigkill" in body, (
        "Tetragon policy missing 'Sigkill' matchAction (§4.1 verbatim — "
        "operator's 'reject not bridge' contract requires immediate "
        "kernel-space SIGKILL on unauthorized syscall)"
    )
    # Catches silent action drift (Sigkill → NoOp / Log / etc)
    import re
    actions = re.findall(r"action:\s+(\w+)", body)
    bad_actions = [a for a in actions if a not in ("Sigkill",)]
    if bad_actions:
        # NoOp or Log etc would silently disable the perimeter
        forbidden_in_drift = {"NoOp", "Log", "Audit", "Allow"}
        bad_in_drift = [a for a in bad_actions if a in forbidden_in_drift]
        assert not bad_in_drift, (
            f"Tetragon policy has unauthorized actions {bad_in_drift} — "
            f"operator's §4.1 contract specifies Sigkill only"
        )


def test_match_binaries_notin_operator():
    """The §4.1 policy structure rejects (NotIn) all binaries except
    the 4-binary allowlist. The 'NotIn' operator is the load-bearing
    semantic — silently changing to 'In' would invert the policy."""
    body = _read_policy_script()
    assert "NotIn" in body, (
        "Tetragon policy missing 'NotIn' operator (§4.1 — the load-"
        "bearing semantic that rejects unauthorized binaries). 'In' "
        "would invert the policy to ALLOWLIST the 4 binaries AND "
        "REJECT everything else — exact opposite of operator intent."
    )


def test_four_binary_allowlist_complete():
    """§4.1 4-binary allowlist (R367 bidirectional check, here pinned
    to script directly). The 4 operator-named binaries:
      /usr/bin/python3
      /usr/bin/nvidia-smi
      /usr/local/bin/vllm
      /usr/bin/podman
    """
    body = _read_policy_script()
    binaries = [
        "/usr/bin/python3",
        "/usr/bin/nvidia-smi",
        "/usr/local/bin/vllm",
        "/usr/bin/podman",
    ]
    missing = [b for b in binaries if b not in body]
    assert not missing, (
        f"Tetragon policy missing operator-verbatim §4.1 allowlist "
        f"binaries: {missing}"
    )


def test_policy_default_path_consistent():
    """Policy is written to a deterministic path that the runtime
    systemd unit loads (consistency: script + service unit + verifier
    all reference the same path)."""
    body = _read_policy_script()
    # Common Tetragon policy path
    expected_path_fragments = ("/etc/tetragon", "tracing-policies",
                                "sovereign-kernel-fence")
    has_path = all(frag in body for frag in expected_path_fragments)
    assert has_path, (
        "Tetragon policy script missing reference to canonical path "
        "fragments (/etc/tetragon / tracing-policies / sovereign-kernel-"
        "fence). Path must be consistent with the systemd unit loader."
    )
