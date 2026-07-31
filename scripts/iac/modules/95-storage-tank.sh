#!/usr/bin/env bash
# ZFS 'tank' pool — profiles.storage
# gate: IAC_ENABLE_TANK        (OFF by default — this DESTROYS a disk)
#
# WHY
#   profiles.storage declares layout "zfs-tiered" over 2x nvme-pcie-5 in raid0,
#   with datasets tank/models and tank/context. The installer instead built ext4
#   on one NVMe and left Debian 13 on the other, so there is no pool at all —
#   which blocks the model vault (/mnt/vault), ZFS snapshots, rollback, and the
#   ms003 forensic security_audit.log.
#
#   Operator decision 2026-07-31: reclaim the Debian disk as a single-device
#   tank. Not the declared raid0 (that needs a from-scratch rebuild), but a real
#   NVMe device with real ZFS integrity rather than a file-backed compromise.
#
# THIS IS THE MOST DESTRUCTIVE THING CONVERGE CAN DO.
#   Both disks are identical 2TB Samsung 990 EVO Plus whose serials differ only
#   in the tail (…16134D root vs …16121D target). Kernel names (nvme0n1/nvme1n1)
#   are NOT stable across boots. So the target is resolved BY SERIAL via
#   /dev/disk/by-id, and every gate below must pass before anything is written:
#
#     1. the resolved device must NOT be the disk carrying /
#     2. no partition of it may be mounted
#     3. it must not already belong to an imported pool
#     4. IAC_TANK_CONFIRM_WIPE must equal the target serial exactly
#
#   Gate 4 means a stray IAC_ENABLE_TANK=1 cannot wipe anything on its own.
#
# shellcheck shell=bash

_pool="${IAC_TANK_POOL:-tank}"
_serial="${IAC_TANK_DEVICE_SERIAL:-}"
_confirm="${IAC_TANK_CONFIRM_WIPE:-}"
_mnt="${IAC_TANK_MOUNTPOINT:-/mnt/vault}"

# ---- already done? (idempotent fast path) ----
if zpool list -H -o name 2>/dev/null | grep -qx "${_pool}"; then
  ok "pool ${_pool} imported"
  _have_pool=1
else
  _have_pool=0
fi

if [ "${_have_pool}" = 0 ]; then
  if [ -z "${_serial}" ]; then
    skip "IAC_TANK_DEVICE_SERIAL unset — nothing to claim"
    return 0 2>/dev/null || exit 0
  fi

  # ---- resolve target by serial, never by kernel name ----
  _dev=""
  for l in /dev/disk/by-id/nvme-*; do
    case "$(basename "${l}")" in *"${_serial}") ;; *) continue ;; esac
    case "$(basename "${l}")" in *_1|*-part*) continue ;; esac
    _dev="$(readlink -f "${l}")"; break
  done
  if [ -z "${_dev}" ] || [ ! -b "${_dev}" ]; then
    fail "no block device with serial ${_serial} under /dev/disk/by-id"
    return 0 2>/dev/null || exit 0
  fi
  iac_info "target: ${_dev} (serial ${_serial})"

  # ---- GATE 1: never the root disk ----
  _rootsrc="$(findmnt -no SOURCE / 2>/dev/null)"
  _rootdisk="/dev/$(lsblk -no PKNAME "${_rootsrc}" 2>/dev/null | head -1)"
  if [ "${_dev}" = "${_rootdisk}" ]; then
    fail "REFUSING: ${_dev} is the disk carrying / — serial lookup resolved to the root disk"
    return 0 2>/dev/null || exit 0
  fi
  ok "target is not the root disk (${_rootdisk})"

  # ---- GATE 2: nothing mounted from it ----
  _mounted="$(lsblk -no MOUNTPOINT "${_dev}" 2>/dev/null | grep -v '^$' | tr '\n' ' ')"
  if [ -n "${_mounted}" ]; then
    fail "REFUSING: ${_dev} has mounted partitions: ${_mounted}"
    return 0 2>/dev/null || exit 0
  fi
  ok "no partition of ${_dev} is mounted"

  # ---- GATE 3: not part of an existing pool ----
  if zpool status 2>/dev/null | grep -q "$(basename "${_dev}")"; then
    fail "REFUSING: ${_dev} appears in an imported pool"
    return 0 2>/dev/null || exit 0
  fi

  # ---- GATE 4: explicit typed confirmation ----
  if [ "${_confirm}" != "${_serial}" ]; then
    fail "REFUSING: IAC_TANK_CONFIRM_WIPE does not equal the target serial"
    iac_info "this wipes ${_dev} (1.8TB, currently Debian 13) — irreversible"
    iac_info "to proceed, set in converge.conf:  IAC_TANK_CONFIRM_WIPE=\"${_serial}\""
    return 0 2>/dev/null || exit 0
  fi
  ok "wipe confirmed for serial ${_serial}"

  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "create pool ${_pool} on ${_dev} (DESTROYS Debian 13)"
    return 0 2>/dev/null || exit 0
  fi

  # ---- create ----
  # -f: the disk carries an existing ext4/vfat signature we are deliberately
  # replacing. ashift=12 for 4K-native NVMe. autotrim for SSD longevity.
  iac_info "creating ${_pool} on ${_dev} — this destroys its contents"
  if zpool create -f -o ashift=12 -o autotrim=on \
        -O compression=lz4 -O atime=off -O xattr=sa -O acltype=posixacl \
        -m "${_mnt}" "${_pool}" "/dev/disk/by-id/nvme-${_serial}" 2>/dev/null \
     || zpool create -f -o ashift=12 -o autotrim=on \
        -O compression=lz4 -O atime=off -O xattr=sa -O acltype=posixacl \
        -m "${_mnt}" "${_pool}" "${_dev}"; then
    changed "created pool ${_pool} on ${_dev} → ${_mnt}"
  else
    fail "zpool create failed"
    return 0 2>/dev/null || exit 0
  fi
fi

# ---- datasets, per profiles.storage.datasets ----
# tank/models  : 1M recordsize, lz4 — big sequential weight files
# tank/context : 16k, zstd-9, copies=2, sync=always — the state fabric
#
# The profile also asks for encryption=aes-256-gcm on tank/context. NOT applied
# here: ZFS native encryption needs a key at import, so a passphrase blocks
# unattended boot and a keyfile on / offers little against the threat model that
# justifies encrypting at all. That is an operator decision with real
# operational consequences, so converge leaves it unencrypted and says so rather
# than silently picking one.
_mk_ds() {
  local name="$1"; shift
  if zfs list -H -o name "${_pool}/${name}" >/dev/null 2>&1; then
    ok "dataset ${_pool}/${name}"
  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "create dataset ${_pool}/${name}"
  elif zfs create "$@" "${_pool}/${name}" 2>/dev/null; then
    changed "created dataset ${_pool}/${name}"
  else
    fail "could not create ${_pool}/${name}"
  fi
}

if zpool list -H -o name 2>/dev/null | grep -qx "${_pool}" || [ "${IAC_DRY_RUN}" = 1 ]; then
  _mk_ds models  -o recordsize=1M  -o compression=lz4    -o redundant_metadata=most
  _mk_ds context -o recordsize=16k -o compression=zstd-9 -o copies=2 -o sync=always
  [ "${IAC_DRY_RUN}" = 1 ] || iac_info "encryption NOT enabled on ${_pool}/context — see this module's header"
fi
