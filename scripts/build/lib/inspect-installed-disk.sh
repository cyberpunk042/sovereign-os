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
  # Locate the root FILESYSTEM. Two layouts, and they are NOT interchangeable:
  #
  #   ubuntu-autoinstall  storage: {layout: {name: direct}}  -> plain ext4 part
  #   installer-cdd       partman-auto/method = lvm          -> ext4 inside the
  #                       `root` LV of VG `sovereign`
  #
  # The old "largest partition" rule silently picked the LVM PV on a Debian
  # install. debugfs then found no superblock, ${MNT} stayed empty, and EVERY
  # assertion below would have read nothing — the same class of false PASS that
  # the rdump bug produced (2026-07-29).
  eval "$(python3 - "${RAW}" <<'PY'
import json, re, shutil, subprocess, sys

# sfdisk/debugfs/losetup live in /sbin, which is NOT on a normal user's PATH.
# This is the third time that has bitten in one session; resolve explicitly
# rather than trusting PATH (2026-07-29).
sfdisk = (shutil.which("sfdisk") or shutil.which("sfdisk", path="/sbin:/usr/sbin")
          or "/sbin/sfdisk")
img, SS = sys.argv[1], 512
out = subprocess.run([sfdisk, "-J", img], capture_output=True, text=True).stdout
parts = json.loads(out)["partitiontable"]["partitions"]
cand = max(parts, key=lambda p: p.get("size", 0))
off, ln = cand["start"] * SS, cand["size"] * SS

EXT4_MAGIC = b"\x53\xef"          # at superblock offset 0x38, i.e. part+0x438
LVM_LABEL  = b"LABELONE"          # within the first 4 sectors of a PV


def read(o, n):
    with open(img, "rb") as fh:
        fh.seek(o)
        return fh.read(n)


def is_ext4(base):
    return read(base + 0x438, 2) == EXT4_MAGIC


note = ""
if not is_ext4(off) and LVM_LABEL in read(off, 4 * SS):
    # An LVM2 PV. Its metadata area is ASCII text near the head of the PV and
    # carries everything needed to locate a linear LV without lvm2 or root:
    #
    #   extent_size = <sectors>          (VG level)
    #   pe_start    = <sectors>          (per physical_volume)
    #   segment1 { ... stripes = [ "pv0", <start_extent> ] }
    #
    #   LV byte offset in the PV = (pe_start + start_extent * extent_size) * 512
    #
    # Only the LINEAR/striped-with-one-stripe case is handled. Anything else
    # (real striping, mirrors, thin pools) is reported unsupported rather than
    # guessed at — a wrong offset reads garbage and every check fails
    # mysteriously.
    blob = read(off, 1 << 20).decode("latin-1")
    def num(pat, where=blob):
        m = re.search(pat, where)
        return int(m.group(1)) if m else None

    extent_size = num(r"extent_size\s*=\s*(\d+)")
    pe_start = num(r"pe_start\s*=\s*(\d+)")

    # Scope to the logical_volumes section. Searching the whole blob lets a
    # lazy `.*?` start at the VG's own opening brace and run forward into an
    # LV's fields, naming the LV after the volume group.
    lvsec = ""
    m = re.search(r"logical_volumes\s*\{", blob)
    if m:
        i, depth = m.end(), 1
        while i < len(blob) and depth:
            if blob[i] == "{":
                depth += 1
            elif blob[i] == "}":
                depth -= 1
            i += 1
        lvsec = blob[m.end():i - 1]

    # Prefer an LV literally named `root`; else the largest one.
    lvs = {}
    for m in re.finditer(r"([A-Za-z0-9_+.-]+)\s*\{", lvsec):
        name, i, depth = m.group(1), m.end(), 1
        while i < len(lvsec) and depth:
            if lvsec[i] == "{":
                depth += 1
            elif lvsec[i] == "}":
                depth -= 1
            i += 1
        body = lvsec[m.end():i - 1]
        segs = re.search(r"segment_count\s*=\s*(\d+)", body)
        st = re.search(r'stripes\s*=\s*\[\s*"[^"]+"\s*,\s*(\d+)', body)
        cnt = re.search(r"extent_count\s*=\s*(\d+)", body)
        stripe_cnt = re.search(r"stripe_count\s*=\s*(\d+)", body)
        if (segs and segs.group(1) == "1" and st and cnt
                and (not stripe_cnt or stripe_cnt.group(1) == "1")):
            lvs[name] = (int(st.group(1)), int(cnt.group(1)))

    pick = None
    if "root" in lvs:
        pick = ("root", *lvs["root"])
    elif lvs:
        name = max(lvs, key=lambda k: lvs[k][1])
        pick = (name, *lvs[name])

    if pick and extent_size and pe_start is not None:
        name, start_ext, ext_cnt = pick
        lv_off = off + (pe_start + start_ext * extent_size) * SS
        lv_len = ext_cnt * extent_size * SS
        if is_ext4(lv_off):
            off, ln = lv_off, lv_len
            sz = f"{ln // (1 << 30)}G" if ln >= (1 << 30) else f"{ln // (1 << 20)}M"
            note = f"LVM: LV {name} ({sz})"
        else:
            note = f"LVM-BAD: computed offset for LV {name} is not ext4"
    else:
        note = "LVM-UNSUPPORTED: no single-segment linear LV found"
