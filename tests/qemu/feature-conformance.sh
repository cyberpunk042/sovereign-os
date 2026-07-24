#!/usr/bin/env bash
# tests/qemu/feature-conformance.sh — Layer 4 in-guest feature conformance
# (closes the F-2026-052 "Layer-4 is scaffold-only" gap with a REAL harness).
#
# Layer 4 to date (scaffold.sh) proves only that the image BOOTS. This harness
# adds the missing half: once the image is up, run the shipped features' LIVE
# self-tests INSIDE the guest and assert they all pass — the same
# `sovereign-feature-selftest --self-check` the Feature Test Lab panel drives,
# but exercised against the real booted OS.
#
# The in-guest RUN needs a KVM-capable runner + a built image (same three
# preconditions as scaffold.sh), so on a plain CI runner this SKIPs (exit 0)
# with an operator-actionable reason. The feature self-test PAYLOAD itself is
# covered host-side by `cargo test -p sovereign-feature-selftest`
# (every_feature_self_test_passes) — so the features are verified even where the
# QEMU transport can't run; this harness verifies they pass on the REAL image.
#
# Usage:
#   tests/qemu/feature-conformance.sh [profile]     # default profile: sain-01
#
# Exit codes: 0 = passed OR gracefully skipped; 1 = a conformance failure.

set -euo pipefail

PROFILE="${1:-sain-01}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

green='\033[32m'; yellow='\033[33m'; red='\033[31m'; bold='\033[1m'; reset='\033[0m'
pass=0; fail=0; skip=0
ok() { echo -e "  ${green}PASS${reset} — $1"; pass=$((pass + 1)); }
sk() { echo -e "  ${yellow}SKIP${reset} — $1"; skip=$((skip + 1)); }
ko() { echo -e "  ${red}FAIL${reset} — $1"; fail=$((fail + 1)); }

echo -e "${bold}tests/qemu/feature-conformance.sh${reset} — profile=${PROFILE}"
echo

# ---- the in-guest payload: build the self-test binary for the guest ----
selftest_bin="${REPO_ROOT}/target/release/sovereign-feature-selftest"
if cargo build --release -p sovereign-feature-selftest >/dev/null 2>&1 \
    && [ -x "${selftest_bin}" ]; then
  ok "sovereign-feature-selftest built (the in-guest conformance payload)"
else
  ko "sovereign-feature-selftest failed to build"
fi

# ---- preconditions for the in-guest RUN (mirror scaffold.sh) ----
kvm_ok=0; [ -e /dev/kvm ] && [ -r /dev/kvm ] && kvm_ok=1
qemu_ok=0; command -v qemu-system-x86_64 >/dev/null 2>&1 && qemu_ok=1
image_dir="${SOVEREIGN_OS_IMAGE_DIR:-}"
if [ -z "${image_dir}" ]; then
  for c in "${REPO_ROOT}/build/${PROFILE}/output" "/var/lib/sovereign-os/output"; do
    if [ -d "${c}" ] && find "${c}" -maxdepth 1 \( -name '*.raw' -o -name '*.iso' \) -type f 2>/dev/null | grep -q .; then
      image_dir="${c}"; break
    fi
  done
fi
image_ok=0
[ -n "${image_dir}" ] && [ -d "${image_dir}" ] \
  && find "${image_dir}" -maxdepth 1 \( -name '*.raw' -o -name '*.iso' \) -type f 2>/dev/null | grep -q . \
  && image_ok=1

[ "${kvm_ok}" -eq 1 ]   || sk "/dev/kvm absent — in-guest run needs KVM acceleration"
[ "${qemu_ok}" -eq 1 ]  || sk "qemu-system-x86_64 not installed"
[ "${image_ok}" -eq 1 ] || sk "no built image (run orchestrate.sh run first)"

# ---- the in-guest run (gated on all three preconditions) ----
if [ "${kvm_ok}" -eq 1 ] && [ "${qemu_ok}" -eq 1 ] && [ "${image_ok}" -eq 1 ]; then
  echo
  echo -e "${bold}preconditions met — booting + running the self-test in-guest${reset}"
  serial_log="$(mktemp)"
  # 09-image-verify.sh boots the image and logs in as root over the serial
  # console; SOVEREIGN_OS_INGUEST_CMD runs after login and its stdout is
  # captured to the serial log the monitor persists.
  if SOVEREIGN_OS_IMAGE_DIR="${image_dir}" \
     SOVEREIGN_OS_SERIAL_LOG="${serial_log}" \
     SOVEREIGN_OS_INGUEST_CMD="sovereign-feature-selftest --self-check" \
     "${REPO_ROOT}/scripts/build/09-image-verify.sh"; then
    if grep -q '"all_ok": true' "${serial_log}" 2>/dev/null; then
      ok "in-guest self-check reported all_ok=true (features conform on the real image)"
    else
      ko "in-guest self-check did NOT report all_ok=true (see ${serial_log})"
    fi
  else
    ko "image boot / in-guest run failed (see ${serial_log})"
  fi
fi

# ---- result ----
echo
total=$((pass + fail + skip))
echo "tests/qemu/feature-conformance.sh: ${pass}/${total} passed; ${skip} skipped"
if [ "${skip}" -gt 0 ] && [ "${fail}" -eq 0 ]; then
  echo -e "${yellow}  (the in-guest run is environment-gated; the feature payload is covered by${reset}"
  echo -e "${yellow}   cargo test -p sovereign-feature-selftest even when this SKIPs)${reset}"
fi
[ "${fail}" -eq 0 ] && exit 0 || exit 1
