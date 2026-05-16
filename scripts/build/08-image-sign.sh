#!/usr/bin/env bash
# scripts/build/08-image-sign.sh — sign the produced image + bootloader
# per profile.kernel.cmdline.secure_boot.
#
# Skipped if secure_boot=disabled. For 'shim' or 'signed', the
# operator's MOK (or distro key) is used. MOK key generation is
# operator-side (out of scope here); this step uses the configured
# key path from SOVEREIGN_OS_MOK_KEY / SOVEREIGN_OS_MOK_CERT env vars.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"

STEP_ID="08-image-sign"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_image="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
if [ -f "${env_image}" ]; then
  # shellcheck disable=SC1090
  . "${env_image}"
fi

secure_boot="$(profile_field kernel.cmdline.secure_boot)"
: "${secure_boot:=disabled}"

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "sign image (secure_boot=${secure_boot})"
state_step_start "${STEP_ID}" "${inputs_hash}"

case "${secure_boot}" in
  disabled)
    log_info "secure_boot=disabled; skipping signing"
    state_step_complete "${STEP_ID}"
    exit 0
    ;;
  shim)
    log_info "secure_boot=shim; relying on Microsoft-signed shim chain"
    log_info "no operator signing required for shim path"
    state_step_complete "${STEP_ID}"
    exit 0
    ;;
  signed)
    log_info "secure_boot=signed; signing with operator MOK"
    ;;
  *)
    log_error "unknown secure_boot value: ${secure_boot}"
    state_step_fail "${STEP_ID}" "unknown-secure-boot"
    exit 1
    ;;
esac

# ---- MOK signing path ----
require_command sbsign
require_command sbverify

: "${SOVEREIGN_OS_MOK_KEY:?SOVEREIGN_OS_MOK_KEY env var required for secure_boot=signed (path to MOK.priv)}"
: "${SOVEREIGN_OS_MOK_CERT:?SOVEREIGN_OS_MOK_CERT env var required for secure_boot=signed (path to MOK.der/crt)}"

require_file "${SOVEREIGN_OS_MOK_KEY}"
require_file "${SOVEREIGN_OS_MOK_CERT}"

if [ -z "${SOVEREIGN_OS_IMAGE_DIR:-}" ] || [ ! -d "${SOVEREIGN_OS_IMAGE_DIR}" ]; then
  log_error "image dir not found (set SOVEREIGN_OS_IMAGE_DIR or rerun step 07)"
  state_step_fail "${STEP_ID}" "no-image"
  exit 1
fi

# Sign every kernel + EFI binary in the image
signed_count=0
while IFS= read -r f; do
  log_info "signing: ${f}"
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_warn "  DRY-RUN — would sbsign"
  else
    sbsign --key "${SOVEREIGN_OS_MOK_KEY}" --cert "${SOVEREIGN_OS_MOK_CERT}" \
      --output "${f}.signed" "${f}"
    mv "${f}.signed" "${f}"
    sbverify --cert "${SOVEREIGN_OS_MOK_CERT}" "${f}" || {
      log_error "verification failed for ${f}"
      state_step_fail "${STEP_ID}" "sbverify-failed"
      exit 1
    }
    signed_count=$((signed_count + 1))
  fi
done < <(find "${SOVEREIGN_OS_IMAGE_DIR}" \( -name 'vmlinuz*' -o -name '*.efi' -o -name 'bootx64.efi' \) 2>/dev/null)

log_info "signed ${signed_count} binaries"

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
