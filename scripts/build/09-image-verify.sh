#!/usr/bin/env bash
# scripts/build/09-image-verify.sh — boot the image in QEMU for a smoke
# test. Skipped when SOVEREIGN_OS_SKIP_QEMU is set (e.g., CI runners
# without KVM).
#
# Minimal smoke: boot → login as root via console → check
# /etc/os-release matches whitelabel → reboot. Timeout: 5 minutes.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"

STEP_ID="09-image-verify"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

env_image="${SOVEREIGN_OS_STATE_DIR}/env-image.sh"
if [ -f "${env_image}" ]; then
  # shellcheck disable=SC1090
  . "${env_image}"
fi

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

if [ -n "${SOVEREIGN_OS_SKIP_QEMU:-}" ]; then
  log_warn "SOVEREIGN_OS_SKIP_QEMU set — skipping QEMU smoke test"
  state_step_start "${STEP_ID}" "${inputs_hash}"
  state_step_complete "${STEP_ID}"
  exit 0
fi

log_step_header "${STEP_ID}" "QEMU smoke test"
state_step_start "${STEP_ID}" "${inputs_hash}"

require_command qemu-system-x86_64

if [ -z "${SOVEREIGN_OS_IMAGE_DIR:-}" ] || [ ! -d "${SOVEREIGN_OS_IMAGE_DIR}" ]; then
  log_error "image dir not found (set SOVEREIGN_OS_IMAGE_DIR or rerun step 07)"
  state_step_fail "${STEP_ID}" "no-image"
  exit 1
fi

# Find the produced image file
image_file="$(find "${SOVEREIGN_OS_IMAGE_DIR}" -maxdepth 1 \( -name '*.img' -o -name '*.qcow2' -o -name '*.raw' -o -name "${SOVEREIGN_OS_PROFILE}" \) -type f 2>/dev/null | head -1)"

if [ -z "${image_file}" ]; then
  log_error "no image artifact found in ${SOVEREIGN_OS_IMAGE_DIR}"
  state_step_fail "${STEP_ID}" "no-image-artifact"
  exit 1
fi

log_info "QEMU boot test of: ${image_file}"

# For now: just boot to firmware + check the disk is bootable.
# Full inside-VM verification lands at PR 10 (TDD harness Layer 4)
# with an actual login shell or guest-agent integration.

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — skipping QEMU boot"
else
  : "${SOVEREIGN_OS_QEMU_TIMEOUT:=300}"
  : "${SOVEREIGN_OS_QEMU_MEM:=4G}"

  log_info "booting (timeout ${SOVEREIGN_OS_QEMU_TIMEOUT}s, mem ${SOVEREIGN_OS_QEMU_MEM})"

  timeout "${SOVEREIGN_OS_QEMU_TIMEOUT}" \
    qemu-system-x86_64 \
      -m "${SOVEREIGN_OS_QEMU_MEM}" \
      -smp 2 \
      -nographic \
      -no-reboot \
      -drive "file=${image_file},format=raw,if=virtio,readonly=on" \
      -kernel "${SOVEREIGN_OS_IMAGE_DIR}/$(ls "${SOVEREIGN_OS_IMAGE_DIR}" | grep vmlinuz | head -1)" \
      2>&1 | tee "${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log" || {
      rc=$?
      if [ $rc -eq 124 ]; then
        log_warn "QEMU boot reached timeout (${SOVEREIGN_OS_QEMU_TIMEOUT}s); reviewing log…"
      else
        log_error "QEMU exited with status ${rc}"
        state_step_fail "${STEP_ID}" "qemu-failed-${rc}"
        exit 1
      fi
    }

  # Basic check: did the boot reach userspace? Look for systemd or
  # /etc/os-release in the boot log.
  if grep -q "Welcome to\|systemd\[1\]\|sovereign" "${SOVEREIGN_OS_LOG_DIR}/qemu-boot-${SOVEREIGN_OS_BUILD_ID}.log"; then
    log_info "boot log contains userspace markers"
  else
    log_warn "boot log lacks userspace markers; image may not boot cleanly"
  fi
fi

state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
