#!/usr/bin/env bash
# scripts/hooks/post-install/tetragon-install.sh
#
# Install the Tetragon daemon from Cilium's release tarball at first
# boot. Tetragon is NOT in the Debian archive (see the sain-01 profile
# packages note), so the profile's claim "installs at first boot from
# Cilium's release tarball" is realized HERE — before this hook existed,
# tetragon-policy-load.sh hard-failed on a fresh image because nothing
# ever installed the daemon (found + fixed 2026-07-17).
#
# Runs BEFORE tetragon-policy-load in the sain-01 first-boot chain.
# FAIL-LOUD: the kernel fence is a mandatory security boundary; a
# missing daemon must be visible, not silently skipped. Resumable
# post-flash (re-run this script, then tetragon-policy-load).
#
# Supply chain (operator-owned, per the MS003/mkosi key doctrine):
#   - Version pinned below; override: SOVEREIGN_OS_TETRAGON_VERSION
#   - Tarball checksum verified against either the operator-pinned
#     SOVEREIGN_OS_TETRAGON_SHA256 or the release's published
#     .sha256sum sibling asset. No checksum source → hard fail.
#
# Vendor flow (tetragon.io/docs/installation/package, verified
# 2026-07-17): tetragon-v<VER>-amd64.tar.gz → extract → sudo ./install.sh
# → systemd-managed `tetragon` service.
set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="tetragon-install"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

# Pinned daemon version (latest stable per tetragon.io, 2026-07-17).
: "${SOVEREIGN_OS_TETRAGON_VERSION:=1.7.0}"
# Optional operator-pinned tarball sha256 (hex). When set, it is the
# ONLY accepted checksum source (stronger than the published sibling).
: "${SOVEREIGN_OS_TETRAGON_SHA256:=}"

log_step_header "${STEP_ID}" "install Tetragon daemon v${SOVEREIGN_OS_TETRAGON_VERSION} (Cilium release tarball)"

emit_tetragon_install_metric() {
  emit_metric sovereign_os_post_install_tetragon_install_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

require_root

# ---- idempotency: daemon already present is a no-op ----
if command -v tetragon >/dev/null 2>&1; then
  log_info "tetragon already installed ($(command -v tetragon)) — no-op"
  emit_tetragon_install_metric already-present
  exit 0
fi

require_command curl "apt install curl"
require_command tar

arch="amd64"
tarball="tetragon-v${SOVEREIGN_OS_TETRAGON_VERSION}-${arch}.tar.gz"
base_url="https://github.com/cilium/tetragon/releases/download/v${SOVEREIGN_OS_TETRAGON_VERSION}"
workdir="$(mktemp -d /tmp/tetragon-install.XXXXXX)"
trap 'rm -rf "${workdir}"' EXIT

log_info "fetching ${base_url}/${tarball}"
if ! curl -fsSL "${base_url}/${tarball}" -o "${workdir}/${tarball}"; then
  log_error "download failed: ${base_url}/${tarball}"
  log_error "REMEDIATION: check network, or re-run post-flash:"
  log_error "  sudo ${__REPO_ROOT}/scripts/hooks/post-install/tetragon-install.sh"
  emit_tetragon_install_metric download-failed
  exit 1
fi

# ---- checksum verification (operator-owned supply chain) ----
actual_sha="$(sha256sum "${workdir}/${tarball}" | awk '{print $1}')"
if [ -n "${SOVEREIGN_OS_TETRAGON_SHA256}" ]; then
  if [ "${actual_sha}" != "${SOVEREIGN_OS_TETRAGON_SHA256}" ]; then
    log_error "tarball sha256 mismatch against operator-pinned value"
    log_error "  expected: ${SOVEREIGN_OS_TETRAGON_SHA256}"
    log_error "  actual:   ${actual_sha}"
    emit_tetragon_install_metric checksum-mismatch
    exit 1
  fi
  log_info "sha256 verified against operator-pinned SOVEREIGN_OS_TETRAGON_SHA256"
elif curl -fsSL "${base_url}/${tarball}.sha256sum" -o "${workdir}/${tarball}.sha256sum"; then
  published_sha="$(awk '{print $1}' "${workdir}/${tarball}.sha256sum")"
  if [ "${actual_sha}" != "${published_sha}" ]; then
    log_error "tarball sha256 mismatch against published .sha256sum asset"
    log_error "  published: ${published_sha}"
    log_error "  actual:    ${actual_sha}"
    emit_tetragon_install_metric checksum-mismatch
    exit 1
  fi
  log_info "sha256 verified against published release .sha256sum"
else
  log_error "no checksum source: release .sha256sum asset unreachable and"
  log_error "SOVEREIGN_OS_TETRAGON_SHA256 not set — refusing unverified install"
  log_error "REMEDIATION: export SOVEREIGN_OS_TETRAGON_SHA256=<hex> (from a"
  log_error "trusted mirror of the v${SOVEREIGN_OS_TETRAGON_VERSION} release) and re-run"
  emit_tetragon_install_metric no-checksum-source
  exit 1
fi

# ---- extract + vendor install.sh (installs binaries + systemd unit) ----
tar -xzf "${workdir}/${tarball}" -C "${workdir}"
extract_dir="${workdir}/tetragon-v${SOVEREIGN_OS_TETRAGON_VERSION}-${arch}"
if [ ! -x "${extract_dir}/install.sh" ]; then
  log_error "vendor install.sh missing/not executable in ${tarball}"
  emit_tetragon_install_metric bad-tarball
  exit 1
fi
if ! (cd "${extract_dir}" && ./install.sh); then
  log_error "vendor install.sh failed"
  emit_tetragon_install_metric vendor-install-failed
  exit 1
fi

if ! command -v tetragon >/dev/null 2>&1; then
  log_error "tetragon binary still not on PATH after vendor install"
  emit_tetragon_install_metric post-install-missing
  exit 1
fi

log_info "tetragon v${SOVEREIGN_OS_TETRAGON_VERSION} installed ($(command -v tetragon))"
log_info "policy load + service enable happens next in the chain (tetragon-policy-load)"
emit_tetragon_install_metric installed
exit 0
