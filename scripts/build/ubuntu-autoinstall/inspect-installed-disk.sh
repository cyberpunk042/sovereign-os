#!/usr/bin/env bash
# Assert on a sovereign-os installation, from OUTSIDE it.
#
# Reads an installed disk image (qcow2 via qemu-nbd, or a block device) and
# checks the things that actually decided whether the 2026-07-28 install was
# usable. Every assertion here corresponds to a failure that shipped:
#
#   nomodeset absent + KMS blacklisted  -> no master-of-seat -> CanGraphical=no
#                                       -> sddm waits forever -> DARK SCREEN
#   custom kernel not installed         -> the whole point of the build missing
#   cockpit payload absent              -> no dashboards, silently
#   dashboards deploy failed            -> 113 units present, 0 enabled
#
# Read-only: mounts with -o ro and unmounts on every exit path.
#
# Usage: inspect-installed-disk.sh <disk.qcow2|/dev/sdX>
set -uo pipefail

IMG="${1:?usage: inspect-installed-disk.sh <disk.qcow2|blockdev>}"
NBD="${SOVEREIGN_OS_NBD:-/dev/nbd0}"
MNT="$(mktemp -d /tmp/sovereign-inspect-XXXXXX)"
PASS=0; FAIL=0
_connected=""

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAIL=$((FAIL+1)); }
info() { printf '        %s\n' "$*"; }

cleanup() {
  mountpoint -q "${MNT}/boot/efi" 2>/dev/null && umount "${MNT}/boot/efi" 2>/dev/null
  mountpoint -q "${MNT}" 2>/dev/null && umount "${MNT}" 2>/dev/null
  [ -n "${_connected}" ] && qemu-nbd --disconnect "${NBD}" >/dev/null 2>&1
  rmdir "${MNT}" 2>/dev/null || true
}
trap cleanup EXIT

DEBUGFS="$(command -v debugfs || echo /sbin/debugfs)"

# ── UNPRIVILEGED PATH ───────────────────────────────────────────────────────
# Mounting anything needs root, and so does `modprobe nbd`. But the only thing
# actually required here is READING an ext4 filesystem, and debugfs does that
# from a plain file with `-o <offset>` — no mount, no loop device, no root.
# Prefer it, and fall back to nbd+mount only when it is unavailable.
if [ -x "${DEBUGFS}" ] && [ "${IMG#/dev/}" = "${IMG}" ] && command -v qemu-img >/dev/null; then
  RAW="${IMG%.qcow2}.raw"
  if [ ! -f "${RAW}" ] || [ "${IMG}" -nt "${RAW}" ]; then
    # -U: this is a strictly READ-ONLY inspection, so do not take the image
    # lock. Without it, inspecting a disk while a VM still has it open fails
    # with 'Failed to get shared "write" lock' — which is exactly when you most
    # want to look at it (2026-07-29).
    qemu-img convert -U -O raw "${IMG}" "${RAW}" || { echo "qemu-img convert failed"; exit 1; }
  fi
  # Largest ext4 partition = root (the installer's `direct` layout).
  eval "$(python3 - "${RAW}" <<'PY'
import json, shutil, subprocess, sys
# sfdisk/debugfs/losetup live in /sbin, which is NOT on a normal user's PATH.
# This is the third time that has bitten in one session; resolve explicitly
# rather than trusting PATH (2026-07-29).
sfdisk = (shutil.which("sfdisk") or shutil.which("sfdisk", path="/sbin:/usr/sbin")
          or "/sbin/sfdisk")
