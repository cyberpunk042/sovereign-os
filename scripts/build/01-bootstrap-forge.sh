#!/usr/bin/env bash
# scripts/build/01-bootstrap-forge.sh — bootstrap the kernel-forge.
#
# Per E101 (info-hub `wiki/backlog/epics/milestone-sain01/e101-sovereign-os-build.md`):
#   "64 GB tmpfs ramdisk mounted at /mnt/kernel_forge; kernel source
#    extracted there" + GCC 14 + build toolchain.
#
# Corrects the L0 dump's `bwarw tools-compiler` hallucination to real
# Debian package names (per SDD-006).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="01-bootstrap-forge"

: "${SOVEREIGN_OS_FORGE_DIR:=/mnt/kernel_forge}"
: "${SOVEREIGN_OS_FORGE_SIZE:=64G}"

# Real Debian packages — corrects L0 dump's `bwarw tools-compiler`
REQUIRED_PACKAGES=(
  build-essential
  libncurses-dev
  bison
  flex
  libssl-dev
  libelf-dev
  bc
  git
  rsync
  debhelper
  pahole
  gcc-14
  g++-14
  cpio
  kmod
)

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}")"

# The forge DIRECTORY is the output. It is a tmpfs, so a reboot removes it
# while the recorded "completed" survives — and skipping this step then
# means nothing ever remounts it (2026-07-30).
if ! state_step_should_run "${STEP_ID}" "${inputs_hash}" \
     "${SOVEREIGN_OS_FORGE_DIR}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "bootstrap kernel-forge tmpfs + dev toolchain"
state_step_start "${STEP_ID}" "${inputs_hash}"

# ---- pre-flight ----
log_info "checking pre-requisites"

if ! dpkg --version >/dev/null 2>&1; then
  log_error "this step assumes a Debian/Ubuntu host (dpkg required)"
  state_step_fail "${STEP_ID}" "non-debian-host"
  exit 1
fi

# ---- DRY-RUN short-circuit (operator-verbatim CI/preview safety) ----
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — skipping apt install + tmpfs mount"
  emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  # Record 'dry-run', NOT 'completed' — completing here with the real
  # inputs_hash makes the next REAL run skip this step body entirely.
  state_step_dry_run "${STEP_ID}"
  exit 0
fi

# ---- install packages ----
missing=()
for pkg in "${REQUIRED_PACKAGES[@]}"; do
  if ! dpkg -l "${pkg}" 2>/dev/null | grep -q '^ii'; then
    missing+=("${pkg}")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  log_info "installing missing packages: ${missing[*]}"
  if [ "$(id -u)" -ne 0 ]; then
    log_error "package install requires root; re-run with sudo or pre-install: ${missing[*]}"
    state_step_fail "${STEP_ID}" "needs-root-for-apt"
    exit 1
  fi
  # Guard apt explicitly (per the 03/05 convention): a bare apt-get under
  # `set -e` would abort the step on a repo blip / held package / disk-full
  # WITHOUT a result="fail" sample or state_step_fail — leaving the build in
  # `started` limbo, indistinguishable from a hang. Record the failure like
  # the non-debian / needs-root paths above do.
  if ! DEBIAN_FRONTEND=noninteractive apt-get update; then
    log_error "apt-get update failed — package metadata unavailable (repo/network)"
    emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
    state_step_fail "${STEP_ID}" "apt-update-failed"
    exit 1
  fi
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"; then
    log_error "apt-get install failed for: ${missing[*]} (held package, unmet dep, or disk-full)"
    emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
    state_step_fail "${STEP_ID}" "apt-install-failed"
    exit 1
  fi
else
  log_info "all required packages already installed"
fi

# ---- mount tmpfs forge ----
# The tmpfs is a SPEED optimisation, not a correctness requirement: the kernel
# builds perfectly well on disk, just slower (proven 2026-07-29 — a full
# unprivileged 02→04 build on a plain directory produced a working
# linux-image-6.12.0 in ~13 min on 24 cores).
#
# This used to HARD-FAIL a non-root run. That blocked an otherwise-ready build
# for a performance choice, and — worse — it did so at step 01, so an operator
# whose whole pipeline was ready got "re-run with sudo" and nothing else. Warn
# and continue on disk instead; only a forge dir we cannot USE is fatal.
if mountpoint -q "${SOVEREIGN_OS_FORGE_DIR}" 2>/dev/null; then
  log_info "tmpfs already mounted at ${SOVEREIGN_OS_FORGE_DIR}"
elif [ -n "${SOVEREIGN_OS_FORGE_NO_TMPFS:-}" ]; then
  log_info "SOVEREIGN_OS_FORGE_NO_TMPFS set — building on disk at ${SOVEREIGN_OS_FORGE_DIR}"
  mkdir -p "${SOVEREIGN_OS_FORGE_DIR}"
elif [ "$(id -u)" -ne 0 ]; then
  log_warn "tmpfs mount needs root — continuing ON DISK at ${SOVEREIGN_OS_FORGE_DIR}"
  log_warn "  the kernel build is correct either way, just slower without the ramdisk."
  log_warn "  for the ramdisk: sudo scripts/build/orchestrate.sh run"
  log_warn "  to silence this: export SOVEREIGN_OS_FORGE_NO_TMPFS=1"
  mkdir -p "${SOVEREIGN_OS_FORGE_DIR}"
  emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"on-disk\""
else
  log_info "mounting tmpfs (${SOVEREIGN_OS_FORGE_SIZE}) at ${SOVEREIGN_OS_FORGE_DIR}"
  mkdir -p "${SOVEREIGN_OS_FORGE_DIR}"
  if ! mount -t tmpfs -o "size=${SOVEREIGN_OS_FORGE_SIZE},mode=0755" tmpfs "${SOVEREIGN_OS_FORGE_DIR}"; then
    log_warn "tmpfs mount failed at ${SOVEREIGN_OS_FORGE_DIR} (size=${SOVEREIGN_OS_FORGE_SIZE} — insufficient RAM, or mount blocked)"
    log_warn "  continuing ON DISK; the build is correct, just slower."
    emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
      "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"on-disk\""
  fi
fi

# Whatever we ended up with, it must be USABLE — that IS fatal.
if [ ! -d "${SOVEREIGN_OS_FORGE_DIR}" ] || [ ! -w "${SOVEREIGN_OS_FORGE_DIR}" ]; then
  log_error "forge dir ${SOVEREIGN_OS_FORGE_DIR} is not a writable directory"
  emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "forge-dir-unusable"
  exit 1
fi

# ---- verify gcc-14 reachable ----
if command -v gcc-14 >/dev/null 2>&1; then
  log_info "gcc-14: $(gcc-14 --version | head -1)"
else
  log_warn "gcc-14 not in PATH; later steps may pin via update-alternatives"
fi

# ---- emit handoff env file for subsequent steps ----
env_file="${SOVEREIGN_OS_STATE_DIR}/env-bootstrap.sh"
cat > "${env_file}" <<EOF
# auto-generated by ${STEP_ID}
export SOVEREIGN_OS_FORGE_DIR="${SOVEREIGN_OS_FORGE_DIR}"
EOF
log_info "env handoff written: ${env_file}"

emit_metric sovereign_os_build_step_bootstrap_forge_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
