#!/usr/bin/env bash
# scripts/hooks/post-install/tetragon-policy-load.sh
#
# Load Tetragon TracingPolicy for the sovereign-kernel-fence. Allowlists
# execve binaries; SIGKILL on violation.
#
# Per SAIN-01 milestone (info-hub E104). The base policy (pinned by
# R390/R419 lint — the 4-binary allowlist, __x64_sys_execve, Sigkill,
# PID-1 exclusion, followForks) is the literal template below; two
# operator knobs make it a real (not L0-minimum) fence without touching
# the pinned base:
#
#   SOVEREIGN_OS_TETRAGON_SCOPE   host (default) | container
#     host      — the shipped behavior: host-wide minus PID 1.
#     container — ALSO require the process be in a non-host mount
#                 namespace (matchNamespaces Mnt NotIn host_ns), i.e.
#                 the fence enforces only inside containers. This
#                 NARROWS coverage; opt-in for hosts that run agents
#                 exclusively in podman.
#   provisioning.tetragon.extra_allowed_binaries  (profile) OR
#   SOVEREIGN_OS_TETRAGON_EXTRA_BINS (colon-separated env)
#     — extra ABSOLUTE binary paths appended to the base 4-binary
#       allowlist, so a legitimate 5th+ workload isn't SIGKILLed.
#       Non-absolute entries are refused (never widen the fence on a
#       typo). The base 4 always remain.
#
# Both default to today's exact output, so a node that sets neither
# gets the byte-identical shipped policy. The daemon itself is installed
# by the preceding first-boot hook, tetragon-install.sh (Cilium release
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

# --- resolve the two operator knobs (both default to shipped behavior) ---
: "${SOVEREIGN_OS_TETRAGON_SCOPE:=$(profile_field provisioning.tetragon.scope)}"
: "${SOVEREIGN_OS_TETRAGON_SCOPE:=host}"

# Collect operator-declared extra allowed binaries from BOTH sources:
# profile provisioning.tetragon.extra_allowed_binaries (JSON list) +
# SOVEREIGN_OS_TETRAGON_EXTRA_BINS (colon-separated). Validated to
# absolute paths — a relative/garbage entry must never silently widen
# the fence, so it is refused with a warning, not templated in.
extra_bins_yaml=""
_add_extra_bin() {
  local b="$1"
  case "${b}" in
    /*) extra_bins_yaml="${extra_bins_yaml}        - \"${b}\""$'\n' ;;
    "") : ;;
    *)  log_warn "ignoring non-absolute extra_allowed_binaries entry: '${b}'" ;;
  esac
}
_extra_json="$(profile_field provisioning.tetragon.extra_allowed_binaries)"
if [ -n "${_extra_json}" ] && [ "${_extra_json}" != "null" ]; then
  while IFS= read -r _b; do _add_extra_bin "${_b}"; done < <(
    printf '%s' "${_extra_json}" | "${PYTHON3}" -c \
      'import sys,json;
d=json.load(sys.stdin);
[print(x) for x in (d if isinstance(d,list) else [])]' 2>/dev/null)
fi
if [ -n "${SOVEREIGN_OS_TETRAGON_EXTRA_BINS:-}" ]; then
  IFS=':' read -ra _envbins <<< "${SOVEREIGN_OS_TETRAGON_EXTRA_BINS}"
  for _b in "${_envbins[@]}"; do _add_extra_bin "${_b}"; done
fi

# container scope adds a matchNamespaces clause AND-ed into the selector
# (Tetragon ANDs match* clauses within one selector) — enforce only for
# processes whose mount namespace is NOT the host's.
ns_block=""
if [ "${SOVEREIGN_OS_TETRAGON_SCOPE}" = "container" ]; then
  ns_block=$'      matchNamespaces:\n      - namespace: Mnt\n        operator: "NotIn"\n        values:\n        - "host_ns"\n'
  log_info "tetragon scope=container — fence enforces inside non-host mount namespaces only"
elif [ "${SOVEREIGN_OS_TETRAGON_SCOPE}" != "host" ]; then
  log_warn "unknown SOVEREIGN_OS_TETRAGON_SCOPE='${SOVEREIGN_OS_TETRAGON_SCOPE}' — using host scope"
  SOVEREIGN_OS_TETRAGON_SCOPE="host"
fi

if [ ! -f "${policy_file}" ]; then
  log_info "installing sovereign-kernel-fence policy → ${policy_file} (scope=${SOVEREIGN_OS_TETRAGON_SCOPE})"
  # The base 4-binary allowlist + Sigkill + matchPIDs NotIn [1] +
  # followForks: true are pinned by R390/R419 and appear literally
  # below. ${extra_bins_yaml} appends operator-validated absolute paths;
  # ${ns_block} is empty for host scope. Unquoted heredoc for the two
  # interpolations; the YAML carries no other $.
  cat > "${policy_file}" <<EOF
# Sovereign-os kernel-fence Tetragon TracingPolicy.
# Allowlists execve binaries; SIGKILL on any other execve attempt.
# Base scope: HOST-WIDE minus PID 1 (matchPIDs NotIn [1]); with
# SOVEREIGN_OS_TETRAGON_SCOPE=container it ALSO requires a non-host
# mount namespace. Base allowlist is the pinned 4; operator extras
# (validated absolute paths) append. Per SAIN-01 milestone E104.

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
${ns_block}      matchBinaries:
      - operator: "NotIn"
        values:
        - "/usr/bin/python3"
        - "/usr/bin/nvidia-smi"
        - "/usr/local/bin/vllm"
        - "/usr/bin/podman"
${extra_bins_yaml}      matchActions:
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
