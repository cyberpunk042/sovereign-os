#!/usr/bin/env bash
# tests/qemu/scaffold.sh — Layer 4 QEMU integration scaffold.
#
# Layer 4 = "full image boots in QEMU and reaches userspace". The
# real test depends on:
#   1. A built sovereign-os image (orchestrate.sh run end-to-end)
#   2. KVM acceleration in the runner (CI may or may not have it)
#   3. >2GB free disk for the image artifact
#
# CI runners typically don't have all three. This scaffold:
#   - probes the environment for the three preconditions
#   - if all three present: bridges to scripts/build/09-image-verify.sh
#     which IS the substantive QEMU boot
#   - otherwise: graceful SKIP with operator-actionable reason

set -euo pipefail

PROFILE="${1:-sain-01}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

bold='\033[1m'; green='\033[32m'; yellow='\033[33m'; reset='\033[0m'

fail=0; pass=0; skip=0
ok()   { echo -e "  ${green}PASS${reset} — $1"; pass=$((pass + 1)); }
sk()   { echo -e "  ${yellow}SKIP${reset} — $1"; skip=$((skip + 1)); }
ko()   { echo -e "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/qemu/scaffold.sh — profile=${PROFILE}"
echo

# ----------- precondition 1: 09-image-verify.sh present ---------------

if [ -x "${REPO_ROOT}/scripts/build/09-image-verify.sh" ]; then
  ok "09-image-verify.sh present (Layer 4 driver)"
else
  ko "09-image-verify.sh missing"
fi

# ----------- precondition 2: KVM available ---------------

kvm_ok=0
if [ -e /dev/kvm ] && [ -r /dev/kvm ]; then
  ok "/dev/kvm present + readable (KVM acceleration available)"
  kvm_ok=1
else
  sk "/dev/kvm absent — boot test would be too slow without acceleration"
fi

# ----------- precondition 3: qemu-system-x86_64 available ---------------

qemu_ok=0
if command -v qemu-system-x86_64 >/dev/null 2>&1; then
  ok "qemu-system-x86_64 installed"
  qemu_ok=1
else
  sk "qemu-system-x86_64 not installed"
fi

# ----------- precondition 4: built image present ---------------

image_dir="${SOVEREIGN_OS_IMAGE_DIR:-}"
if [ -z "${image_dir}" ]; then
  # Auto-discover from common paths
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
if [ -n "${image_dir}" ] && [ -d "${image_dir}" ]; then
  if find "${image_dir}" -maxdepth 1 \( -name '*.raw' -o -name '*.iso' \) -type f 2>/dev/null | grep -q .; then
    ok "built image artifact present at ${image_dir}"
    image_ok=1
  fi
fi
[ "${image_ok}" -eq 0 ] && sk "no built image artifact found (run orchestrate.sh run first)"

# ----------- destructive-loop scaffold (Q-014 partial closure) ---------------

# The plan called for a "Layer 4 QEMU destructive-loop test" — boot
# the image, perform a destructive operation inside the guest (e.g.,
# `sovereign-osctl decommission start`), verify the guest is in the
# expected post-destruction state, all without touching the host.
# Scaffold lives here; full implementation lands when KVM-equipped
# self-hosted runner is provisioned (Q10-B per SDD-020).

cat <<EOF

Layer 4 readiness:
  KVM:    $([ "${kvm_ok}" -eq 1 ] && echo "yes" || echo "no — gating SKIP")
  qemu:   $([ "${qemu_ok}" -eq 1 ] && echo "yes" || echo "no — gating SKIP")
  image:  $([ "${image_ok}" -eq 1 ] && echo "yes — ${image_dir}" || echo "no — run orchestrate.sh run first")

Q-014 destructive-loop status:
  scaffold ready; substantive run gated on KVM + built image.
  When all three preconditions clear:
    bridge to scripts/build/09-image-verify.sh — that script is the
    Layer 4 driver (QEMU boot smoke; the destructive-loop verb extends
    that path).
EOF

# ----------- substantive run (only when all preconditions clear) ---------------

if [ "${kvm_ok}" -eq 1 ] && [ "${qemu_ok}" -eq 1 ] && [ "${image_ok}" -eq 1 ]; then
  echo
  echo -e "${bold}all preconditions met — running 09-image-verify.sh${reset}"
  SOVEREIGN_OS_IMAGE_DIR="${image_dir}" \
    "${REPO_ROOT}/scripts/build/09-image-verify.sh"
fi

# ----------- result ---------------

echo
total=$((pass + fail + skip))
echo "tests/qemu/scaffold.sh: ${pass}/${total} passed; ${skip} skipped (KVM/qemu/image absent)"
[ "${fail}" -eq 0 ] && exit 0 || exit 1
