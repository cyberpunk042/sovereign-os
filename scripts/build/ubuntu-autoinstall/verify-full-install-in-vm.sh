#!/usr/bin/env bash
# Run the Ubuntu autoinstall TO COMPLETION in a VM and inspect what it installed.
#
# WHY THIS EXISTS, and why it is separate from verify-installer-in-vm.sh.
#
# That harness proves the ISO BOOTS INTO the installer — the smallest useful
# check, and enough to have caught "a weird launcher rather than the standard
# installer". It deliberately stops there, because the shipped answer file
# leaves `storage` and `identity` INTERACTIVE (no unattended repartitioning, no
# baked-in password — SDD-015).
#
# But everything downstream of the disk pick was therefore never exercised:
#   * do the late-commands actually run?
#   * does the custom znver5 kernel land via dpkg -i from /cdrom/sovereign/pool?
#   * does `nomodeset` reach the INSTALLED /boot/grub/grub.cfg?
#   * is there a route to a graphical seat, or does sddm hang like 2026-07-28?
#
# Those are exactly the failures that cost the operator days. So: build a
# VM-ONLY variant of the ISO with the two interactive sections answered, install
# it to a throwaway qcow2, then MOUNT that disk and assert on what is really
# there.
#
# The VM-only answer file is generated at runtime into scratch and never written
# into the repo or the shipped ISO. The password is a throwaway hash minted per
# run — nothing is committed, and the shipped artifact is untouched.
#
# Usage:  verify-full-install-in-vm.sh [iso]
# Exit:   0 = installed system passes every assertion
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../../.." && pwd)"
ISO="${1:-${REPO}/build/sain-01/output/sain-01-ubuntu-installer.iso}"
WORK="${SOVEREIGN_OS_VMTEST_WORK:-/var/tmp/sovereign-ubuntu-vmtest}"
DISK_GB="${SOVEREIGN_OS_VMTEST_DISK_GB:-24}"
BOOT_TIMEOUT="${SOVEREIGN_OS_VMTEST_TIMEOUT:-2400}"   # 40 min: install + reboot

red() { printf '\033[31m%s\033[0m\n' "$*"; }
grn() { printf '\033[32m%s\033[0m\n' "$*"; }
log() { printf '\033[36m━━ vmtest: %s\033[0m\n' "$*" >&2; }

[ -r "${ISO}" ] || { red "no ISO at ${ISO}"; exit 1; }
for t in qemu-system-x86_64 xorriso qemu-img; do
  command -v "$t" >/dev/null || { red "missing ${t}"; exit 1; }
done
OVMF_CODE=/usr/share/OVMF/OVMF_CODE_4M.fd
OVMF_VARS=/usr/share/OVMF/OVMF_VARS_4M.fd
[ -r "${OVMF_CODE}" ] || { red "no OVMF (sudo apt install ovmf)"; exit 1; }

rm -rf "${WORK}"; mkdir -p "${WORK}/ai"
log "scratch: ${WORK}"

# ── 1. the VM-ONLY answer file ──────────────────────────────────────────────
# Start from the SHIPPED one so we test what we ship, then answer only the two
# interactive sections. Anything else that differs would make this test a lie.
xorriso -indev "${ISO}" -osirrox on -extract /autoinstall/user-data \
  "${WORK}/ai/user-data" >/dev/null 2>&1 || { red "could not read user-data from the ISO"; exit 1; }
chmod u+w "${WORK}/ai/user-data"
: > "${WORK}/ai/meta-data"

_pw="$(openssl rand -base64 18)"
_hash="$(printf '%s' "${_pw}" | openssl passwd -6 -stdin)"
# Record the throwaway credential in scratch. When a VM install boots to
# something unexpected, being unable to log in and look is a needless dead end
# (2026-07-29). Scratch only — never the repo, never the ISO.
printf 'vmtest / %s\n' "${_pw}" > "${WORK}/vm-credentials.txt"
chmod 0600 "${WORK}/vm-credentials.txt"

