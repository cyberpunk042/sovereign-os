#!/usr/bin/env bash
# scripts/build/build-intelligence.sh — compile sovereign-os's OWN intelligence
# layer (crates/ — the Deterministic Cortex Runtime [M009], Memory OS [M028],
# retrieval + reasoning stack, ~712 crates / 218K LOC) with the pinned Rust
# toolchain, and install its daemon binaries. THIS STEP WAS MISSING: without it
# a flashed image ships the brain as UNCOMPILED SOURCE. Idempotent (cargo caches
# incrementally); --dry-run previews.
#
#   ⚡ YOU RUN:  scripts/build/build-intelligence.sh        (or via make provision)
#
# Env:
#   SOVEREIGN_OS_RUST_PROFILE  release|dev   (default release)
#   SOVEREIGN_OS_RUST_BINDIR   daemon install dir (default /usr/local/lib/sovereign-os/bin)
set -euo pipefail

DRY_RUN=""; [ "${1:-}" = "--dry-run" ] && DRY_RUN=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "${REPO}"
PROFILE="${SOVEREIGN_OS_RUST_PROFILE:-release}"
BINDIR="${SOVEREIGN_OS_RUST_BINDIR:-/usr/local/lib/sovereign-os/bin}"

# 1) toolchain (idempotent — installs nothing if a new-enough cargo is present)
"${REPO}/scripts/install/rust-toolchain.sh" ${DRY_RUN:+--dry-run}
# shellcheck disable=SC1090
. "${HOME}/.cargo/env" 2>/dev/null || true
CARGO="$(command -v cargo 2>/dev/null || echo "${HOME}/.cargo/bin/cargo")"

flag="--release"; OUT="target/release"
[ "${PROFILE}" = "dev" ] && { flag=""; OUT="target/debug"; }

if [ -n "${DRY_RUN}" ]; then
  echo "  dry-run: ${CARGO} build ${flag} --bins   →  install daemons to ${BINDIR}"
  exit 0
fi

# 2) build the daemon binaries + their whole dependency graph
echo "  compiling the intelligence layer (profile=${PROFILE}) — the first build is long…"
"${CARGO}" build ${flag} --bins

# 3) install the compiled daemons (best-effort; BINDIR usually needs root)
mkdir -p "${BINDIR}" 2>/dev/null || sudo mkdir -p "${BINDIR}" 2>/dev/null || true
n=0
for b in "${OUT}"/*; do
  [ -f "${b}" ] && [ -x "${b}" ] || continue      # skip .d files, deps/, build/
  install -m 0755 "${b}" "${BINDIR}/" 2>/dev/null \
    || sudo install -m 0755 "${b}" "${BINDIR}/" 2>/dev/null || continue
  n=$((n + 1))
done
echo "  ✓ intelligence layer built · ${n} daemon binaries → ${BINDIR}"