elif not is_ext4(off):
    note = "NOT-EXT4: largest partition has no ext4 superblock"

print(f"ROOT_OFF={off}")
print(f"ROOT_LEN={ln}")
print(f"ROOT_NOTE={note!r}".replace("ROOT_NOTE='", "ROOT_NOTE='"))
PY
)"
  # Never let an unresolved layout masquerade as an empty-but-healthy install.
  case "${ROOT_NOTE:-}" in
    LVM-BAD*|LVM-UNSUPPORTED*|NOT-EXT4*)
      printf '  \033[31mFAIL\033[0m  cannot locate the root filesystem: %s\n' "${ROOT_NOTE}"
      printf '        Refusing to report on a disk that was never read. Re-run as\n'
      printf '        root to use the qemu-nbd + mount path instead.\n'
      exit 1 ;;
    LVM:*) printf '        %s\n' "${ROOT_NOTE}" ;;
  esac
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
             "${MNT}"/usr/lib \
             "${MNT}"/var/lib/dpkg "${MNT}"/var/lib/sovereign-os \
             "${MNT}"/var/log/sovereign-os "${MNT}"/opt
    for f in /boot/grub/grub.cfg /boot/grub/grubenv \
             /usr/lib/os-release /etc/os-release \
             /etc/sovereign-os/active-profile \
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
#
# THE ROUTE IS PER-DISTRO and the wrong one is a silent total failure in BOTH
# directions (operator decision 2026-07-29). Read the distro off the DISK — an
# inspector that assumes Debian reports "nomodeset ABSENT" on a correct Ubuntu
# install and sends the operator to the one change that guarantees a dark
# screen.
#
#   debian  Plasma ships /usr/share/xsessions/plasmax11.desktop -> X11 on the
#           EFI framebuffer. Route: nomodeset (udev 71-seat.rules 23/28).
#   ubuntu  26.04's Plasma is WAYLAND-ONLY (xsessions EMPTY) and Wayland needs
#           a DRM device, which nomodeset removes. Route: a bound KMS driver —
#           the NVIDIA driver with nvidia-drm.modeset=1 (rule 35).
GRUBCFG="${MNT}/boot/grub/grub.cfg"

# /etc/os-release is a SYMLINK to ../usr/lib/os-release on both distros, and
# debugfs `dump` does NOT follow symlinks — it wrote a 21-byte link target and
# the distro read back "unknown", silently defaulting to Debian. On an Ubuntu
# disk that means reporting the CORRECT configuration as a failure. Read the
# real file (2026-07-29, found by the first real VM install).
_osrel=""
for _c in "${MNT}/usr/lib/os-release" "${MNT}/etc/os-release"; do
  [ -s "${_c}" ] && grep -q '^ID=' "${_c}" 2>/dev/null && { _osrel="${_c}"; break; }
done
_distro=debian
if [ -n "${_osrel}" ] && grep -qE '^ID=ubuntu' "${_osrel}" 2>/dev/null; then
  _distro=ubuntu
fi
_prettyid="$(sed -n 's/^PRETTY_NAME="\(.*\)"/\1/p' "${_osrel}" 2>/dev/null)"
info "installed distro: ${_prettyid:-unknown} (route: $([ "${_distro}" = ubuntu ] && echo DRM || echo nomodeset))"

# REFUSE TO JUDGE WITHOUT EVIDENCE. On a disk with no grub.cfg at all the old
# logic fell through to "a route to a graphical seat exists" — a PASS derived
# from two absent files. That is the same false-PASS class as the rdump bug,
# and it is the one thing this script must never do (2026-07-29).
if [ ! -s "${GRUBCFG}" ]; then
  bad "no /boot/grub/grub.cfg on the installed disk — nothing will boot, and"
  info "the seat invariant cannot be judged. Not reporting a route either way."
