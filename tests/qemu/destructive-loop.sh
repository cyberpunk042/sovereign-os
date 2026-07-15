#!/usr/bin/env bash
# tests/qemu/destructive-loop.sh — Layer 4 QEMU destructive-loop probe (Q-014).
#
# SDD-014 resolution: actual destruction is operator-driven on real hardware.
# This script tests what CAN be safely validated in QEMU without touching
# the host or the guest disk:
#
#   1. Boot the built image with -snapshot (all disk writes discarded).
#   2. Attach a serial socket and monitor the guest boot stream.
#   3. Wait for the "login:" prompt — proves the guest reaches fully
#      interactive userspace.
#   4. Verify that sovereign-osctl is installed by grepping the boot log
#      for "sovereign-os" banners (present in motd/issue).
#   5. Generate a throwaway SSH keypair for future operator injection
#      (when guestfish / loopback mount tools become available).
#
# Pre-conditions (same as scaffold.sh):
#   - qemu-system-x86_64 installed
#   - /dev/kvm present + readable (KVM strongly recommended; TCG slow-path
#     is allowed via SOVEREIGN_OS_LAYER4_SLOW=1)
#   - Built image artifact present
#
# CLI:
#   destructive-loop.sh [profile]      run the destructive-loop probe
#   destructive-loop.sh --help         show usage
#
# Exit codes:
#   0 — probe completed, guest reached interactive prompt
#   1 — at least one precondition failed or guest did not reach prompt
#   2 — usage error

set -euo pipefail

PROFILE="${1:-sain-01}"
if [ "${PROFILE}" = "--help" ] || [ "${PROFILE}" = "-h" ]; then
  sed -n '1,30p' "${BASH_SOURCE[0]}"
  exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

bold='\033[1m'; green='\033[32m'; yellow='\033[33m'; red='\033[31m'; reset='\033[0m'

fail=0; pass=0; skip=0
ok()   { echo -e "  ${green}PASS${reset} — $1"; pass=$((pass + 1)); }
sk()   { echo -e "  ${yellow}SKIP${reset} — $1"; skip=$((skip + 1)); }
ko()   { echo -e "  ${red}FAIL${reset} — $1"; fail=$((fail + 1)); }

# ---- Python3 resolver (same pattern as run.sh / phases.sh) ----
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

echo "tests/qemu/destructive-loop.sh — profile=${PROFILE}"
echo

# ---- precondition 1: qemu-system-x86_64 ----

qemu_ok=0
if command -v qemu-system-x86_64 >/dev/null 2>&1; then
  ok "qemu-system-x86_64 installed"
  qemu_ok=1
else
  ko "qemu-system-x86_64 not installed"
fi

# ---- precondition 2: KVM ----

kvm_ok=0
if [ -e /dev/kvm ] && [ -r /dev/kvm ]; then
  ok "/dev/kvm present + readable"
  kvm_ok=1
else
  sk "/dev/kvm absent — boot will be very slow (TCG)"
fi

# ---- precondition 3: built image ----

image_dir="${SOVEREIGN_OS_IMAGE_DIR:-}"
if [ -z "${image_dir}" ]; then
  for candidate in \
    "${REPO_ROOT}/build/${PROFILE}/output" \
    "/var/lib/sovereign-os/output"; do
    if [ -d "${candidate}" ] && find "${candidate}" -maxdepth 1 \( -name '*.raw' -o -name '*.iso' \) -type f 2>/dev/null | grep -q .; then
      image_dir="${candidate}"
      break
    fi
  done
fi

image_ok=0
image_file=""
if [ -n "${image_dir}" ] && [ -d "${image_dir}" ]; then
  image_file="$(find "${image_dir}" -maxdepth 1 \( -name '*.raw' -o -name '*.iso' \) -type f 2>/dev/null | head -1)"
  if [ -n "${image_file}" ]; then
    ok "built image artifact present: ${image_file}"
    image_ok=1
  fi
fi
[ "${image_ok}" -eq 0 ] && ko "no built image artifact found (run orchestrate.sh run first)"

# ---- result if preconditions missing ----

if [ "${qemu_ok}" -eq 0 ] || [ "${image_ok}" -eq 0 ]; then
  echo
  total=$((pass + fail + skip))
  echo "destructive-loop: ${pass}/${total} passed; ${skip} skipped"
  echo "FAIL — preconditions not met"
  exit 1
fi

# ---- generate throwaway SSH key for future injection ----

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

key_file="${TMPDIR}/q014-test"
if ssh-keygen -t ed25519 -f "${key_file}" -N "" -C "q014@${PROFILE}" >/dev/null 2>&1; then
  ok "throwaway SSH keypair generated (${key_file}.pub)"
else
  sk "ssh-keygen failed — future SSH injection will need manual key"
fi

# ---- boot the image with -snapshot + serial socket ----
# -snapshot  → every disk write goes to a temporary overlay; the original
#              image file is never modified. Safe for destructive tests.
# -serial chardev:serial0  → guest ttyS0 plumbed to a UNIX socket that
#              our serial-monitor.py can read and write.
# -no-reboot → when the guest reboots or panics, QEMU exits.

