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

# --- arming knob (observe posture WITHOUT violating the Sigkill verbatim) ---
# The fence ACTION is always Sigkill (operator-verbatim §4.1 — never log-only);
# this knob controls only whether the Sigkill fence is LOADED into the running
# daemon. Default: armed (the appliance posture). Disarmed writes the policy
# file (verify.sh + operator-named path preserved) but does NOT load it — the
# container-scope selector is unsound on a systemd DESKTOP (it false-matches
# host services), so arming Sigkill there is unsafe until the scoping is
# redesigned. See backlog/notes/2026-08-20-tetragon-fence-not-enforcing-findings.
: "${SOVEREIGN_OS_TETRAGON_ARMED:=$(profile_field provisioning.tetragon.armed)}"
case "${SOVEREIGN_OS_TETRAGON_ARMED:-}" in
  0|false|no|off|disarmed) SOVEREIGN_OS_TETRAGON_ARMED=0 ;;
  *)                       SOVEREIGN_OS_TETRAGON_ARMED=1 ;;
esac

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

# ---- install the fence where THIS tetragon actually auto-loads from ----
# ${policy_file} above is the operator-named canonical path (and what verify.sh
# checks), but Cilium's Tetragon reads policies from its configured
# tracing-policy-dir (package default /etc/tetragon/tetragon.tp.d) — a DIFFERENT
# directory. Writing only to the operator-named path leaves the fence UNLOADED:
# the daemon never sees it, yet every file-presence check reports green (the
# "green but blind" failure found 2026-08-20 — file present, `tetra
# tracingpolicy list` empty, canary walked through). Detect the daemon's
# effective dir and install a copy there so it actually auto-loads on boot.
_tp_dir="${SOVEREIGN_OS_TETRAGON_TP_DIR:-}"
if [ -z "${_tp_dir}" ]; then
  for _base in /usr/lib/tetragon /usr/local/lib/tetragon /etc/tetragon; do
    [ -f "${_base}/tetragon.conf.d/tracing-policy-dir" ] && \
      _tp_dir="$(tr -d '[:space:]' < "${_base}/tetragon.conf.d/tracing-policy-dir")"
  done
  : "${_tp_dir:=/etc/tetragon/tetragon.tp.d}"
fi
if [ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 1 ]; then
  if [ "${_tp_dir}" != "${SOVEREIGN_OS_TETRAGON_POLICY_DIR}" ]; then
    mkdir -p "${_tp_dir}"
    if cp -f "${policy_file}" "${_tp_dir}/sovereign-kernel-fence.yaml"; then
      log_info "ARMED — installed fence into tetragon auto-load dir → ${_tp_dir}/sovereign-kernel-fence.yaml"
    else
      log_error "could not install fence into ${_tp_dir} — daemon will NOT auto-load it"
      emit_tetragon_metric fail
      exit 1
    fi
  fi
else
  # Disarmed: keep the operator-named policy file, but ensure it is NOT loaded.
  log_warn "DISARMED (SOVEREIGN_OS_TETRAGON_ARMED=0) — Sigkill fence written to ${policy_file} but NOT loaded into the daemon (observe posture)"
  rm -f "${_tp_dir}/sovereign-kernel-fence.yaml" 2>/dev/null || true
  command -v tetra >/dev/null 2>&1 && tetra tracingpolicy delete sovereign-kernel-fence >/dev/null 2>&1 || true
fi

# ---- wire the JSON event export the Auditor circuit-breaker consumes ----
# Cilium's vendor install.sh ships export-filename=/var/run/tetragon/tetragon.log
# under /usr/local/lib/tetragon/tetragon.conf.d. The Auditor chain expects
# /var/run/tetragon/tetragon.events — guardian-core tails it (master spec § 10),
# and bootstrap verify-grid check 05 asserts it present. Without this drop-in the
# stream lands at tetragon.log and the Guardian starves. An /etc drop-in wins over
# the vendor default; the restart below activates it. Idempotent (rewrites on drift
# only), env-overridable per the IaC bar.
_export_conf_dir="${SOVEREIGN_OS_TETRAGON_CONF_DIR:-/etc/tetragon/tetragon.conf.d}"
_export_target="${SOVEREIGN_OS_TETRAGON_EXPORT_FILE:-/var/run/tetragon/tetragon.events}"
mkdir -p "${_export_conf_dir}"
if [ "$(cat "${_export_conf_dir}/export-filename" 2>/dev/null)" = "${_export_target}" ]; then
  log_info "Tetragon export-filename already → ${_export_target}"
else
  printf '%s\n' "${_export_target}" > "${_export_conf_dir}/export-filename"
  log_info "set Tetragon export-filename → ${_export_target}"
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
    log_info "tetragon active"
  else
    log_error "tetragon not active after restart"
    emit_tetragon_metric fail
    exit 1
  fi
fi

# ---- verify the fence load state matches the arming intent ----
# File-present != loaded. A policy in a dir the daemon does not read loads
# nothing while every file check still reports green (the "green but blind"
# failure, 2026-08-20). Assert the daemon's actual state matches ARMED. Requires
# root + the tetra CLI + a reachable socket; degrade honestly when we cannot query.
if command -v tetra >/dev/null 2>&1 && tetra tracingpolicy list >/dev/null 2>&1; then
  if tetra tracingpolicy list 2>/dev/null | grep -q 'sovereign-kernel-fence'; then
    if [ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 1 ]; then
      log_info "verified: sovereign-kernel-fence ARMED (loaded in the running daemon)"
    else
      log_error "disarm requested but sovereign-kernel-fence is still loaded — removing"
      tetra tracingpolicy delete sovereign-kernel-fence >/dev/null 2>&1 || true
    fi
  else
    if [ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 1 ]; then
      log_error "sovereign-kernel-fence is NOT loaded (tetra tracingpolicy list) — perimeter BLIND"
      emit_tetragon_metric fail
      exit 1
    else
      log_info "verified: sovereign-kernel-fence DISARMED (not loaded — observe posture)"
    fi
  fi
else
  log_warn "cannot query the daemon (need root + tetra + live socket) — fence load state UNVERIFIED"
fi

emit_tetragon_metric "$([ "${SOVEREIGN_OS_TETRAGON_ARMED}" = 1 ] && echo loaded || echo disarmed)"
log_info "${STEP_ID} complete (armed=${SOVEREIGN_OS_TETRAGON_ARMED})"
