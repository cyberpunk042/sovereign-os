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

for dev in ${SOVEREIGN_OS_WIPE_DEVICES}; do
  if [ ! -b "${dev}" ]; then
    log_warn "skipping ${dev} (not a block device)"
    continue
  fi
  log_info "wiping ${dev}"
  # NVMe: prefer hardware secure-erase if supported
  if [[ "${dev}" =~ nvme ]]; then
    if command -v nvme >/dev/null 2>&1; then
      log_info "  attempting nvme format with secure-erase"
      nvme format "${dev}" --ses=1 --force 2>&1 | sed 's/^/    /' || {
        log_warn "  nvme secure-erase failed; falling back to blkdiscard"
        blkdiscard "${dev}" 2>&1 | sed 's/^/    /' || log_warn "  blkdiscard also failed"
      }
    fi
  else
    # SATA/HDD: blkdiscard if SSD, dd zero if rotational (slow but reliable)
    if [ -f "/sys/block/$(basename "${dev}")/queue/rotational" ] && [ "$(cat "/sys/block/$(basename "${dev}")/queue/rotational")" = "0" ]; then
      blkdiscard "${dev}" 2>&1 | sed 's/^/    /'
    else
      log_warn "  rotational device; writing zeros (this can take hours)"
      dd if=/dev/zero of="${dev}" bs=1M status=progress 2>&1 | tail -5
    fi
  fi
done

log_info "secure-wipe complete"