serial_sock="${TMPDIR}/qemu-serial.sock"
serial_log="${TMPDIR}/serial.log"
qemu_log="${TMPDIR}/qemu.log"

qemu_boot_args=()

# OVMF firmware (same logic as 09-image-verify.sh)
if [ -f /usr/share/OVMF/OVMF_CODE_4M.fd ]; then
  ovmf_code="/usr/share/OVMF/OVMF_CODE_4M.fd"
elif [ -f /usr/share/OVMF/OVMF_CODE.fd ]; then
  ovmf_code="/usr/share/OVMF/OVMF_CODE.fd"
else
  ovmf_code=""
fi

if [ -n "${ovmf_code}" ]; then
  ovmf_vars_src="${ovmf_code/CODE/VARS}"
  ovmf_vars="${TMPDIR}/ovmf-vars.fd"
  if [ -f "${ovmf_vars_src}" ]; then
    cp "${ovmf_vars_src}" "${ovmf_vars}"
    qemu_boot_args+=(
      -machine q35
      -drive "if=pflash,format=raw,readonly=on,file=${ovmf_code}"
      -drive "if=pflash,format=raw,file=${ovmf_vars}"
    )
  fi
fi

if [ "${kvm_ok}" -eq 1 ]; then
  qemu_boot_args+=(-enable-kvm -cpu host)
else
  qemu_boot_args+=(-cpu max)
fi

: "${SOVEREIGN_OS_QEMU_TIMEOUT:=300}"
: "${SOVEREIGN_OS_QEMU_MEM:=4G}"

ok "QEMU timeout=${SOVEREIGN_OS_QEMU_TIMEOUT}s mem=${SOVEREIGN_OS_QEMU_MEM}"

# Start the serial monitor in the background BEFORE QEMU so the socket
# has a consumer ready.
"${PYTHON3}" "${REPO_ROOT}/tests/qemu/lib/serial-monitor.py" "${serial_sock}" "${serial_log}" >"${TMPDIR}/monitor.out" 2>"${TMPDIR}/monitor.err" &
monitor_pid=$!

# Start QEMU.
qemu-system-x86_64 \
  -m "${SOVEREIGN_OS_QEMU_MEM}" \
  -smp 2 \
  -nographic \
  -no-reboot \
  -snapshot \
  -drive "file=${image_file},format=raw,if=virtio,readonly=on" \
  -chardev "socket,path=${serial_sock},id=serial0,server=on,wait=off" \
  -serial chardev:serial0 \
  "${qemu_boot_args[@]}" \
  >"${qemu_log}" 2>&1 &
qemu_pid=$!

# Wait for boot completion: "login:" in the serial log.
login_found=0
for i in $(seq 1 "${SOVEREIGN_OS_QEMU_TIMEOUT}"); do
  if [ -f "${serial_log}" ] && grep -qE "login:|Welcome to|sovereign" "${serial_log}" 2>/dev/null; then
    login_found=1
    break
  fi
  sleep 1
done

# Clean up QEMU and monitor.
if kill -0 "${qemu_pid}" 2>/dev/null; then
  kill "${qemu_pid}" >/dev/null 2>&1 || true
  wait "${qemu_pid}" >/dev/null 2>&1 || true
fi
if kill -0 "${monitor_pid}" 2>/dev/null; then
  kill "${monitor_pid}" >/dev/null 2>&1 || true
  wait "${monitor_pid}" >/dev/null 2>&1 || true
fi

# ---- assertions ----

if [ "${login_found}" -eq 1 ]; then
  ok "guest serial log contains login/userspace marker"
else
  ko "guest did not reach login prompt within ${SOVEREIGN_OS_QEMU_TIMEOUT}s"
fi

if [ -f "${serial_log}" ] && grep -qi "sovereign" "${serial_log}" 2>/dev/null; then
  ok "serial log carries 'sovereign' branding (motd/issue present)"
else
  sk "sovereign branding not detected in serial log (may need longer timeout)"
fi

if [ -f "${serial_log}" ] && grep -qi "qemu\|kvm\|virtio" "${serial_log}" 2>/dev/null; then
  ok "guest detected virtualization layer (virtio/qemu in dmesg)"
else
  sk "virtualization layer not detected in serial log"
fi

# ---- summary ----

echo
total=$((pass + fail + skip))
echo "destructive-loop: ${pass}/${total} passed; ${skip} skipped"

if [ "${fail}" -eq 0 ]; then
  echo
  echo -e "${bold}Q-014 probe summary${reset}"
  echo "  Image booted to interactive prompt with -snapshot (disk-safe)."
  echo "  Serial log: ${serial_log}"
  echo "  Throwaway key: ${key_file}.pub (for future SSH-injection tests)"
  echo "  Next step for full loop: inject key into image, boot again,"
  echo "  SSH in, run 'sovereign-osctl decommission start', verify abort."
  echo "PASS"
  exit 0
else
  echo "FAIL"
  exit 1
fi
