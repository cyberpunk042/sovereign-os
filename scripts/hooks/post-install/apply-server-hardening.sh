#!/usr/bin/env bash
# scripts/hooks/post-install/apply-server-hardening.sh
#
# Round 96: applies sovereign-os hardening config to role-server
# profiles (currently: headless). Drops in:
#   - /etc/audit/rules.d/sovereign-os.rules
#   - /etc/fail2ban/jail.d/sovereign-os.local
#   - /etc/apt/apt.conf.d/52sovereign-os-unattended.conf
#
# Idempotent: re-running produces the same end state. Honors
# SOVEREIGN_OS_DRY_RUN=1. Emits Layer B counters per SDD-016/023.
#
# Only runs when the active profile composes the role-server mixin.
# Other profiles SKIP cleanly with explanatory log.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="apply-server-hardening"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "drop sovereign-os hardening config (role-server profiles)"

# Detect role-server membership via the profile YAML's mixins list.
# python3 reads the file directly; no need to walk the resolved profile.
has_role_server="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f) or {}
mixins = data.get('mixins') or []
print('yes' if 'role-server' in mixins else 'no')
")"

if [ "${has_role_server}" != "yes" ]; then
  log_info "  SKIP — profile '${SOVEREIGN_OS_PROFILE}' does not compose role-server mixin"
  emit_metric sovereign_os_post_install_server_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"skipped\""
  exit 0
fi

log_info "  applies to profile=${SOVEREIGN_OS_PROFILE} (role-server)"

src_dir="${__REPO_ROOT}/config/server"
require_dir "${src_dir}"

# Destination prefix override (default empty = absolute /etc/* paths).
# Operators applying hardening into a chroot / container / image
# building tree set this to a target root, e.g.:
#   SOVEREIGN_OS_HARDENING_DEST_PREFIX=/mnt/target sovereign-osctl maintenance ...
# The hook then writes to ${PREFIX}/etc/audit/rules.d/...  etc.
: "${SOVEREIGN_OS_HARDENING_DEST_PREFIX:=}"

declare -a actions=(
  "auditd.rules:${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/audit/rules.d/sovereign-os.rules"
  "fail2ban-jail.local:${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/fail2ban/jail.d/sovereign-os.local"
  "unattended-upgrades.conf:${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/apt/apt.conf.d/52sovereign-os-unattended.conf"
  "sshd.conf:${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/ssh/sshd_config.d/50sovereign-os.conf"
  "pwquality.conf:${SOVEREIGN_OS_HARDENING_DEST_PREFIX}/etc/security/pwquality.conf.d/50sovereign-os.conf"
)

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would copy:"
  for a in "${actions[@]}"; do
    log_info "  ${src_dir}/${a%:*}  →  ${a#*:}"
  done
  emit_metric sovereign_os_post_install_server_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  exit 0
fi

# Apply each drop-in. Idempotent: if content is unchanged, no-op.
applied=0
unchanged=0
fail=0
for a in "${actions[@]}"; do
  src="${src_dir}/${a%:*}"
  dst="${a#*:}"
  if [ ! -r "${src}" ]; then
    log_error "  MISSING source: ${src}"
    fail=$((fail + 1))
    continue
  fi
  mkdir -p "$(dirname "${dst}")" 2>/dev/null || true
  if [ -f "${dst}" ] && cmp -s "${src}" "${dst}"; then
    log_info "  unchanged: ${dst}"
    unchanged=$((unchanged + 1))
    continue
  fi
  if install -m 0644 "${src}" "${dst}" 2>/dev/null; then
    log_info "  applied:   ${dst}"
    applied=$((applied + 1))
  else
    log_error "  FAILED to install: ${dst} (permission? path?)"
    fail=$((fail + 1))
  fi
done

# Reload services where applicable. Best-effort: in chroot / container,
# systemctl may not be wired — that's not a failure of this hook, just
# an environmental fact, so we warn instead of fail.
#
# When DEST_PREFIX is set we wrote into a target tree, not the running
# system; reloading services on the build host would be wrong.
if [ -n "${SOVEREIGN_OS_HARDENING_DEST_PREFIX:-}" ]; then
  log_info "DEST_PREFIX is set; skipping service reload (target tree, not running system)"
elif [ "${applied}" -gt 0 ] && [ "${fail}" -eq 0 ]; then
  log_info "reloading affected services (best-effort)"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active --quiet auditd && {
      augenrules --load 2>/dev/null || systemctl restart auditd 2>/dev/null || \
        log_warn "  could not reload auditd (manual: 'augenrules --load' or 'systemctl restart auditd')"
    }
    systemctl is-active --quiet fail2ban && {
      systemctl reload fail2ban 2>/dev/null || \
        log_warn "  could not reload fail2ban (manual: 'systemctl reload fail2ban')"
    }
    systemctl is-active --quiet ssh && {
      # SSH reload — drop in is sshd_config.d/*.conf, sshd parses on reload
      # Validate config syntax FIRST to avoid locking the operator out
      if sshd -t 2>/dev/null; then
        systemctl reload ssh 2>/dev/null || \
          log_warn "  could not reload ssh (manual: 'systemctl reload ssh')"
      else
        log_error "  sshd -t failed; NOT reloading ssh (would lock operator out)"
        log_error "  inspect: /etc/ssh/sshd_config.d/50sovereign-os.conf"
        fail=$((fail + 1))
      fi
    }
    # unattended-upgrades is timer-driven; no daemon to reload
  else
    log_warn "  systemctl not available (chroot/container?); skipping reload"
  fi
fi

if [ "${fail}" -gt 0 ]; then
  log_error "${STEP_ID}: ${fail} drop-in(s) failed; ${applied} applied; ${unchanged} unchanged"
  emit_metric sovereign_os_post_install_server_hardening_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  exit 1
fi

log_info "${STEP_ID}: ${applied} applied, ${unchanged} unchanged, 0 failed"
emit_metric sovereign_os_post_install_server_hardening_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
emit_metric sovereign_os_post_install_server_hardening_applied "${applied}" \
  "profile=\"${SOVEREIGN_OS_PROFILE}\""
