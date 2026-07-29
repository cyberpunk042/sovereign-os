# scripts/build/lib/kernel-debs.sh — where the custom kernel .debs are.
#
# ONE resolution order, shared by every substrate builder.
#
# WHY THIS EXISTS (2026-07-29). The two installer builders each hardcoded a
# fallback, and the two fallbacks DISAGREED:
#
#     installer-cdd/build.sh      /mnt/kernel_forge/kernel-debs
#     ubuntu-autoinstall/build.sh /mnt/kernel_forge          <- missing suffix
#
# Neither path exists on the operator's machine. The Debian build worked only
# because step 07 sources the state file below before invoking it; running
# either builder DIRECTLY failed, and the Ubuntu one failed with a path that was
# wrong in a second, independent way. A stale default that is only ever correct
# via a caller's environment is not a default, it is a trap.
#
# The authority is step 04, which writes:
#     ${SOVEREIGN_OS_STATE_DIR}/env-kernel-debs.sh
#     export SOVEREIGN_OS_KERNEL_DEBS_DIR="…/kernel-forge/kernel-debs"
#
# Order, highest first:
#   1. SOVEREIGN_OS_KERNEL_DEBS_DIR already in the environment (operator or
#      step 07, which sources the same state file)
#   2. the state file written by step 04
#   3. the default forge location under the invoking user's home
#   4. the legacy /mnt/kernel_forge mount, kept so an existing operator setup
#      does not break
#
# Sets SOVEREIGN_OS_KERNEL_DEBS_DIR. Never fails — the CALLER decides whether a
# missing directory is fatal, because that differs (the installers require the
# .debs; some substrates can build without them).

kernel_debs_dir() {
  if [ -n "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" ]; then
    printf '%s\n' "${SOVEREIGN_OS_KERNEL_DEBS_DIR}"
    return 0
  fi

  _kdd_state="${SOVEREIGN_OS_STATE_DIR:-${HOME:-/root}/.sovereign-os/build-state}"
  if [ -r "${_kdd_state}/env-kernel-debs.sh" ]; then
    # shellcheck disable=SC1090
    . "${_kdd_state}/env-kernel-debs.sh" || true
    if [ -n "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" ]; then
      printf '%s\n' "${SOVEREIGN_OS_KERNEL_DEBS_DIR}"
      return 0
    fi
  fi

  for _kdd_c in "${SOVEREIGN_OS_FORGE_DIR:-${HOME:-/root}/.sovereign-os/kernel-forge}/kernel-debs" \
                /mnt/kernel_forge/kernel-debs; do
    if ls "${_kdd_c}"/linux-image-*.deb >/dev/null 2>&1; then
      printf '%s\n' "${_kdd_c}"
      return 0
    fi
  done

  # Nothing found: return the canonical location so the caller's error message
  # names the place the operator should actually look.
  printf '%s\n' "${SOVEREIGN_OS_FORGE_DIR:-${HOME:-/root}/.sovereign-os/kernel-forge}/kernel-debs"
}
