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
  # Record 'dry-run', NOT 'completed' — completing here with the real
  # inputs_hash makes the next REAL run skip this step body entirely.
  state_step_dry_run "${STEP_ID}"
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

# ---- mkosi substrate: verify-in-place instead of signing loose files ----
# A mkosi disk image carries its boot binaries INSIDE the ESP partition,
# already signed at build time via [Validation] SecureBootKey= with the
# operator key (mkosi-emit.sh). There are no loose vmlinuz*/*.efi in the
# output dir to sbsign — the old find-based loop found nothing and failed
# with 'NO signable binaries' on the first real image (2026-06-10). The
# correct job here is to loop-mount the ESP read-only and sbverify every
# EFI binary against the operator cert — which doubles as a boot-chain
# sanity check (systemd-boot + UKI must both be present and signed).
raw_image="$(find "${SOVEREIGN_OS_IMAGE_DIR}" -maxdepth 1 -name '*.raw' 2>/dev/null | head -1)"
if [ -n "${raw_image}" ]; then
  log_info "mkosi disk image: ${raw_image}"
  log_info "boot binaries signed at image-build time (mkosi [Validation], operator cert) — verifying in place"
  require_root
  require_command losetup

  loopdev="$(losetup --find --show --read-only --partscan "${raw_image}")" || {
    log_error "losetup failed for ${raw_image}"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "losetup-failed"
    exit 1
  }
  esp_mnt="$(mktemp -d)"
  # shellcheck disable=SC2317  # body runs via the EXIT trap below, not inline
  cleanup_loop() {
    umount "${esp_mnt}" 2>/dev/null || true
    losetup -d "${loopdev}" 2>/dev/null || true
    rmdir "${esp_mnt}" 2>/dev/null || true
  }
  trap cleanup_loop EXIT

  # Find the vfat (ESP) partition rather than assuming an index.
  esp_part=""
  for part in "${loopdev}"p*; do
    [ -b "${part}" ] || continue
    if [ "$(blkid -o value -s TYPE "${part}" 2>/dev/null)" = "vfat" ]; then
      esp_part="${part}"
      break
    fi
  done
  if [ -z "${esp_part}" ]; then
    log_error "no vfat ESP partition found in ${raw_image}"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "no-esp"
    exit 1
  fi
  mount -o ro "${esp_part}" "${esp_mnt}"

  verified=0
  while IFS= read -r f; do
    if sbverify --cert "${sign_cert}" "${f}" >/dev/null 2>&1; then
      log_info "verified: ${f#"${esp_mnt}"/} ✓"
      verified=$((verified + 1))
    else
      log_error "signature verification FAILED for ${f#"${esp_mnt}"/} against ${sign_cert}"
      emit_sign_metric fail
      state_step_fail "${STEP_ID}" "sbverify-failed"
      exit 1
    fi
  done < <(find "${esp_mnt}" -iname '*.efi' 2>/dev/null)

  if [ "${verified}" -eq 0 ]; then
    log_error "no EFI binaries found inside the image ESP — image would not boot"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "esp-empty"
    exit 1
  fi
  log_info "ESP signature verification: ${verified} EFI binaries verified against operator cert"
  emit_sign_metric success
  state_step_complete "${STEP_ID}"
  log_info "step ${STEP_ID} complete"
  exit 0
fi

# Sign every kernel + EFI binary in the image
signed_count=0
while IFS= read -r f; do
  log_info "signing: ${f}"
  # Guard sbsign + mv the same way sbverify (below) is guarded: a bare
  # sbsign under set -e would abort the step on a bad key / unsignable
  # binary WITHOUT a result="fail" sample or state_step_fail, leaving the
  # build in 'started' limbo — and the carefully-instrumented verify one
  # line down would never be reached to report it.
  sbsign --key "${sign_key}" --cert "${sign_cert}" \
    --output "${f}.signed" "${f}" || {
    log_error "sbsign failed for ${f} (bad key/cert or unsignable binary)"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "sbsign-failed"
    exit 1
  }
  mv "${f}.signed" "${f}" || {
    log_error "could not replace ${f} with its signed copy"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "sbsign-mv-failed"
    exit 1
  }
  sbverify --cert "${sign_cert}" "${f}" || {
    log_error "verification failed for ${f}"
    emit_sign_metric fail
    state_step_fail "${STEP_ID}" "sbverify-failed"
    exit 1
  }
  signed_count=$((signed_count + 1))
done < <(find "${SOVEREIGN_OS_IMAGE_DIR}" \( -name 'vmlinuz*' -o -name '*.efi' -o -name 'bootx64.efi' \) 2>/dev/null)

# We only reach here for the shim/signed postures (none/unknown exited earlier).
# Signing ZERO binaries means the image will fail Secure Boot — but the loop
# above would otherwise report success. Fail loudly: either the image layout
# doesn't match the find patterns (vmlinuz* / *.efi) or step 07 produced no
# bootable artifacts.
if [ "${signed_count}" -eq 0 ]; then
  log_error "secure_boot=${secure_boot} but NO signable binaries found under ${SOVEREIGN_OS_IMAGE_DIR}"
  log_error "  (expected vmlinuz* / *.efi) — nothing was signed; the image would FAIL Secure Boot"
  emit_sign_metric fail
  state_step_fail "${STEP_ID}" "nothing-signed"
  exit 1
fi

log_info "signed ${signed_count} binaries with ${secure_boot}-path key"
emit_sign_metric success

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
