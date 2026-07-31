#!/usr/bin/env bash
# rescued Debian archive → tank/archive, pruned
# gate: IAC_ENABLE_ARCHIVE
#
# WHAT THIS IS
#   debian-rescue.sh copied 55G off nvme1n1 before module 95 reclaimed it for
#   the pool. That disk is now wiped, so /home/jfortin/from-debian is the ONLY
#   copy of everything on it.
#
#   Inspection showed ~54G of it is disposable:
#     .sovereign-os/kernel-forge  32G  the abandoned custom 6.12.0 build tree —
#                                      this host runs the stock signed 7.0.0-28
#     sovereign-os/               22G  a checkout whose bulk is build output
#                                      (sain-01-ubuntu.raw 8.7G, installer ISOs,
#                                      a Debian DVD ISO twice). The repo itself
#                                      is cloned at IAC_SOURCE_DIR and pushed.
#
#   and ~1.7G is worth keeping: the Firefox profile, the MOK Secure Boot keys
#   (12K, only copy — useless while SecureBoot is off, but regenerating means
#   re-enrolling in firmware), the kernel/ubuntu build logs, Downloads, /root.
#
# ORDER MATTERS AND IS NOT NEGOTIABLE
#   copy → verify byte-for-byte → only then delete. This is the sole copy of the
#   data; a "move" that half-succeeds loses it. The prune step refuses to run
#   unless every keeper is present at the destination and identical.
#
# shellcheck shell=bash

_src=/home/jfortin/from-debian
_pool="${IAC_TANK_POOL:-tank}"
_ds="${_pool}/archive"
_mnt="${IAC_TANK_MOUNTPOINT:-/mnt/vault}/archive"

# Paths kept, relative to _src.
_keep="
home/jfortin/.mozilla
home/jfortin/.sovereign-os/keys
home/jfortin/.sovereign-os/log
home/jfortin/.sovereign-os/kernel-build.log
home/jfortin/.sovereign-os/ubuntu-build.log
home/jfortin/.sovereign-os/debian-build.log
home/jfortin/.sovereign-os/build-state
home/jfortin/Downloads
root
"

if [ ! -d "${_src}" ]; then
  ok "archive already handled (${_src} absent)"
  return 0 2>/dev/null || exit 0
fi
if ! zpool list -H -o name 2>/dev/null | grep -qx "${_pool}"; then
  skip "pool ${_pool} not imported — nothing to archive onto"
  return 0 2>/dev/null || exit 0
fi

# ---- dataset ----
# copies=1 deliberately: this is cold archive on a single-device pool, so a
# second copy buys protection against bit-rot only, at double the space. lz4 is
# free on incompressible data and helps on the logs.
if zfs list -H -o name "${_ds}" >/dev/null 2>&1; then
  ok "dataset ${_ds}"
elif [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "create dataset ${_ds}"
elif zfs create -o compression=lz4 -o recordsize=1M "${_ds}" 2>/dev/null; then
  changed "created dataset ${_ds}"
else
  fail "could not create ${_ds}"
  return 0 2>/dev/null || exit 0
fi

# ---- copy the keepers ----
_copied=0
_missing=""
while read -r rel; do
  [ -n "${rel}" ] || continue
  _from="${_src}/${rel}"
  _to="${_mnt}/${rel}"
  if [ ! -e "${_from}" ]; then
    # Already pruned, or never existed — not an error either way.
    [ -e "${_to}" ] || _missing="${_missing} ${rel}"
    continue
  fi
  if [ -e "${_to}" ] && diff -rq --no-dereference "${_from}" "${_to}" >/dev/null 2>&1; then
    ok "archived ${rel}"
    continue
  fi
  if [ "${IAC_DRY_RUN}" = 1 ]; then
    changed "archive ${rel}"
    continue
  fi
  install -d "$(dirname "${_to}")" 2>/dev/null || true
  if rsync -a --delete "${_from}/" "${_to}/" 2>/dev/null \
     || rsync -a "${_from}" "$(dirname "${_to}")/" 2>/dev/null; then
    changed "archived ${rel}"
    _copied=1
  else
    fail "could not archive ${rel}"
  fi
done <<< "${_keep}"

[ -n "${_missing}" ] && skip "not present to archive:${_missing}"

# ---- prune, ONLY after verifying every keeper landed ----
if [ "${IAC_ENABLE_ARCHIVE_PRUNE:-0}" != 1 ]; then
  skip "prune not enabled (IAC_ENABLE_ARCHIVE_PRUNE=0) — ${_src} left intact"
  return 0 2>/dev/null || exit 0
fi
if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "prune ${_src} (~54G) after verification"
  return 0 2>/dev/null || exit 0
fi

# --no-dereference is load-bearing, not tidiness. A Firefox profile carries a
# runtime lock symlink (.mozilla/firefox/*/lock -> 127.0.1.1:+PID) pointing at a
# process that no longer exists. Plain `diff -rq` FOLLOWS it, fails to stat the
# target, and reports a difference — so the verification would refuse to prune a
# byte-perfect copy. Compare the links themselves.
_verified=1
while read -r rel; do
  [ -n "${rel}" ] || continue
  [ -e "${_src}/${rel}" ] || continue          # nothing to lose
  if ! diff -rq --no-dereference "${_src}/${rel}" "${_mnt}/${rel}" >/dev/null 2>&1; then
    fail "VERIFY FAILED for ${rel} — refusing to prune"
    _verified=0
  fi
done <<< "${_keep}"

if [ "${_verified}" != 1 ]; then
  fail "${_src} left untouched; the archive copy is not yet trustworthy"
  return 0 2>/dev/null || exit 0
fi

_before="$(du -sh "${_src}" 2>/dev/null | cut -f1)"
if rm -rf "${_src}" 2>/dev/null; then
  changed "pruned ${_src} (${_before} freed; keepers verified on ${_ds})"
else
  fail "could not remove ${_src}"
fi
