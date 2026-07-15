#!/usr/bin/env bash
# scripts/hooks/post-install/apply-workstation-hardening.sh
#
# Round 104: applies sovereign-os hardening config to role-workstation
# profiles (sain-01, old-workstation). Parallel to apply-server-hardening
# but with a workstation threat model:
#
#   - SHARED with server: auditd (universal), pwquality (sudo/su),
#     unattended-upgrades (security-only)
#   - WORKSTATION-SPECIFIC: looser sshd (allows password auth as fallback
#     since operator works at console; agent + tcp forwarding allowed)
#   - DELIBERATELY OMITTED: fail2ban (workstation not internet-facing;
#     Tetragon perimeter on sain-01 handles intrusion detection in-kernel)
#
# Idempotent + DEST_PREFIX-aware + DRY-RUN-safe — same contract as
# apply-server-hardening (SDD-024).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"

# ---------- python3 resolver ----------
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="apply-workstation-hardening"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "drop sovereign-os hardening config (role-workstation profiles)"

has_role_workstation="$(${PYTHON3} -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f) or {}
mixins = data.get('mixins') or []
print('yes' if 'role-workstation' in mixins else 'no')
")"

if [ "${has_role_workstation}" != "yes" ]; then
  log_info "  SKIP — profile '${SOVEREIGN_OS_PROFILE}' does not compose role-workstation mixin"
  emit_metric sovereign_os_post_install_workstation_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"skipped\""
  exit 0
fi

log_info "  applies to profile=${SOVEREIGN_OS_PROFILE} (role-workstation)"

server_src="${__REPO_ROOT}/config/server"
ws_src="${__REPO_ROOT}/config/workstation"
require_dir "${server_src}"
require_dir "${ws_src}"

: "${SOVEREIGN_OS_HARDENING_DEST_PREFIX:=}"

# Source-dir + filename + destination triples. server/ supplies the 3
# universal drop-ins (auditd, pwquality, unattended-upgrades);
# workstation/ supplies the workstation-tuned sshd. No fail2ban.
declare -a actions=(
  "${server_src}|auditd.rules|${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/audit/rules.d/sovereign-os.rules"
  "${server_src}|unattended-upgrades.conf|${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/apt/apt.conf.d/52sovereign-os-unattended.conf"
  "${ws_src}|sshd.conf|${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/ssh/sshd_config.d/50sovereign-os.conf"
  "${server_src}|pwquality.conf|${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/security/pwquality.conf.d/50sovereign-os.conf"
)

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would copy:"
  for a in "${actions[@]}"; do
    IFS='|' read -r asrc afile adst <<< "${a}"
    log_info "  ${asrc}/${afile}  →  ${adst}"
  done
  emit_metric sovereign_os_post_install_workstation_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  exit 0
fi

applied=0
unchanged=0
fail=0
for a in "${actions[@]}"; do
  IFS='|' read -r asrc afile adst <<< "${a}"
  src="${asrc}/${afile}"
  if [ ! -r "${src}" ]; then
    log_error "  MISSING source: ${src}"
    fail=$((fail + 1))
    continue
  fi
  mkdir -p "$(dirname "${adst}")" 2>/dev/null || true
  if [ -f "${adst}" ] && cmp -s "${src}" "${adst}"; then
    log_info "  unchanged: ${adst}"
    unchanged=$((unchanged + 1))
    continue
  fi
  if install -m 0644 "${src}" "${adst}" 2>/dev/null; then
    log_info "  applied:   ${adst}"
    applied=$((applied + 1))
  else
    log_error "  FAILED to install: ${adst} (permission? path?)"
    fail=$((fail + 1))
  fi
done

if [ -n "${SOVEREIGN_OS_HARDENING_DEST_PREFIX:-}" ]; then
  log_info "DEST_PREFIX is set; skipping service reload (target tree, not running system)"
elif [ "${applied}" -gt 0 ] && [ "${fail}" -eq 0 ]; then
  log_info "reloading affected services (best-effort)"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active --quiet auditd && {
      augenrules --load 2>/dev/null || systemctl restart auditd 2>/dev/null || \
        log_warn "  could not reload auditd"
    }
    systemctl is-active --quiet ssh && {
      if sshd -t 2>/dev/null; then
        systemctl reload ssh 2>/dev/null || \
          log_warn "  could not reload ssh"
      else
        log_error "  sshd -t failed; NOT reloading ssh (would lock operator out)"
        log_error "  inspect: /etc/ssh/sshd_config.d/50sovereign-os.conf"
        fail=$((fail + 1))
      fi
    }
  else
    log_warn "  systemctl not available; skipping reload"
  fi
fi

if [ "${fail}" -gt 0 ]; then
  log_error "${STEP_ID}: ${fail} drop-in(s) failed; ${applied} applied; ${unchanged} unchanged"
  emit_metric sovereign_os_post_install_workstation_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  exit 1
fi

log_info "${STEP_ID}: ${applied} applied, ${unchanged} unchanged, 0 failed"
emit_metric sovereign_os_post_install_workstation_hardening_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
emit_metric sovereign_os_post_install_workstation_hardening_applied "${applied}" \
  "profile=\"${SOVEREIGN_OS_PROFILE}\""
