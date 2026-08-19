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

# ---- boot-mount path: zfs-mount-generator ----
# Ubuntu VENDOR-MASKS zfs-load-key.service (/usr/lib/systemd/system/zfs-load-key
# .service is a symlink to /dev/null) and relies on zfs-mount-generator instead.
# That generator reads /etc/zfs/zfs-list.cache/<pool> and emits per-dataset
# .mount units — including the load-key step for encrypted datasets.
#
# On this host that cache directory DID NOT EXIST, so the generator had nothing
# to work from and /mnt/vault mounted only because zfs-mount.service runs
# `zfs mount -a`. That is fine while everything is unencrypted and silently
# fatal the moment it is not: `zfs mount -a` does not load keys, so an encrypted
# tank/context would simply not mount after a reboot — with no error anywhere
# obvious. Set the cache up BEFORE encrypting anything.
#
# zed's history_event-zfs-list-cacher.sh maintains the file once it exists; it
# only acts on pools that already have a cache entry, which is why the empty
# file has to be created by hand first.
_zlc=/etc/zfs/zfs-list.cache
if zpool list -H -o name 2>/dev/null | grep -qx "${_pool}"; then
  ensure_dir "${_zlc}" 0755 root:root
  if [ -f "${_zlc}/${_pool}" ] && [ -s "${_zlc}/${_pool}" ]; then
    ok "zfs-list.cache/${_pool} populated ($(wc -l < "${_zlc}/${_pool}") dataset lines)"
  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "seed ${_zlc}/${_pool} for zfs-mount-generator"
  else
    : > "${_zlc}/${_pool}" 2>/dev/null || true
    # zed only writes the cache in response to a property-change event, so nudge
    # one. Setting a property to its current value still emits the history event.
    zfs set canmount=on "${_pool}" >/dev/null 2>&1 || true
    sleep 2
    if [ -s "${_zlc}/${_pool}" ]; then
      changed "seeded ${_zlc}/${_pool} ($(wc -l < "${_zlc}/${_pool}") dataset lines)"
      systemctl daemon-reload 2>/dev/null || true
    else
      fail "${_zlc}/${_pool} still empty — zed did not populate it; encrypted datasets would not mount at boot"
      iac_info "check: systemctl is-active zfs-zed  /  /etc/zfs/zed.d/history_event-zfs-list-cacher.sh"
    fi
  fi
fi

