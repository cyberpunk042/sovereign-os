#!/usr/bin/env bash
# Boot the installer ISO in a VM and prove it reaches debian-installer.
#
# WHY. Every failure this project has hit was discovered by the operator, on
# real hardware, an hour into a cycle: a live-build TUI where a Debian installer
# was expected; an ISO that booted to a dark screen; an install that finished
# and produced no desktop. Nothing ever booted the artifact before they did.
#
# qemu + OVMF + KVM are present on the build host, so the ISO can be booted here
# in seconds. This is deliberately the SMALLEST useful check — does it boot, and
# is what comes up debian-installer — because that alone would have caught the
# "weird launcher rather than the standard installer" failure immediately.
#
# It does NOT run a full install (that needs preseed answers this profile
# deliberately leaves interactive). Exit 0 = the ISO boots into d-i.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
# Default to the distro-qualified name (2026-07-29), falling back to the
# legacy one so a pre-rename ISO still works. Hardcoding either alone means
# the harness silently verifies the wrong vintage — or nothing at all.
_prof="${SOVEREIGN_OS_PROFILE:-sain-01}"
_outdir="${REPO}/build/${_prof}/output"
ISO="${1:-}"
if [ -z "${ISO}" ]; then
  for _c in "${_outdir}/${_prof}-debian-installer.iso" \
            "${_outdir}/${_prof}-installer.iso"; do
    [ -r "${_c}" ] && { ISO="${_c}"; break; }
  done
  ISO="${ISO:-${_outdir}/${_prof}-debian-installer.iso}"
fi
TIMEOUT="${SOVEREIGN_OS_VM_TIMEOUT:-120}"
LOG="$(mktemp /tmp/sovereign-vm-XXXXXX.log)"

red() { printf '\033[31m%s\033[0m\n' "$*"; }
grn() { printf '\033[32m%s\033[0m\n' "$*"; }
inf() { printf '  %s\n' "$*"; }

[ -r "${ISO}" ] || { red "no ISO at ${ISO}"; exit 1; }
command -v qemu-system-x86_64 >/dev/null || { red "qemu-system-x86_64 not installed"; exit 1; }

OVMF=""
for c in /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/ovmf/OVMF.fd; do
  [ -r "$c" ] && { OVMF="$c"; break; }
done
[ -n "${OVMF}" ] || { red "no OVMF firmware — cannot test the UEFI path"; exit 1; }

VARS="$(mktemp /tmp/sovereign-vmvars-XXXXXX.fd)"
for c in /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd; do
  [ -r "$c" ] && { cp "$c" "${VARS}"; break; }
done
[ -s "${VARS}" ] || { red "no OVMF_VARS template"; exit 1; }

ACCEL=(); [ -w /dev/kvm ] && ACCEL=(-enable-kvm -cpu host)

inf "ISO      : ${ISO}"
inf "firmware : ${OVMF}"
inf "timeout  : ${TIMEOUT}s"
inf "booting…"

# BOOT THE ISO'S OWN KERNEL DIRECTLY.
#
# Booting the ISO normally gets as far as "Loading bootloader..." and then goes
# silent: GRUB hands off to d-i, which writes to the VIDEO console. The serial
# log stays empty and the test can conclude nothing — the same blindness that
# made three earlier QEMU checks useless.
#
# Extracting /install.amd/{vmlinuz,initrd.gz} and booting them with -kernel
# lets us set console=ttyS0 for THIS RUN ONLY. The ISO is untouched: its own
# kernel line keeps the video console, which is what real hardware needs (an
# earlier build baked console=ttyS0 into the ISO and sent the whole installer
# UI to a serial port nobody was watching).
KDIR="$(mktemp -d /tmp/sovereign-vmk-XXXXXX)"
if ! xorriso -osirrox on -indev "${ISO}" \
      -cpx /install.amd/vmlinuz /install.amd/initrd.gz "${KDIR}/" >/dev/null 2>&1; then
  red "could not extract the installer kernel from ${ISO}"
  rm -rf "${KDIR}" "${VARS}"; exit 1
fi

set +e
timeout "${TIMEOUT}" qemu-system-x86_64 \
  "${ACCEL[@]}" -m 2048 -smp 2 -nographic \
  -drive "if=pflash,format=raw,readonly=on,file=${OVMF}" \
  -drive "if=pflash,format=raw,file=${VARS}" \
  -cdrom "${ISO}" \
  -kernel "${KDIR}/vmlinuz" -initrd "${KDIR}/initrd.gz" \
  -append "console=ttyS0,115200n8 DEBIAN_FRONTEND=text --- quiet" \
  -serial "file:${LOG}" >/dev/null 2>&1
set -e
rm -rf "${KDIR}" "${VARS}"

# What did it become? Any of these means d-i itself started.
# What d-i actually puts on the console. The first version looked for
# "debian-installer"/"anna-install" and found neither: the real markers are the
# installer's own tmux-style status bar ("1*installer") and its first question.
# The run DID reach d-i and the harness reported failure (2026-07-27).
if grep -qaE "1\*installer|Select a language|Choose the language|main-menu|anna-install|Detecting hardware" "${LOG}" 2>/dev/null; then
  grn "✓ the ISO boots into debian-installer"
  inf "evidence: $(grep -aoE '1\*installer|Select a language|main-menu|anna-install' "${LOG}" | head -1)"
  inf "serial log: ${LOG}"
  exit 0
fi

if [ ! -s "${LOG}" ]; then
  red "✗ nothing reached the serial console in ${TIMEOUT}s"
  red "  The ISO may not boot under UEFI, or it writes only to the video console."
  inf "serial log (empty): ${LOG}"
  exit 1
fi

red "✗ the ISO booted but did NOT reach debian-installer"
inf "last serial output:"
tail -20 "${LOG}" | sed 's/^/    /'
inf "full log: ${LOG}"
exit 1