else
# GRUB's RECOVERY entry always carries `nomodeset` (Ubuntu) or `single`
# (Debian) — that is what recovery mode IS, on every Debian-family grub.cfg
# ever generated. Grepping all `linux` lines therefore finds nomodeset on a
# PERFECTLY CORRECT Ubuntu install and reports it FATAL.
#
# Caught 2026-07-29 by the first full Ubuntu install: the normal entry read
#   ro nvidia-drm.modeset=1 quiet splash
# and the recovery entry read
#   ro recovery nomodeset dis_ucode_ldr nvidia-drm.modeset=1
# Only the entry the machine actually boots counts.
  _primary_linux() {
    grep -E '^[[:space:]]*linux[[:space:]]' "${GRUBCFG}" 2>/dev/null \
      | grep -vE '[[:space:]](recovery|single)([[:space:]]|$)'
  }
  _nomodeset=no
  _primary_linux | grep -qE '[[:space:]]nomodeset([[:space:]]|$)' && _nomodeset=yes
  _drm=no
  _primary_linux | grep -qE '[[:space:]]nvidia-drm\.modeset=1([[:space:]]|$)' && _drm=yes

  _bl=""
  for m in nouveau amdgpu i915 radeon nvidia; do
    grep -rqE "^[[:space:]]*blacklist[[:space:]]+${m}([[:space:]]|$)" "${MNT}/etc/modprobe.d/" 2>/dev/null \
      && _bl="${_bl} ${m}"
  done
  [ -n "${_bl}" ] && info "KMS drivers blacklisted:${_bl}"

  _x11=no
  if [ -n "${UNPRIV:-}" ]; then
    _dbg "ls -p /usr/share/xsessions" | awk -F/ 'NF>5 && $6!="." && $6!=".."{print $6}' \
      | grep -q . && _x11=yes
  else
    ls "${MNT}"/usr/share/xsessions/*.desktop >/dev/null 2>&1 && _x11=yes
  fi
  [ "${_x11}" = yes ] && info "X11 sessions available" \
                      || info "NO X11 sessions — this desktop is Wayland-only"

  if [ "${_distro}" = ubuntu ]; then
    # nomodeset here is FATAL, not merely suboptimal.
    if [ "${_nomodeset}" = yes ]; then
      bad "nomodeset IS SET on an Ubuntu install — this is FATAL."
      info "Plasma here is Wayland-only and Wayland needs the DRM device"
      info "nomodeset removes, so no session can start: blinking cursor."
      info "Proven by stripping it from one disk — luma 1e-05 -> 0.076."
    else
      ok "nomodeset correctly ABSENT (it is fatal on this distro)"
    fi
    case " ${_bl} " in
      *" nvidia "*) bad "the nvidia module is BLACKLISTED — it cannot bind, so"
                    info "nvidia-drm.modeset=1 is inert and there is no DRM device" ;;
    esac
    if [ "${_drm}" = yes ]; then
      ok "nvidia-drm.modeset=1 on the installed kernel command line"
    else
      bad "nvidia-drm.modeset=1 ABSENT — no DRM device, so udev rule 35 cannot"
      info "tag card0 master-of-seat and the Wayland session never starts"
    fi
    # The option is inert without the module.
    if [ -n "${UNPRIV:-}" ]; then
      _dbg "ls -p /var/lib/dpkg" >/dev/null 2>&1
    fi
    if grep -qE '^Package: nvidia-driver-[0-9]+' "${MNT}/var/lib/dpkg/status" 2>/dev/null; then
      ok "an nvidia-driver-* package is installed (provides the DRM device)"
    else
      bad "NO nvidia-driver-* installed — nvidia-drm.modeset=1 will do nothing"
    fi
  else
    if [ "${_nomodeset}" = yes ]; then
      ok "nomodeset IS on the installed kernel command line"
    else
      bad "nomodeset ABSENT from ${GRUBCFG#${MNT}}"
    fi
    if [ "${_nomodeset}" = no ] && [ -n "${_bl}" ]; then
      bad "NO ROUTE TO A GRAPHICAL SEAT — nomodeset absent AND${_bl} blacklisted."
      info "logind would report CanGraphical=no and sddm would wait forever."
    elif [ "${_nomodeset}" = yes ] && [ "${_x11}" = no ]; then
      bad "nomodeset IS SET but there is no X11 session to use it."
      info "Wayland-only desktop + nomodeset = no DRM = no session at all."
    else
      ok "a route to a graphical seat exists (udev can tag master-of-seat)"
    fi
  fi
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
  # `grep -c` EXITS 1 when the count is zero while still printing "0", so a
  # `|| echo 0` fallback appends a SECOND line and the arithmetic test below
  # dies with "[: 0\n0: integer expression expected" — reported as a FAIL on an
  # install whose self-check was clean. Same trap as 440f65b8; use `|| true` and
  # take only the first line (2026-07-29, found by the first real VM install).
  _probs=$(grep -cE 'PROBLEM|MISSING|FAILED|CONFLICT' \
             "${MNT}/var/log/sovereign-os/install-verify.log" 2>/dev/null | head -1 || true)
  _probs="${_probs:-0}"
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
