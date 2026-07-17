#!/usr/bin/env bash
# scripts/hooks/post-install/tetragon-policy-load.sh
#
# Load Tetragon TracingPolicy for the sovereign-kernel-fence. Allowlists
# ~4 binaries for sys_execve; SIGKILL on violation. Current scope is
# HOST-WIDE minus PID 1 (matchPIDs NotIn [1]) — container/namespace
# scoping of the fence is a Stage-2 refinement, not what ships today.
#
# Per SAIN-01 milestone (info-hub E104). The policy is INLINED in the
# heredoc below (operator-verbatim content pinned by R390/R419 lint)
# and installed to /etc/tetragon/tracing-policies/. Stage-2 tunes the
# substantive allowlist. The daemon itself is installed by the
# preceding first-boot hook, tetragon-install.sh (Cilium release
# tarball — tetragon is not in the Debian archive).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="tetragon-policy-load"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_TETRAGON_POLICY_DIR:=/etc/tetragon/tracing-policies}"

log_step_header "${STEP_ID}" "load Tetragon sovereign-kernel-fence policy"

# Emit on EVERY terminal path. tetragon is the kernel-fence security boundary
# (SIGKILL on unauthorized execve); a silently-failed load means the fence is
# NOT active, so a failure must be VISIBLE as result="fail" — not merely the
# absence of a result="loaded" sample (which is indistinguishable from "the
# hook never ran").
emit_tetragon_metric() {
  emit_metric sovereign_os_post_install_tetragon_policy_load_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

require_root

if ! command -v tetragon >/dev/null 2>&1; then
  log_error "tetragon binary not found (not in the Debian archive)"
  log_error "REMEDIATION: run the installer hook, then re-run this one:"
  log_error "  sudo ${__REPO_ROOT}/scripts/hooks/post-install/tetragon-install.sh"
  emit_tetragon_metric fail
  exit 1
fi

mkdir -p "${SOVEREIGN_OS_TETRAGON_POLICY_DIR}"

policy_file="${SOVEREIGN_OS_TETRAGON_POLICY_DIR}/sovereign-kernel-fence.yaml"

if [ ! -f "${policy_file}" ]; then
  log_info "installing sovereign-kernel-fence policy → ${policy_file}"
  cat > "${policy_file}" <<'EOF'
# Sovereign-os kernel-fence Tetragon TracingPolicy.
# Allowlists ~4 binaries for sys_execve; SIGKILL on any other execve
# attempt. Scope: HOST-WIDE minus PID 1 (matchPIDs NotIn [1]) —
# container/namespace scoping is a Stage-2 refinement.
# Per SAIN-01 milestone E104.
#
# Substantive policy refinement: Stage 2+ tunes the allowlist per
# operator workload. This default is the L0-dump minimum.

apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: sovereign-kernel-fence
spec:
  kprobes:
  - call: "__x64_sys_execve"
    syscall: true
    args:
    - index: 0
      type: "string"
    - index: 1
      type: "string"
    selectors:
    - matchPIDs:
      - operator: "NotIn"
        followForks: true
        isNamespacePID: false
        values: [1]
      matchBinaries:
      - operator: "NotIn"
        values:
        - "/usr/bin/python3"
        - "/usr/bin/nvidia-smi"
        - "/usr/local/bin/vllm"
        - "/usr/bin/podman"
      matchActions:
      - action: Sigkill
EOF
else
  log_info "policy already present at ${policy_file}"
fi

# Start / restart tetragon
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable tetragon 2>&1 | sed 's/^/  /' || true
  systemctl restart tetragon 2>&1 | sed 's/^/  /' || {
    log_error "tetragon failed to start; check 'journalctl -u tetragon'"
    emit_tetragon_metric fail
    exit 1
  }
  # Verify active
  if systemctl is-active --quiet tetragon; then
    log_info "tetragon active; policy loaded"
  else
    log_error "tetragon not active after restart"
    emit_tetragon_metric fail
    exit 1
  fi
fi

emit_tetragon_metric loaded
log_info "${STEP_ID} complete"