# ---- datasets, per profiles.storage.datasets ----
# tank/models  : 1M recordsize, lz4 — big sequential weight files
# tank/context : 16k, zstd-9, copies=2, sync=always — the state fabric
# tank/agents  : 128k, zstd-3 — runtime cache + sub-agent scratch
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
  _mk_ds models -o recordsize=1M -o compression=lz4 -o redundant_metadata=most

  # ---- tank/context, optionally encrypted ----
  # profiles.storage asks for encryption=aes-256-gcm. Operator decision
  # 2026-07-31: keyfile on the ROOT disk. That is a real boundary here, not the
  # usual same-disk theatre — tank lives on nvme1n1 and the key on nvme0n1, so
  # the pool disk leaving the building (RMA, resale, theft, disposal) yields
  # nothing on its own. It does NOT protect against an attacker who already has
  # root on the running machine; nothing keyed for unattended boot can.
  #
  # keylocation MUST be a file:// URI. zfs-mount-generator rejects a bare path
  # ("unknown non-URI keylocation=%s") and then emits no zfs-load-key@ unit, so
  # the dataset would silently fail to mount at boot.
  _keyfile="${IAC_TANK_KEYFILE:-/etc/zfs/keys/tank-context.key}"
  _want_enc="${IAC_TANK_ENCRYPT_CONTEXT:-0}"
  _enc_now="$(zfs get -H -o value encryption "${_pool}/context" 2>/dev/null)"

  if [ "${_want_enc}" != 1 ]; then
    _mk_ds context -o recordsize=16k -o compression=zstd-9 -o copies=2 -o sync=always
    [ "${IAC_DRY_RUN}" = 1 ] || iac_info "encryption NOT enabled on ${_pool}/context (IAC_TANK_ENCRYPT_CONTEXT=0)"

  elif [ "${_enc_now}" = "aes-256-gcm" ]; then
    ok "dataset ${_pool}/context (encrypted, aes-256-gcm)"
    _ks="$(zfs get -H -o value keystatus "${_pool}/context" 2>/dev/null)"
    [ "${_ks}" = available ] && ok "key loaded" || fail "key status: ${_ks}"

  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "recreate ${_pool}/context with aes-256-gcm (destroys it and its snapshots)"

  else
    # Encryption cannot be turned on in place — the dataset must be recreated.
    # Refuse if it holds anything meaningful rather than destroying data to
    # satisfy a config flag.
    _used_kb="$(zfs get -Hp -o value used "${_pool}/context" 2>/dev/null)"
    _used_kb=$(( ${_used_kb:-0} / 1024 ))
    _snaps="$(zfs list -H -t snapshot -o name -r "${_pool}/context" 2>/dev/null | wc -l)"
    iac_info "${_pool}/context currently: ${_used_kb}KB used, ${_snaps} snapshot(s)"
    if [ "${_used_kb}" -gt 10240 ] && [ "${IAC_TANK_ENCRYPT_CONFIRM:-}" != "destroy-context" ]; then
      fail "${_pool}/context holds ${_used_kb}KB — refusing to destroy it to enable encryption"
      iac_info "encryption cannot be enabled in place; set IAC_TANK_ENCRYPT_CONFIRM=\"destroy-context\" to accept the loss"
    else
      # Key first: 32 raw bytes, root-only, on the root disk.
      if [ ! -s "${_keyfile}" ]; then
        install -d -m 0700 "$(dirname "${_keyfile}")" 2>/dev/null || true
        if dd if=/dev/urandom of="${_keyfile}" bs=32 count=1 status=none 2>/dev/null \
           && chmod 0400 "${_keyfile}" 2>/dev/null; then
          changed "generated key ${_keyfile} (32 raw bytes, 0400 root)"
          iac_info "BACK THIS UP. Lose it and ${_pool}/context is unrecoverable."
        else
          fail "could not generate ${_keyfile}"
          return 0 2>/dev/null || exit 0
        fi
      else
        ok "key ${_keyfile} present"
      fi

      zfs destroy -r "${_pool}/context" >/dev/null 2>&1 || true
      if zfs create -o recordsize=16k -o compression=zstd-9 -o copies=2 -o sync=always \
           -o encryption=aes-256-gcm -o keyformat=raw \
           -o keylocation="file://${_keyfile}" "${_pool}/context" 2>/dev/null; then
        changed "recreated ${_pool}/context with aes-256-gcm"
        # Refresh the generator cache so a zfs-load-key@ unit is emitted for it.
        zfs set canmount=on "${_pool}" >/dev/null 2>&1 || true
        sleep 2
        systemctl daemon-reload 2>/dev/null || true
      else
        fail "could not create encrypted ${_pool}/context"
      fi
    fi
  fi

  # ---- tank/agents, optionally encrypted ----
  # profiles.storage adds tank/agents (recordsize=128k, zstd-3, purpose:
  # runtime cache + sub-agent scratch) with encryption=aes-256-gcm. It mirrors
  # tank/context's scheme exactly: a per-dataset raw keyfile on the ROOT disk,
  # same boundary and same caveats (see the context block above). Gated by
  # IAC_TANK_ENCRYPT_AGENTS so the operator opts in explicitly. agents is
  # scratch, so recreating it to enable encryption is cheap — but the >10MB
  # data-loss guard still applies, so a populated cache is never silently wiped.
  _agents_keyfile="${IAC_TANK_AGENTS_KEYFILE:-/etc/zfs/keys/tank-agents.key}"
  _want_enc_agents="${IAC_TANK_ENCRYPT_AGENTS:-0}"
  _enc_now_agents="$(zfs get -H -o value encryption "${_pool}/agents" 2>/dev/null)"

  if [ "${_want_enc_agents}" != 1 ]; then
    _mk_ds agents -o recordsize=128k -o compression=zstd-3
    [ "${IAC_DRY_RUN}" = 1 ] || iac_info "encryption NOT enabled on ${_pool}/agents (IAC_TANK_ENCRYPT_AGENTS=0)"

  elif [ "${_enc_now_agents}" = "aes-256-gcm" ]; then
    ok "dataset ${_pool}/agents (encrypted, aes-256-gcm)"
    _ks_agents="$(zfs get -H -o value keystatus "${_pool}/agents" 2>/dev/null)"
    [ "${_ks_agents}" = available ] && ok "key loaded" || fail "key status: ${_ks_agents}"

  elif [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "recreate ${_pool}/agents with aes-256-gcm (destroys it and its snapshots)"

  else
    # Encryption cannot be turned on in place — the dataset must be recreated.
    # Refuse if it holds more than scratch (>10MB) rather than destroying data
    # to satisfy a config flag.
    _used_kb_agents="$(zfs get -Hp -o value used "${_pool}/agents" 2>/dev/null)"
    _used_kb_agents=$(( ${_used_kb_agents:-0} / 1024 ))
    _snaps_agents="$(zfs list -H -t snapshot -o name -r "${_pool}/agents" 2>/dev/null | wc -l)"
    iac_info "${_pool}/agents currently: ${_used_kb_agents}KB used, ${_snaps_agents} snapshot(s)"
    if [ "${_used_kb_agents}" -gt 10240 ] && [ "${IAC_TANK_ENCRYPT_CONFIRM:-}" != "destroy-agents" ]; then
      fail "${_pool}/agents holds ${_used_kb_agents}KB — refusing to destroy it to enable encryption"
      iac_info "encryption cannot be enabled in place; set IAC_TANK_ENCRYPT_CONFIRM=\"destroy-agents\" to accept the loss"
    else
      # Key first: 32 raw bytes, root-only, on the root disk.
      if [ ! -s "${_agents_keyfile}" ]; then
        install -d -m 0700 "$(dirname "${_agents_keyfile}")" 2>/dev/null || true
        if dd if=/dev/urandom of="${_agents_keyfile}" bs=32 count=1 status=none 2>/dev/null \
           && chmod 0400 "${_agents_keyfile}" 2>/dev/null; then
          changed "generated key ${_agents_keyfile} (32 raw bytes, 0400 root)"
          iac_info "BACK THIS UP. Lose it and ${_pool}/agents is unrecoverable."
        else
          fail "could not generate ${_agents_keyfile}"
          return 0 2>/dev/null || exit 0
        fi
      else
        ok "key ${_agents_keyfile} present"
      fi

      zfs destroy -r "${_pool}/agents" >/dev/null 2>&1 || true
      if zfs create -o recordsize=128k -o compression=zstd-3 \
           -o encryption=aes-256-gcm -o keyformat=raw \
           -o keylocation="file://${_agents_keyfile}" "${_pool}/agents" 2>/dev/null; then
        changed "recreated ${_pool}/agents with aes-256-gcm"
        # Refresh the generator cache so a zfs-load-key@ unit is emitted for it.
        zfs set canmount=on "${_pool}" >/dev/null 2>&1 || true
        sleep 2
        systemctl daemon-reload 2>/dev/null || true
      else
        fail "could not create encrypted ${_pool}/agents"
      fi
    fi
  fi

  # ---- every dataset must actually be MOUNTED ----
  # (placed after the encryption branch so it covers every path through it)
  # `zfs create` leaves the dataset unmounted in some paths, and an unmounted
  # child leaves a plain directory on the PARENT dataset at the same path. That
  # is the dangerous case for tank/context specifically: the ms003 audit log and
  # the snapshot hook would happily write to /mnt/vault/context and land on the
  # UNENCRYPTED parent, with everything looking fine. Assert mounted state, do
  # not infer it from the dataset existing.
  # USE SYSTEMD, NOT `zfs mount`. With zfs-mount-generator active, systemd owns
  # these mounts: it generates mnt-vault-context.mount from the zfs-list.cache
  # and pulls it in via local-fs.target.wants. Mounting behind its back with
  # `zfs mount` makes systemd see a mount appear for a unit it believes is
  # stopped, and it promptly unmounts it again:
  #     Unmounting mnt-vault-context.mount ... Deactivated successfully.
  # which is exactly what happened here — converge reported "mounted", the
  # dataset came back unmounted seconds later, and /mnt/vault/context reverted
  # to a plain directory on the UNENCRYPTED parent.
  for _ds in models context agents; do
    [ "${IAC_DRY_RUN}" = 1 ] && continue
    zfs list -H -o name "${_pool}/${_ds}" >/dev/null 2>&1 || continue
    _mp="$(zfs get -H -o value mountpoint "${_pool}/${_ds}" 2>/dev/null)"
    _unit="$(systemd-escape -p --suffix=mount "${_mp}" 2>/dev/null)"

    if [ "$(zfs get -H -o value mounted "${_pool}/${_ds}" 2>/dev/null)" = yes ]; then
      ok "${_pool}/${_ds} mounted"
      continue
    fi

    if [ -n "${_unit}" ] && systemctl cat "${_unit}" >/dev/null 2>&1; then
      if run "mount-unit" systemctl start "${_unit}"; then
        # Confirm against ZFS, not against systemd's own report.
        if [ "$(zfs get -H -o value mounted "${_pool}/${_ds}" 2>/dev/null)" = yes ]; then
          changed "mounted ${_pool}/${_ds} via ${_unit}"
        else
          fail "${_unit} started but ${_pool}/${_ds} is still unmounted"
        fi
      else
        fail "could not start ${_unit} — see: journalctl -u ${_unit}"
      fi
    elif zfs mount "${_pool}/${_ds}" 2>/dev/null; then
      changed "mounted ${_pool}/${_ds}"
    else
      fail "${_pool}/${_ds} is NOT mounted — writes to its mountpoint would land on the parent dataset"
    fi
  done
fi
