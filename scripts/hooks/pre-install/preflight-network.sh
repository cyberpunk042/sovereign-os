#!/usr/bin/env bash
# scripts/hooks/pre-install/preflight-network.sh
#
# Pre-install reachability check. Runs from the live-USB / installer
# environment BEFORE the target disk is touched.
#
# What it validates:
#   • a default route exists
#   • DNS resolves the configured Debian mirror (default: deb.debian.org)
#   • DNS resolves huggingface.co (post-install model pulls will need it)
#   • the mirror responds with HTTP 200 on /debian/dists/<release>/Release
#
# Exit 0 on PASS; non-zero on FAIL. Honors SOVEREIGN_OS_DRY_RUN=1:
# in dry-run mode, emits "would check X" lines and exits 0.
#
# Tunable env vars:
#   SOVEREIGN_OS_PREFLIGHT_MIRROR        default: deb.debian.org
#   SOVEREIGN_OS_PREFLIGHT_RELEASE       default: trixie
#   SOVEREIGN_OS_PREFLIGHT_SKIP_HF       set to 1 to skip huggingface check (air-gapped)
#   SOVEREIGN_OS_PREFLIGHT_HF_HOST       default: huggingface.co

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="preflight-network"

: "${SOVEREIGN_OS_PREFLIGHT_MIRROR:=deb.debian.org}"
: "${SOVEREIGN_OS_PREFLIGHT_RELEASE:=trixie}"
: "${SOVEREIGN_OS_PREFLIGHT_HF_HOST:=huggingface.co}"

log_step_header "${STEP_ID}" "installer-time network reachability check"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would check:"
  log_info "  • default route present"
  log_info "  • DNS resolves ${SOVEREIGN_OS_PREFLIGHT_MIRROR}"
  log_info "  • HTTP 200 from http://${SOVEREIGN_OS_PREFLIGHT_MIRROR}/debian/dists/${SOVEREIGN_OS_PREFLIGHT_RELEASE}/Release"
  if [ -z "${SOVEREIGN_OS_PREFLIGHT_SKIP_HF:-}" ]; then
    log_info "  • DNS resolves ${SOVEREIGN_OS_PREFLIGHT_HF_HOST}"
  fi
  exit 0
fi

fail=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_info "  PASS — ${desc}"
  else
    log_error "  FAIL — ${desc}"
    fail=$((fail + 1))
  fi
}

# 1. default route
check "default route present" \
  bash -c "ip route show default 2>/dev/null | grep -q '^default'"

# 2. DNS resolves mirror
check "DNS resolves ${SOVEREIGN_OS_PREFLIGHT_MIRROR}" \
  bash -c "getent hosts '${SOVEREIGN_OS_PREFLIGHT_MIRROR}' || host '${SOVEREIGN_OS_PREFLIGHT_MIRROR}' 2>/dev/null"

# 3. Mirror Release file fetches
release_url="http://${SOVEREIGN_OS_PREFLIGHT_MIRROR}/debian/dists/${SOVEREIGN_OS_PREFLIGHT_RELEASE}/Release"
if command -v curl >/dev/null 2>&1; then
  check "mirror serves ${SOVEREIGN_OS_PREFLIGHT_RELEASE}/Release (HTTP 200)" \
    bash -c "curl -fsSI --max-time 10 '${release_url}' >/dev/null"
elif command -v wget >/dev/null 2>&1; then
  check "mirror serves ${SOVEREIGN_OS_PREFLIGHT_RELEASE}/Release (HTTP 200)" \
    bash -c "wget -q --spider --timeout=10 '${release_url}'"
else
  log_warn "  SKIP — neither curl nor wget available to test mirror"
fi

# 4. HuggingFace reachable (unless explicitly skipped)
if [ -z "${SOVEREIGN_OS_PREFLIGHT_SKIP_HF:-}" ]; then
  check "DNS resolves ${SOVEREIGN_OS_PREFLIGHT_HF_HOST} (for post-install model pulls)" \
    bash -c "getent hosts '${SOVEREIGN_OS_PREFLIGHT_HF_HOST}' || host '${SOVEREIGN_OS_PREFLIGHT_HF_HOST}' 2>/dev/null"
else
  log_info "  SKIP — huggingface.co check disabled (SOVEREIGN_OS_PREFLIGHT_SKIP_HF=1)"
fi

if [ "${fail}" -eq 0 ]; then
  log_info "${STEP_ID}: PASS"
  exit 0
else
  log_error "${STEP_ID}: FAIL (${fail} issue(s))"
  exit 1
fi
