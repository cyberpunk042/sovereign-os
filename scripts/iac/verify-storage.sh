#!/usr/bin/env bash
# scripts/iac/verify-storage.sh — prove the two things converge cannot.
#
#   1. The snapshot chain has never run against the ENCRYPTED tank/context.
#      It ran fine unencrypted, and ZFS snapshots encrypted datasets normally,
#      but "should work by analogy" has been wrong repeatedly here. Run it.
#
#   2. /etc/zfs/keys/tank-context.key has no off-machine copy. It is 32 raw
#      bytes with no passphrase fallback: lose it and tank/context and every
#      snapshot in it are unrecoverable. A second copy on / is worthless —
#      that is the same disk the original lives on. It has to leave the machine.
#
# Lives in the repo rather than /tmp because /tmp is tmpfs here and a reboot
# already ate one deliverable.
#
# Run: sudo bash scripts/iac/verify-storage.sh [/path/to/removable/media]
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "must run as root"; exit 1; }

POOL="${IAC_TANK_POOL:-tank}"
KEY="${IAC_TANK_KEYFILE:-/etc/zfs/keys/tank-context.key}"
DEST="${1:-}"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok_()  { printf '  \033[32mok\033[0m   %s\n' "$*"; }
bad_() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

say "1. snapshot chain against the encrypted dataset"
_enc="$(zfs get -H -o value encryption "${POOL}/context" 2>/dev/null)"
echo "  ${POOL}/context encryption: ${_enc}"
_before="$(zfs list -H -t snapshot -o name -r "${POOL}/context" 2>/dev/null | wc -l)"
echo "  snapshots before: ${_before}"

systemctl start sovereign-backup-snapshot.service 2>/dev/null
sleep 2
_after="$(zfs list -H -t snapshot -o name -r "${POOL}/context" 2>/dev/null | wc -l)"
if [ "${_after}" -gt "${_before}" ]; then
  ok_ "snapshot created on an encrypted dataset (${_before} → ${_after})"
  zfs list -t snapshot -o name,used,creation -r "${POOL}/context" 2>/dev/null | tail -3 | sed 's/^/       /'
else
  bad_ "no new snapshot — see: journalctl -u sovereign-backup-snapshot"
  journalctl -u sovereign-backup-snapshot -n 8 --no-pager 2>/dev/null | tail -5 | sed 's/^/       /'
fi

say "2. can a snapshot actually be read back?"
# A snapshot that exists but cannot be traversed is not a backup. Encrypted
# datasets expose snapshots under .zfs/snapshot only while the key is loaded —
# worth confirming rather than trusting the snapshot listing.
_snap="$(zfs list -H -t snapshot -o name -r "${POOL}/context" 2>/dev/null | tail -1)"
if [ -n "${_snap}" ]; then
  _name="${_snap#*@}"
  _mp="$(zfs get -H -o value mountpoint "${POOL}/context" 2>/dev/null)"
  if ls "${_mp}/.zfs/snapshot/${_name}/" >/dev/null 2>&1; then
    ok_ "snapshot is traversable at ${_mp}/.zfs/snapshot/${_name}/"
  else
    bad_ "snapshot exists but ${_mp}/.zfs/snapshot/${_name}/ is not readable"
  fi
else
  bad_ "no snapshot to read back"
fi

say "3. encryption key backup"
if [ ! -s "${KEY}" ]; then
  bad_ "key missing: ${KEY}"
  exit 1
fi
printf '  key: %s (%s bytes, mode %s)\n' "${KEY}" "$(stat -c%s "${KEY}")" "$(stat -c%a "${KEY}")"
printf '  sha256: %s\n' "$(sha256sum "${KEY}" | cut -c1-32)…"

if [ -z "${DEST}" ]; then
  cat <<EOF

  NO DESTINATION GIVEN — nothing copied.

  This key is the only thing standing between you and total loss of
  ${POOL}/context. A copy on / is pointless: that is the same disk. Put it on
  removable media or in a password manager, OFF this machine.

    # to removable media:
    sudo bash scripts/iac/verify-storage.sh /media/\$USER/<stick>

    # or as text for a password manager (WARNING: enters shell scrollback):
    sudo base64 -w0 ${KEY}; echo

  To restore onto a rebuilt machine:
    sudo install -d -m 0700 \$(dirname ${KEY})
    sudo base64 -d > ${KEY} <<< '<the base64 string>'
    sudo chmod 0400 ${KEY}
    sudo zfs load-key ${POOL}/context && sudo zfs mount ${POOL}/context
EOF
elif [ ! -d "${DEST}" ]; then
  bad_ "destination is not a directory: ${DEST}"
else
  _dm="$(findmnt -no TARGET --target "${DEST}" 2>/dev/null)"
  if [ "${_dm}" = "/" ]; then
    bad_ "${DEST} is on the ROOT filesystem — that is the same disk as the key; refusing"
    echo "       use removable media, or a password manager"
  else
    _out="${DEST}/tank-context.key.backup"
    if install -m 0400 "${KEY}" "${_out}" 2>/dev/null; then
      sync
      if cmp -s "${KEY}" "${_out}"; then
        ok_ "copied to ${_out} (verified byte-identical) on ${_dm}"
      else
        bad_ "copy at ${_out} does NOT match the source"
      fi
    else
      bad_ "could not write ${_out}"
    fi
  fi
fi
