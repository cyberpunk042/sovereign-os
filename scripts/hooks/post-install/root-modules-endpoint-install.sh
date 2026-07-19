#!/usr/bin/env bash
# scripts/hooks/post-install/root-modules-endpoint-install.sh
#
# First-boot install of the root-modules (formerly root-ghostproxy)
# endpoint AI-agent safety
# envelope — PROXY MODE DISABLED (SDD-046).
#
# Cross-repo contract (SDD-001 + SDD-046): sovereign-os BUILDS, selfdef
# RUNS the OS runtime defense, root-modules governs the AI-AGENT
# TOOL-CALL surface (machine-level Claude Code + opencode safety
# envelope, agent brain, integrity sentinel). This hook consumes
# root-modules through its OWN install surface per its canonical
# guide (root-modules docs/sovereign-os-endpoint-usage.md) — never
# forks or re-derives the safety envelope.
#
# MODE IS PINNED: --mode endpoint. Never auto — SAIN-01 has two NICs
# (mgmt i226-v + data aqc113c) and root-modules's auto-detection
# promotes multi-NIC hosts to bridge mode, which would enable the
# proxy/IPS half the operator directed OFF (operator verbatim
# 2026-07-03: "we will use use the repo without the proxy mode
# enabled"). Re-enabling the proxy half is a deliberate operator
# action, not a default.
#
# Behavior (triple-gate convention, sister to selfdef-sync):
#   - DEFAULT: report-only. Runs the upstream installer's --dry-run
#     and reports what a real install would do. Never mutates state.
#   - APPLY:   requires SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL=YES.
#     Runs the real install, then the upstream --check verification.
#   - Honors SOVEREIGN_OS_DRY_RUN=1 (forces report-only even with
#     confirm).
#   - Absent checkout is a REPORT, not a hook failure (exit 0; the
#     operator sees result="absent" in metrics).
#
# Emits Layer B metrics:
#   sovereign_os_ghostproxy_endpoint_install_result{result=report-only|installed|install-failed|absent}
#   sovereign_os_ghostproxy_endpoint_install_last_run_timestamp

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

# Renamed 2026-07-19: the upstream project root-ghostproxy is now root-modules
# ("ghostproxy" now names the proxy module combo this binding keeps OFF).
# Canonical env: SOVEREIGN_OS_ROOT_MODULES_DIR; legacy SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR
# honored; a pre-rename ~/root-ghostproxy checkout is still found.
if [ -z "${SOVEREIGN_OS_ROOT_MODULES_DIR:-}" ] && [ -n "${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR:-}" ]; then
  SOVEREIGN_OS_ROOT_MODULES_DIR="${SOVEREIGN_OS_ROOT_GHOSTPROXY_DIR}"
fi
if [ -z "${SOVEREIGN_OS_ROOT_MODULES_DIR:-}" ]; then
  if [ -d "${HOME}/root-modules" ] || [ ! -d "${HOME}/root-ghostproxy" ]; then
    SOVEREIGN_OS_ROOT_MODULES_DIR="${HOME}/root-modules"
  else
    SOVEREIGN_OS_ROOT_MODULES_DIR="${HOME}/root-ghostproxy"
  fi
fi
: "${SOVEREIGN_OS_GHOSTPROXY_PROFILE:=base}"
# NOT env-overridable by design (SDD-046 A2): the mode is the operator
# directive itself. Changing it means editing this hook deliberately.
GHOSTPROXY_MODE="endpoint"

log_step_header "root-modules-endpoint-install" \
  "AI-agent safety envelope (mode=${GHOSTPROXY_MODE}, proxy OFF) from ${SOVEREIGN_OS_ROOT_MODULES_DIR}"

emit_summary() {
  local result="$1"
  emit_metric_set ghostproxy-endpoint-install \
    '# HELP sovereign_os_ghostproxy_endpoint_install_result Last install-hook outcome (1 = this result)' \
    '# TYPE sovereign_os_ghostproxy_endpoint_install_result gauge' \
    "sovereign_os_ghostproxy_endpoint_install_result{result=\"${result}\"} 1" \
    '# HELP sovereign_os_ghostproxy_endpoint_install_last_run_timestamp Unix timestamp of last run' \
    '# TYPE sovereign_os_ghostproxy_endpoint_install_last_run_timestamp gauge' \
    "sovereign_os_ghostproxy_endpoint_install_last_run_timestamp $(date +%s)"
}

INSTALLER="${SOVEREIGN_OS_ROOT_MODULES_DIR}/install.sh"

if [ ! -x "${INSTALLER}" ]; then
  log_warn "no root-modules checkout at ${SOVEREIGN_OS_ROOT_MODULES_DIR} (set SOVEREIGN_OS_ROOT_MODULES_DIR)"
  log_warn "clone it, then re-run: git clone https://github.com/cyberpunk042/root-modules ${SOVEREIGN_OS_ROOT_MODULES_DIR}"
  emit_summary absent
  exit 0   # absent is a report, not a hook failure
fi

cd "${SOVEREIGN_OS_ROOT_MODULES_DIR}"
require_command bash

if [ "${SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL:-}" != "YES" ] || [ "${SOVEREIGN_OS_DRY_RUN:-0}" = "1" ]; then
  log_info "  report-only: previewing endpoint install (upstream --dry-run)"
  bash "${INSTALLER}" --dry-run --profile "${SOVEREIGN_OS_GHOSTPROXY_PROFILE}" --mode "${GHOSTPROXY_MODE}"
  log_warn "  no changes made. Set SOVEREIGN_OS_CONFIRM_GHOSTPROXY_INSTALL=YES to apply."
  emit_summary report-only
  exit 0
fi

log_info "  applying: upstream endpoint install (profile=${SOVEREIGN_OS_GHOSTPROXY_PROFILE} mode=${GHOSTPROXY_MODE})"
if ! bash "${INSTALLER}" --profile "${SOVEREIGN_OS_GHOSTPROXY_PROFILE}" --mode "${GHOSTPROXY_MODE}" --yes; then
  log_error "root-modules install failed — see upstream output above."
  emit_summary install-failed
  exit 1
fi

log_info "  verifying: upstream --check (read-only)"
if ! bash "${INSTALLER}" --check --profile "${SOVEREIGN_OS_GHOSTPROXY_PROFILE}" --mode "${GHOSTPROXY_MODE}"; then
  log_warn "  post-install --check reported drift; inspect upstream output."
fi

log_info "  root-modules endpoint envelope installed (proxy half OFF)."
emit_summary installed
