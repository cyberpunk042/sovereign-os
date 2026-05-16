#!/usr/bin/env bash
# scripts/hooks/post-install/tetragon-policy-load.sh
#
# Load Tetragon TracingPolicy for the sovereign-kernel-fence. Allowlists
# ~4 binaries for sys_execve in containerized agents; SIGKILL on
# violation.
#
# Per SAIN-01 milestone (info-hub E104). Policy lives in
# scripts/hooks/post-install/policies/sovereign-kernel-fence.yaml
# (Stage-2 fills in the substantive list; this script ensures the
# daemon + policy are loaded).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="tetragon-policy-load"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_TETRAGON_POLICY_DIR:=/etc/tetragon/tracing-policies}"

log_step_header "${STEP_ID}" "load Tetragon sovereign-kernel-fence policy"

require_root

if ! command -v tetragon >/dev/null 2>&1; then
  log_error "tetragon binary not found; install via profile packages"
  exit 1
fi

mkdir -p "${SOVEREIGN_OS_TETRAGON_POLICY_DIR}"

policy_file="${SOVEREIGN_OS_TETRAGON_POLICY_DIR}/sovereign-kernel-fence.yaml"

if [ ! -f "${policy_file}" ]; then
  log_info "installing sovereign-kernel-fence policy → ${policy_file}"
  cat > "${policy_file}" <<'EOF'
# Sovereign-os kernel-fence Tetragon TracingPolicy.
# Allowlists ~4 binaries for sys_execve inside containerized agents;
# SIGKILL on any other execve attempt.
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
    exit 1
  }
  # Verify active
  if systemctl is-active --quiet tetragon; then
    log_info "tetragon active; policy loaded"
  else
    log_error "tetragon not active after restart"
    exit 1
  fi
fi

log_info "${STEP_ID} complete"
