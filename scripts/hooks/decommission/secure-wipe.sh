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
  log_error "  Example: SOVEREIGN_OS_WIPE_DEVICES='/dev/sdb'"
  log_error "  (name ONLY the disks you mean; an example listing every NVMe in a"
  log_error "   two-disk box is a copy-paste away from erasing the live system)"
  exit 1
fi

# REFUSE the disk hosting the running root. Wiping the disk you booted from is
# not a decommission, it is a crash: the dd corrupts the filesystem underneath
# the running tool, which then dies partway through. Decommissioning that disk
# is legitimate -- from a live USB, where it no longer hosts /.
#
# Resolution walks the whole device chain. PKNAME is only the IMMEDIATE parent,
# so on an LVM root a single hop yields the PV partition and never matches a
# whole-disk argument -- the same flaw found in both installers and the flash
# panel the same day (2026-07-27).
_parent_disk_of() {
  _d="$1"
  # BOUNDED. The Python twin in flash-api.py caps this at 16 hops; these shell
  # copies were `while :; do` with no counter. A device whose PKNAME resolves to
  # itself — or any cycle in the tree — spins forever, as root, mid-install.
  # Real stacks are 2-3 deep (disk → partition → LV); 16 is far past any of them
  # (2026-07-27).
  _hops=0
  while [ "${_hops}" -lt 16 ]; do
    _hops=$((_hops + 1))
    _p="$(lsblk -no PKNAME "${_d}" 2>/dev/null | head -1 | tr -d ' ')"
    [ -n "${_p}" ] || break
    _d="/dev/${_p}"
  done
  printf '%s\n' "${_d}"
}
_run_root_disk="$(_parent_disk_of "$(findmnt -no SOURCE / 2>/dev/null)" 2>/dev/null || true)"
for dev in ${SOVEREIGN_OS_WIPE_DEVICES}; do
  if [ -n "${_run_root_disk}" ] && [ "$(_parent_disk_of "${dev}")" = "${_run_root_disk}" ]; then
    log_error "REFUSING: ${dev} hosts the RUNNING root (${_run_root_disk})."
    log_error "  Boot a live medium to decommission this disk."
    exit 1
  fi
done

if ! confirm "Wipe devices: ${SOVEREIGN_OS_WIPE_DEVICES}? ALL DATA UNRECOVERABLE." default-no; then
  log_info "aborted by operator"
  exit 1
fi

# Run a wipe command and indent its output, returning the command's OWN exit
# status via PIPESTATUS[0]. (common.sh sets `pipefail`, so a bare `cmd | sed`
# already yields the command's status; this just makes the per-device success
# tracking explicit and robust regardless of shell options.)
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