python3 - "${WORK}/ai/user-data" "${_hash}" <<'PY'
import sys, yaml
path, pwhash = sys.argv[1], sys.argv[2]
doc = yaml.safe_load(open(path))
ai = doc["autoinstall"]
# VM-ONLY: answer the two sections the shipped file leaves to the operator.
ai.pop("interactive-sections", None)
ai["identity"] = {"realname": "vmtest", "username": "vmtest",
                  "hostname": "sovereign-vmtest", "password": pwhash}
ai["storage"] = {"layout": {"name": "direct"}}
open(path, "w").write("#cloud-config\n" + yaml.safe_dump(doc, sort_keys=False))
print(f"user-data: {len(ai.get('packages', []))} packages, "
      f"{len(ai.get('late-commands', []))} late-commands, storage+identity answered")
PY

# ── 2. remaster the test ISO ────────────────────────────────────────────────
TEST_ISO="${WORK}/vmtest.iso"
log "remastering a VM-only ISO (interactive sections answered)"
# COPY then modify IN PLACE with `-boot_image any keep`.
#
# `-indev A -outdev B -boot_image any replay` works when A is a pristine distro
# ISO (that is what build.sh does), but this input is ALREADY a remaster, and
# replay then cannot re-derive the second El Torito image:
#   SORRY : Cannot enable EL Torito boot image #2 because it is not a data file
# `keep` on an in-place device is the pattern build.sh already uses for its own
# grub.cfg write, and it preserves both boot images (2026-07-29).
cp "${ISO}" "${TEST_ISO}"
xorriso -dev "${TEST_ISO}" -boot_image any keep \
  -rm_r /autoinstall -- \
  -map "${WORK}/ai" /autoinstall -- >/dev/null 2>&1 \
  || { red "remaster failed"; exit 1; }

# ── 3. install ──────────────────────────────────────────────────────────────
cp "${OVMF_VARS}" "${WORK}/vars.fd"; chmod u+w "${WORK}/vars.fd"
qemu-img create -f qcow2 "${WORK}/disk.qcow2" "${DISK_GB}G" >/dev/null
log "installing (up to $((BOOT_TIMEOUT/60)) min) — disk ${DISK_GB}G"
# The installer writes nothing to serial (its kernel line has no console=ttyS0,
# by design — the profile puts tty0 last so the physical display keeps
# /dev/console). Over a 40-minute run that leaves no way to tell "working" from
# "wedged" except watching the qcow2 grow. The QMP socket below makes the
# framebuffer capturable:
#     echo '{"execute":"qmp_capabilities"}{"execute":"screendump","arguments":
#            {"filename":"/tmp/s.ppm"}}' | socat - UNIX-CONNECT:<work>/qmp.sock
log "  progress: watch ${WORK}/disk.qcow2 grow, or screendump via ${WORK}/qmp.sock"
set +e
timeout "${BOOT_TIMEOUT}" qemu-system-x86_64 \
  -machine q35,accel=kvm -cpu host -m 8G -smp 6 \
  -drive if=pflash,format=raw,unit=0,readonly=on,file="${OVMF_CODE}" \
  -drive if=pflash,format=raw,unit=1,file="${WORK}/vars.fd" \
  -drive file="${WORK}/disk.qcow2",if=virtio,format=qcow2 \
  -cdrom "${TEST_ISO}" -boot d -display none -vga std \
  -serial "file:${WORK}/serial.log" -no-reboot \
  -qmp "unix:${WORK}/qmp.sock,server,nowait" \
  >"${WORK}/qemu.log" 2>&1
_rc=$?
set -e
log "qemu exited rc=${_rc} (-no-reboot: the VM stops when the install reboots)"

# ── 4. inspect the INSTALLED disk ───────────────────────────────────────────
# Everything below reads the qcow2 read-only via qemu-nbd; nothing on the host
# is touched. This is the part that could not be done before.
# No nbd gate here. The inspector reads ext4 with debugfs on an extracted
# partition — no mount, no loop device, no root. It falls back to nbd+mount only
# if debugfs is unavailable, and decides that for itself. An earlier version of
# this script refused to inspect at all unless the nbd module was loaded, which
# would have failed the run on an otherwise-complete install (2026-07-29).
log "inspecting the installed disk"
"${HERE}/inspect-installed-disk.sh" "${WORK}/disk.qcow2"
