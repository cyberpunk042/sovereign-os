#!/usr/bin/env bash
# tests/nspawn/test_apply_workstation_hardening.sh
#
# Layer 3 test for apply-workstation-hardening.sh (Round 104).
# Parallels test_apply_server_hardening.sh; verifies workstation hook
# behavior across SKIP / DRY-RUN / live-apply with DEST_PREFIX.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

HOOK="${__REPO_ROOT}/scripts/hooks/post-install/apply-workstation-hardening.sh"

echo "tests/nspawn/test_apply_workstation_hardening.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

mdir="${tmp}/textfile_collector"; mkdir -p "${mdir}"

# ---------- SKIP on non-role-workstation profile (headless) ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=headless \
       SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "SKIP — profile 'headless' does not compose role-workstation" <<< "${out}"; then
  ok "SKIPs cleanly on role-server profile (headless)"
else
  ko "SKIP gate broken (rc=${rc})"
fi

# ---------- SKIP on minimal too ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=minimal \
       SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "SKIP" <<< "${out}"; then
  ok "SKIPs cleanly on minimal (role-headless)"
else
  ko "SKIP minimal broken"
fi

# ---------- DRY-RUN on sain-01 ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_DRY_RUN=1 \
       SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "applies to profile=sain-01 (role-workstation)" <<< "${out}"; then
  ok "DRY-RUN on sain-01 detects role-workstation"
else
  ko "role-workstation detection broken"
fi
# 4 drop-ins (not 5 — no fail2ban for workstation)
copy_lines="$(grep -c "would copy:\|→" <<< "${out}" || true)"
if grep -q "auditd.rules.*→.*/etc/audit" <<< "${out}" && \
   grep -q "unattended-upgrades.conf.*→" <<< "${out}" && \
   grep -q "workstation/sshd.conf.*→.*sshd_config.d" <<< "${out}" && \
   grep -q "pwquality.conf.*→" <<< "${out}"; then
  ok "DRY-RUN lists all 4 workstation drop-ins"
else
  ko "DRY-RUN action list wrong"
fi
# No fail2ban
if ! grep -q "fail2ban" <<< "${out}"; then
  ok "DRY-RUN omits fail2ban (workstation isn't internet-facing)"
else
  ko "DRY-RUN incorrectly includes fail2ban"
fi

# ---------- DRY-RUN on old-workstation ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=old-workstation \
       SOVEREIGN_OS_DRY_RUN=1 \
       SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       "${HOOK}" 2>&1)"
set -e
if grep -q "applies to profile=old-workstation (role-workstation)" <<< "${out}"; then
  ok "DRY-RUN works on old-workstation profile too"
else
  ko "old-workstation profile not detected"
fi

# ---------- LIVE apply via DEST_PREFIX ----------
target="${tmp}/target-ws"; mkdir -p "${target}"
set +e
out="$(SOVEREIGN_OS_PROFILE=sain-01 \
       SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" \
       SOVEREIGN_OS_METRICS_DIR="${tmp}/live-mdir" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "4 applied, 0 unchanged, 0 failed" <<< "${out}"; then
  ok "live apply on sain-01 → 4 applied (not 5; no fail2ban)"
else
  ko "live apply broken (rc=${rc}); out=${out:0:200}"
fi

# Workstation-specific sshd MUST come from config/workstation/, not config/server/
ws_sshd="${target}/etc/ssh/sshd_config.d/50sovereign-os.conf"
if [ -f "${ws_sshd}" ]; then
  ok "workstation sshd drop-in landed"
else
  ko "workstation sshd missing"
fi
if grep -q "PasswordAuthentication         yes" "${ws_sshd}"; then
  ok "workstation sshd has PasswordAuthentication yes (workstation-specific)"
else
  ko "workstation sshd lacks password fallback"
fi
if grep -q "AllowAgentForwarding           yes" "${ws_sshd}"; then
  ok "workstation sshd allows agent forwarding (dev hop pattern)"
else
  ko "workstation sshd blocks agent forwarding (wrong for workstation)"
fi

# fail2ban file MUST NOT be present in target tree
if [ ! -f "${target}/etc/fail2ban/jail.d/sovereign-os.local" ]; then
  ok "fail2ban drop-in NOT present (correctly omitted for workstation)"
else
  ko "fail2ban incorrectly applied to workstation"
fi

# Idempotency
set +e
out2="$(SOVEREIGN_OS_PROFILE=sain-01 \
        SOVEREIGN_OS_HARDENING_DEST_PREFIX="${target}" \
        SOVEREIGN_OS_METRICS_DIR="${tmp}/live-mdir" \
        "${HOOK}" 2>&1)"
set -e
if grep -q "0 applied, 4 unchanged, 0 failed" <<< "${out2}"; then
  ok "idempotent re-run → 0 applied / 4 unchanged"
else
  ko "idempotency broken"
fi

# Layer B success counter
prom="${tmp}/live-mdir/sovereign-os-post.prom"
if grep -q 'sovereign_os_post_install_workstation_hardening_total{profile="sain-01",result="success"}' "${prom}" 2>/dev/null; then
  ok "live apply emits workstation_hardening success counter"
else
  ko "success counter missing"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_apply_workstation_hardening: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
