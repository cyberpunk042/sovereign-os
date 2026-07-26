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
  # /dev/tpmrm0 is crw-rw---- tss:tss. Unprivileged, tpm2_pcrread fails with
  # "Permission denied" on the TCTI device — which is NOT "this TPM has no
  # sha256 bank". Reporting the latter sent the operator hunting a firmware
  # problem that does not exist; the real build runs as root and reads it fine.
  if [ ! -r /dev/tpmrm0 ] && [ ! -r /dev/tpm0 ] && [ "$(id -u)" -ne 0 ]; then
    log_warn "  SKIP — TPM device is tss-group only and this preflight is not root"
    log_warn "  (run: sudo … preflight, or add $(id -un) to the 'tss' group to check it here)"
    log_warn "  the build itself runs as root and reads the TPM normally"
  else
    check "tpm2_pcrread reports sha256 bank" \
      bash -c "tpm2_pcrread sha256:0 2>/dev/null | grep -q '^\s*0\s*:'"
  fi
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
elif [ -f /etc/sovereign-os/keys/mok.key ] && [ -f /etc/sovereign-os/keys/mok.crt ]; then
  log_info "  MOK env unset, but an operator key exists at /etc/sovereign-os/keys — the build will use it"
elif [ -d /etc/sovereign-os/keys ] && [ ! -r /etc/sovereign-os/keys ]; then
  # The key dir is 0700 root by design. Unprivileged we cannot see INTO it, so
  # "no key" would be a guess — and a wrong one here sends the operator off to
  # regenerate a key that already exists.
  log_info "  operator key dir exists but is not readable as $(id -un) (0700 root, expected)"
  log_info "  the build runs as root and will find/mint the key itself"
else
  # This branch used to claim "step 08 will auto-generate", which was FALSE:
  # no step generated anything, and step 05 hard-failed on the missing key
  # LONG before 08 would have run — so the operator lost a 30+ minute kernel
  # compile to a check that could have run here in milliseconds (reported
  # 2026-07-25). scripts/build/lib/operator-keys.sh now mints the key, but it
  # can only do so as root, so warn precisely when that will not happen.
  if [ "$(id -u)" -eq 0 ]; then
    log_info "  no operator key yet — the build will mint one at /etc/sovereign-os/keys (SDD-015; enroll with mokutil after install)"
  else
    log_warn "  no operator key at /etc/sovereign-os/keys, and this preflight is not root"
    log_warn "  the build mints one automatically WHEN RUN AS ROOT (panel: pkexec; CLI: sudo)"
    log_warn "  an unprivileged build will fail at step 05 with posture secure_boot=${secure_boot}"
  fi
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
