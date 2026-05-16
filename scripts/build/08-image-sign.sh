#!/usr/bin/env bash
# scripts/build/08-image-sign.sh — sign the produced image + bootloader
# per profile.kernel.cmdline.secure_boot.
#
# Per SDD-015 (Q-006 resolution), the secure-boot posture is a 3-level
# enum:
#   none    — no signing (dev / throwaway). Step is a no-op.
#   shim    — Microsoft-signed shim chains to operator MOK → kernel.
#             Step sbsign's vmlinuz + EFI binaries with operator MOK.
#   signed  — direct sbsign with operator's Platform Key, no shim.
#             Step sbsign's everything with PK; falls back to MOK
#             with a warning if PK env vars unset.
#
# Operator-supplied keys (NEVER stored in repo):
#   SOVEREIGN_OS_PK_KEY    Platform Key (preferred for signed)
#   SOVEREIGN_OS_PK_CERT   Platform Key cert
#   SOVEREIGN_OS_MOK_KEY   MOK private key (required for shim;
#                          fallback for signed)
#   SOVEREIGN_OS_MOK_CERT  MOK certificate
#
# Honors SOVEREIGN_OS_DRY_RUN=1 (logs intent, doesn't sbsign).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="08-image-sign"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_image="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
if [ -f "${env_image}" ]; then
  # shellcheck disable=SC1090
  . "${env_image}"
fi

secure_boot="$(profile_field kernel.cmdline.secure_boot)"
: "${secure_boot:=none}"

# Legacy alias: 'disabled' → 'none' (some older profiles used this)
if [ "${secure_boot}" = "disabled" ]; then
  log_warn "secure_boot=disabled is a legacy alias; SDD-015 enum is none/shim/signed"
  secure_boot="none"
fi

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "sign image (secure_boot=${secure_boot})"
state_step_start "${STEP_ID}" "${inputs_hash}"

emit_sign_metric() {
  emit_metric sovereign_os_build_step_sign_total 1 \
    "posture=\"${secure_boot}\",result=\"$1\""
}

case "${secure_boot}" in
  none)
    log_info "secure_boot=none; skipping signing (per SDD-015 posture=none)"
    emit_sign_metric skip
    state_step_complete "${STEP_ID}"
    exit 0
    ;;
  shim)
    log_info "secure_boot=shim; sbsign'ing vmlinuz/EFI with operator MOK"
    : "${SOVEREIGN_OS_MOK_KEY:?SOVEREIGN_OS_MOK_KEY required for shim path}"
    : "${SOVEREIGN_OS_MOK_CERT:?SOVEREIGN_OS_MOK_CERT required for shim path}"
    sign_key="${SOVEREIGN_OS_MOK_KEY}"
    sign_cert="${SOVEREIGN_OS_MOK_CERT}"
    ;;
  signed)
    if [ -n "${SOVEREIGN_OS_PK_KEY:-}" ] && [ -n "${SOVEREIGN_OS_PK_CERT:-}" ]; then
      log_info "secure_boot=signed; sbsign'ing with operator Platform Key (preferred chain per SDD-015)"
      sign_key="${SOVEREIGN_OS_PK_KEY}"
      sign_cert="${SOVEREIGN_OS_PK_CERT}"
    elif [ -n "${SOVEREIGN_OS_MOK_KEY:-}" ] && [ -n "${SOVEREIGN_OS_MOK_CERT:-}" ]; then
      log_warn "secure_boot=signed but PK env vars unset — falling back to MOK key"
      log_warn "  operator must enroll the MOK cert via mokutil post-install"
      sign_key="${SOVEREIGN_OS_MOK_KEY}"
      sign_cert="${SOVEREIGN_OS_MOK_CERT}"
    else
      log_error "secure_boot=signed requires SOVEREIGN_OS_PK_{KEY,CERT} or SOVEREIGN_OS_MOK_{KEY,CERT}"
      emit_sign_metric fail
      state_step_fail "${STEP_ID}" "no-signing-key"
      exit 1
    fi
    ;;
  *)
    log_error "unknown secure_boot value: ${secure_boot} (SDD-015 enum: none/shim/signed)"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "unknown-secure-boot"
    exit 1
    ;;
esac

# ---- common signing path (shim + signed) ----

# Dry-run: log intent + emit metric + exit before require_command checks
# (operator can dry-run on a build host without sbsign installed).
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would sbsign with key=${sign_key} cert=${sign_cert}"
  log_info "DRY-RUN — would sbverify each signed binary"
  emit_sign_metric skip
  state_step_complete "${STEP_ID}"
  exit 0
fi

require_command sbsign
require_command sbverify

require_file "${sign_key}"
require_file "${sign_cert}"

if [ -z "${SOVEREIGN_OS_IMAGE_DIR:-}" ] || [ ! -d "${SOVEREIGN_OS_IMAGE_DIR}" ]; then
  log_error "image dir not found (set SOVEREIGN_OS_IMAGE_DIR or rerun step 07)"
  emit_sign_metric fail
  state_step_fail "${STEP_ID}" "no-image"
  exit 1
fi

# Sign every kernel + EFI binary in the image
signed_count=0
while IFS= read -r f; do
  log_info "signing: ${f}"
  sbsign --key "${sign_key}" --cert "${sign_cert}" \
    --output "${f}.signed" "${f}"
  mv "${f}.signed" "${f}"
  sbverify --cert "${sign_cert}" "${f}" || {
    log_error "verification failed for ${f}"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "sbverify-failed"
    exit 1
  }
  signed_count=$((signed_count + 1))
done < <(find "${SOVEREIGN_OS_IMAGE_DIR}" \( -name 'vmlinuz*' -o -name '*.efi' -o -name 'bootx64.efi' \) 2>/dev/null)

log_info "signed ${signed_count} binaries with ${secure_boot}-path key"
emit_sign_metric success

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