out = subprocess.run([sfdisk, "-J", sys.argv[1]], capture_output=True, text=True).stdout
parts = json.loads(out)["partitiontable"]["partitions"]
ss = 512
best = max(parts, key=lambda p: p.get("size", 0))
print(f'ROOT_OFF={best["start"]*ss}')
print(f'ROOT_LEN={best["size"]*ss}')
PY
)"
  # debugfs takes a FILESYSTEM, not a disk image plus an offset — it has NO -o
  # flag (usage: -b -s -f -R -d -i -n -D -V -w -z -c). An earlier version of
  # this script passed `-o ${ROOT_OFF}` and every call failed with
  #     debugfs: invalid option -- 'o'
  # which would have made every assertion below silently read nothing. Caught by
  # smoke-testing the inspector against a synthetic ext4 image BEFORE trusting it
  # on a real install (2026-07-29). So carve the partition out to its own file.
  ROOTIMG="${RAW%.raw}.root.img"
  if [ ! -f "${ROOTIMG}" ] || [ "${RAW}" -nt "${ROOTIMG}" ]; then
    dd if="${RAW}" of="${ROOTIMG}" bs=1M skip=$((ROOT_OFF/1048576)) \
       count=$((ROOT_LEN/1048576)) status=none 2>/dev/null || true
  fi
  _dbg() { "${DEBUGFS}" -R "$1" "${ROOTIMG}" 2>/dev/null; }
  if _dbg "stat <2>" | grep -q Inode; then
    echo "── inspecting ${ROOTIMG} (debugfs, unprivileged) ──"
    UNPRIV=1
    # Stage exactly the paths the assertions read into ${MNT}, so every check
    # below is byte-identical between the two modes — no second code path to
    # drift.
    mkdir -p "${MNT}"/boot/grub "${MNT}"/etc/modprobe.d "${MNT}"/etc/sovereign-os \
             "${MNT}"/var/lib/dpkg "${MNT}"/var/lib/sovereign-os \
             "${MNT}"/var/log/sovereign-os "${MNT}"/opt
    for f in /boot/grub/grub.cfg /boot/grub/grubenv /etc/sovereign-os/active-profile \
             /var/lib/dpkg/status /var/lib/sovereign-os/dashboards-install.status \
             /var/log/sovereign-os/install-verify.log \
             /var/log/sovereign-os/dashboards-install.log; do
      _dbg "dump ${f} ${MNT}${f}" >/dev/null 2>&1 || true
    done
    # Per-file `dump`, NOT `rdump`. rdump into a directory that ALREADY EXISTS
    # extracts nothing at all — silently. Because the mkdir above pre-created
    # ${MNT}/etc/modprobe.d, the blacklist files were never staged, `_bl` came
    # back empty, and the master-of-seat invariant — the single check this whole
    # script exists for — reported PASS on a disk reproducing the 2026-07-28
    # dark screen. Caught by a NEGATIVE test (2026-07-29); a checker that only
    # ever passes is worse than no checker.
    _dbg "ls -p /etc/modprobe.d" | awk -F/ 'NF>5 && $6!="." && $6!=".."{print $6}' \
    | while IFS= read -r _f; do
        [ -n "${_f}" ] || continue
        _dbg "dump /etc/modprobe.d/${_f} ${MNT}/etc/modprobe.d/${_f}" >/dev/null 2>&1 || true
      done
    # Existence-only checks: materialise a marker so `ls`/`-d` behave the same.
    for f in /boot/vmlinuz-6.12.0 /boot/initrd.img-6.12.0; do
      _dbg "stat ${f}" | grep -q 'Inode:' && : > "${MNT}${f}"
    done
    _dbg "stat /opt/sovereign-os/scripts" | grep -q 'Inode:' \
      && mkdir -p "${MNT}/opt/sovereign-os/scripts"
  fi
fi

if [ -z "${UNPRIV:-}" ]; then
  case "${IMG}" in
    /dev/*) DEV="${IMG}" ;;
    *)      qemu-nbd --read-only --connect="${NBD}" "${IMG}" || {
              echo "could not attach ${IMG} to ${NBD}"; exit 1; }
            _connected=1; sleep 2; DEV="${NBD}" ;;
  esac
fi

# Mount path (root required). The unprivileged debugfs branch above has already
# staged ${MNT}; skip everything here in that case.
if [ -z "${UNPRIV:-}" ]; then
  # The root is the largest ext4 partition — the installer's `direct` layout puts
  # root on the big one and the ESP on a small vfat.
  ROOT=""
  for p in $(lsblk -lnpo NAME,FSTYPE "${DEV}" 2>/dev/null | awk '$2=="ext4"{print $1}'); do
    [ -z "${ROOT}" ] && ROOT="$p"
    [ "$(blockdev --getsize64 "$p" 2>/dev/null || echo 0)" -gt \
      "$(blockdev --getsize64 "${ROOT}" 2>/dev/null || echo 0)" ] && ROOT="$p"
  done
  [ -n "${ROOT}" ] || { echo "no ext4 root found on ${DEV} — did the install run?"; exit 1; }
  mount -o ro "${ROOT}" "${MNT}" || { echo "cannot mount ${ROOT}"; exit 1; }
  echo "── inspecting ${ROOT} ──"
fi

# ── the seat invariant: the 2026-07-28 dark screen ──────────────────────────
GRUBCFG="${MNT}/boot/grub/grub.cfg"
_nomodeset=no
if grep -qE '^[[:space:]]*linux.*[[:space:]]nomodeset([[:space:]]|$)' "${GRUBCFG}" 2>/dev/null; then
  _nomodeset=yes; ok "nomodeset IS on the installed kernel command line"
else
  bad "nomodeset ABSENT from ${GRUBCFG#${MNT}}"
fi
_bl=""
for m in nouveau amdgpu i915 radeon; do
  grep -rqE "^[[:space:]]*blacklist[[:space:]]+${m}([[:space:]]|$)" "${MNT}/etc/modprobe.d/" 2>/dev/null \
    && _bl="${_bl} ${m}"
done
[ -n "${_bl}" ] && info "KMS drivers blacklisted:${_bl}"
if [ "${_nomodeset}" = no ] && [ -n "${_bl}" ]; then
  bad "NO ROUTE TO A GRAPHICAL SEAT — nomodeset absent AND${_bl} blacklisted."
  info "logind would report CanGraphical=no and sddm would wait forever."
else
  ok "a route to a graphical seat exists (udev can tag master-of-seat)"
fi

# ── the custom kernel ───────────────────────────────────────────────────────
if ls "${MNT}"/boot/vmlinuz-6.12.0 >/dev/null 2>&1; then
  ok "custom znver5 kernel installed (vmlinuz-6.12.0)"
else
  bad "vmlinuz-6.12.0 NOT installed — the late-command dpkg -i did not run"
fi
ls "${MNT}"/boot/initrd.img-6.12.0 >/dev/null 2>&1 \
  && ok "initramfs for 6.12.0 generated" \
  || bad "no initrd.img-6.12.0 — update-initramfs did not run"
if grep -q 'saved_entry=.*6\.12\.0' "${MNT}/boot/grub/grubenv" 2>/dev/null; then
  ok "GRUB default pinned to the custom kernel"
else
  info "GRUB default not pinned to 6.12.0 (stock kernel would boot)"
fi

# ── WHICH display manager actually owns the seat ───────────────────────────
# The inspector passed 12/14 on a system that booted to a blinking cursor,
# because it never asked THIS question. display-manager.service pointed at gdm3
# (the desktop ISO's GNOME base); gdm3 needs a DRM device that nomodeset removes.
# sddm-on-X11 is the configuration proven on this hardware (2026-07-29).
_dm=""
if [ -n "${UNPRIV:-}" ]; then
  _dm="$(_dbg "stat /etc/systemd/system/display-manager.service" \
         | sed -n 's/.*Fast link dest: "\(.*\)".*/\1/p')"
