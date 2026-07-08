#!/usr/bin/env bash
# scripts/hooks/pre-install/preflight-tpm.sh
#
# Pre-install TPM2 + MOK enrollment readiness check. Runs from the
# live-USB / installer environment BEFORE writing to the target disk.
#
# Profile-aware: if the active profile declares a secure-boot posture that needs
# a TPM + key enrollment —
#   kernel.cmdline.secure_boot: signed   (or)  shim   (SDD-015 enum)
# this hook is required to PASS. For posture none/unset it emits SKIP, exits 0.
#
# What it validates (when secure_boot is required):
#   • /dev/tpm0 or /dev/tpmrm0 present
#   • tpm2_pcrread reports a valid PCR bank (sha256)
#   • SOVEREIGN_OS_MOK_KEY + SOVEREIGN_OS_MOK_CERT either both unset
#     (auto-generate at sign step) or both readable files
#   • UEFI variables filesystem mounted at /sys/firmware/efi/efivars
#     (or efivarfs auto-mountable)
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="preflight-tpm"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "TPM2 + MOK enrollment readiness (profile=${SOVEREIGN_OS_PROFILE})"

secure_boot="$(profile_field kernel.cmdline.secure_boot)"

# SDD-015 posture enum is none/shim/signed (NOT 'true'). TPM + key-enrollment
# readiness is required for the postures that actually enroll keys (signed, shim);
# none/unset needs no TPM. The previous '!= true' check matched no real posture
# value, so this preflight ALWAYS skipped — secure-boot installs proceeded with
# zero TPM/UEFI readiness validation.
case "${secure_boot}" in
  signed | shim)
    log_info "  secure_boot=${secure_boot} — TPM + UEFI readiness checks required"
    ;;
  *)
    log_info "  SKIP — secure_boot is '${secure_boot:-unset}' (not signed/shim; no TPM preflight needed)"
    log_info "${STEP_ID}: SKIP"
    exit 0
    ;;
esac

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would check:"
  log_info "  • /dev/tpm0 or /dev/tpmrm0 present"
  log_info "  • tpm2_pcrread succeeds against sha256 bank"
  log_info "  • UEFI variables filesystem mounted"
  log_info "  • MOK key+cert env coherence (both set or both unset)"
  exit 0
fi

fail=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_info "  PASS — ${desc}"
  else
    log_error "  FAIL — ${desc}"
    fail=$((fail + 1))
  fi
}

# 1. TPM device node present
check "TPM device node present (/dev/tpm0 or /dev/tpmrm0)" \
  bash -c "[ -e /dev/tpm0 ] || [ -e /dev/tpmrm0 ]"

# 2. tpm2-tools available + can read a PCR
if command -v tpm2_pcrread >/dev/null 2>&1; then
  check "tpm2_pcrread reports sha256 bank" \
    bash -c "tpm2_pcrread sha256:0 2>/dev/null | grep -q '^\s*0\s*:'"
else
  log_warn "  SKIP — tpm2-tools not installed (operator must install before secure-boot install)"
fi

# 3. EFI variables filesystem (needed for shim/MOK enrollment)
if [ -d /sys/firmware/efi ]; then
  check "UEFI firmware booted (efi vars dir present)" \
    test -d /sys/firmware/efi
  if [ ! -d /sys/firmware/efi/efivars ] || [ -z "$(ls /sys/firmware/efi/efivars 2>/dev/null)" ]; then
    log_warn "  efivarfs not mounted; mount it: mount -t efivarfs efivarfs /sys/firmware/efi/efivars"
  else
    log_info "  PASS — efivarfs mounted + populated"
  fi
else
  log_error "  FAIL — no /sys/firmware/efi (booted via BIOS/legacy?)"
  fail=$((fail + 1))
fi

# 4. MOK key/cert env coherence
if [ -n "${SOVEREIGN_OS_MOK_KEY:-}${SOVEREIGN_OS_MOK_CERT:-}" ]; then
  if [ -n "${SOVEREIGN_OS_MOK_KEY:-}" ] && [ -n "${SOVEREIGN_OS_MOK_CERT:-}" ]; then
    check "MOK key file readable: ${SOVEREIGN_OS_MOK_KEY}" \
      test -r "${SOVEREIGN_OS_MOK_KEY}"
    check "MOK cert file readable: ${SOVEREIGN_OS_MOK_CERT}" \
      test -r "${SOVEREIGN_OS_MOK_CERT}"
  else
    log_error "  FAIL — only one of SOVEREIGN_OS_MOK_{KEY,CERT} is set; must be both or neither"
    fail=$((fail + 1))
  fi
else
  log_info "  MOK key+cert unset — step 08 will auto-generate (operator must enroll manually after install)"
fi

if [ "${fail}" -eq 0 ]; then
  log_info "${STEP_ID}: PASS"
  emit_metric sovereign_os_pre_install_preflight_total 1 \
    "hook=\"preflight-tpm\",result=\"pass\""
  exit 0
else
  log_error "${STEP_ID}: FAIL (${fail} issue(s))"
  emit_metric sovereign_os_pre_install_preflight_total 1 \
    "hook=\"preflight-tpm\",result=\"fail\""
  exit 1
fi
