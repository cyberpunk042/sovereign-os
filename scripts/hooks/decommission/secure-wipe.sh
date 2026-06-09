#!/usr/bin/env bash
# scripts/hooks/decommission/secure-wipe.sh
#
# Final decommission step: cryptographic wipe of the underlying
# storage devices. Idempotent. Most destructive — confirms via
# SOVEREIGN_OS_CONFIRM_DESTROY=YES AND interactive prompt.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_WIPE_DEVICES:=}"

log_step_header "secure-wipe" "device-level secure wipe"

require_root

if [ "${SOVEREIGN_OS_CONFIRM_DESTROY:-}" != "YES" ]; then
  log_error "secure-wipe requires SOVEREIGN_OS_CONFIRM_DESTROY=YES env var"
  exit 1
fi

if [ -z "${SOVEREIGN_OS_WIPE_DEVICES}" ]; then
  log_error "SOVEREIGN_OS_WIPE_DEVICES env var must list devices to wipe"
  log_error "  Example: SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1'"
  exit 1
fi

if ! confirm "Wipe devices: ${SOVEREIGN_OS_WIPE_DEVICES}? ALL DATA UNRECOVERABLE." default-no; then
  log_info "aborted by operator"
  exit 1
fi

# Run a wipe command, indent its output, and return the command's OWN exit
# status (not the trailing `sed`'s — `cmd | sed` would otherwise always look
# successful and mask a failed wipe). Uses PIPESTATUS so a failed erase is
# detected instead of silently reported as success.
run_wipe() {
  "$@" 2>&1 | sed 's/^/    /'
  return "${PIPESTATUS[0]}"
}

wipe_failures=0
for dev in ${SOVEREIGN_OS_WIPE_DEVICES}; do
  if [ ! -b "${dev}" ]; then
    log_warn "skipping ${dev} (not a block device)"
    continue
  fi
  log_info "wiping ${dev}"
  dev_ok=0
  if [[ "${dev}" =~ nvme ]]; then
    # NVMe: prefer hardware secure-erase; fall back to blkdiscard both when the
    # nvme tool is ABSENT (previously a silent no-op — the device was never
    # wiped) and when the secure-erase itself fails.
    if command -v nvme >/dev/null 2>&1; then
      log_info "  attempting nvme format with secure-erase"
      if run_wipe nvme format "${dev}" --ses=1 --force; then
        dev_ok=1
      else
        log_warn "  nvme secure-erase failed; falling back to blkdiscard"
        if run_wipe blkdiscard "${dev}"; then dev_ok=1; fi
      fi
    else
      log_warn "  nvme-cli not installed; falling back to blkdiscard (install nvme-cli for hardware secure-erase)"
      if run_wipe blkdiscard "${dev}"; then dev_ok=1; fi
    fi
  else
    # SATA/HDD: blkdiscard if SSD, dd zero if rotational (slow but reliable)
    if [ -f "/sys/block/$(basename "${dev}")/queue/rotational" ] && [ "$(cat "/sys/block/$(basename "${dev}")/queue/rotational")" = "0" ]; then
      if run_wipe blkdiscard "${dev}"; then dev_ok=1; fi
    else
      log_warn "  rotational device; writing zeros (this can take hours)"
      if dd if=/dev/zero of="${dev}" bs=1M status=progress 2>&1 | tail -5; then dev_ok=1; fi
    fi
  fi
  if [ "${dev_ok}" -ne 1 ]; then
    log_error "  FAILED to wipe ${dev} — its data may still be RECOVERABLE"
    wipe_failures=$((wipe_failures + 1))
  fi
done

if [ "${wipe_failures}" -gt 0 ]; then
  log_error "secure-wipe FAILED for ${wipe_failures} device(s) — do NOT treat these drives as erased"
  exit 1
fi
log_info "secure-wipe complete"