else
  _dm="$(readlink "${MNT}/etc/systemd/system/display-manager.service" 2>/dev/null)"
fi
case "${_dm}" in
  *sddm*)  ok "display manager: sddm (proven config on this hardware)" ;;
  "")      bad "NO display-manager.service — nothing will start a session" ;;
  *gdm*)   bad "display manager is gdm3 (${_dm})."
           info "gdm3 wants a DRM device for its Wayland greeter, and nomodeset"
           info "removes one -> blinking cursor on black. Select sddm:"
           info "  sh /opt/sovereign-os/scripts/install/select-display-manager.sh sddm" ;;
  *)       bad "unexpected display manager: ${_dm}" ;;
esac

# ── the sovereign payload ───────────────────────────────────────────────────
[ -d "${MNT}/opt/sovereign-os/scripts" ] \
  && ok "cockpit payload present at /opt/sovereign-os" \
  || bad "/opt/sovereign-os missing — the cockpit .deb did not install"
[ -f "${MNT}/etc/sovereign-os/active-profile" ] \
  && ok "active-profile written ($(cat "${MNT}/etc/sovereign-os/active-profile" 2>/dev/null))" \
  || bad "/etc/sovereign-os/active-profile missing — late-commands did not run"

# ── standard system utilities + the AI tier ────────────────────────────────
_have() { grep -q "^Package: $1\$" "${MNT}/var/lib/dpkg/status" 2>/dev/null; }
for p in dkms build-essential xdg-utils sddm; do
  _have "$p" && ok "installed: $p" || bad "NOT installed: $p"
done

# ── what the install said about itself ─────────────────────────────────────
if [ -f "${MNT}/var/log/sovereign-os/install-verify.log" ]; then
  ok "install self-check ran (report on disk)"
  _probs=$(grep -cE 'PROBLEM|MISSING|FAILED|CONFLICT' \
             "${MNT}/var/log/sovereign-os/install-verify.log" 2>/dev/null || echo 0)
  [ "${_probs}" -eq 0 ] && ok "self-check found no problems" \
                        || { bad "self-check reported ${_probs} problem(s):"
                             grep -E 'PROBLEM|MISSING|FAILED|CONFLICT' \
                               "${MNT}/var/log/sovereign-os/install-verify.log" | sed 's/^/          /' | head -8; }
else
  info "no install-verify.log (the self-check is Debian-path only today)"
fi
if [ -f "${MNT}/var/lib/sovereign-os/dashboards-install.status" ]; then
  _st="$(cat "${MNT}/var/lib/sovereign-os/dashboards-install.status")"
  [ "${_st}" = ok ] && ok "dashboards deploy: ok" || bad "dashboards deploy: ${_st}"
  [ "${_st}" != ok ] && sed 's/^/          /' "${MNT}/var/log/sovereign-os/dashboards-install.log" 2>/dev/null | tail -6
else
  info "no dashboards-install.status"
fi

echo
printf '  %d passed, %d failed\n' "${PASS}" "${FAIL}"
[ "${FAIL}" -eq 0 ]
