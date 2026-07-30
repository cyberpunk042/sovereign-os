#!/usr/bin/env bash
# missing executables — install what the .deb did not carry
# gate: IAC_ENABLE_BINARIES
#
# WHY: three shipped units point at executables that do not exist on this host,
# because sovereign-os-cockpit is Architecture:all and carries neither the
# `make guardian`-installed script nor the `make bins` Rust output:
#
#   /usr/local/bin/guardian-core        sovereign-guardian-core.service
#   /usr/local/bin/sovereign-gatewayd   sovereign-gatewayd.service
#   sovereign-telemetry (on PATH)       sovereign-telemetry-textfile.timer
#
# Upstream already knows this failure mode. Makefile, at the guardian-core
# install line:
#     "the fleet install must carry the binary the unit points at, or the unit
#      ships as an orphan (enable -> start failure). Was previously only
#      installed by the standalone scripts/auditor/install.sh, which nothing in
#      the make flow invoked (found + fixed 2026-07-17)."
# The fix landed in `make install`; the package we received predates or omits it.
#
# TWO TIERS, because the cost is wildly different:
#   guardian-core is a PYTHON script (scripts/auditor/guardian-core.py) — a
#     755 install, no toolchain, effectively free. Done by default.
#   sovereign-gatewayd / sovereign-telemetry / sovereign-resource-control are
#     Rust, need rustup 1.89.0 (rust-toolchain.toml; Ubuntu's apt rust is older)
#     and a long release build. Gated behind IAC_ENABLE_RUST_BINS.
#
# Module 20 reads the results of this module: it derives gatewayd's and the
# telemetry timer's desired state from whether the binary is present, so a
# successful build here flips them from masked/disabled to enabled on the NEXT
# converge run (or this one, if 20 has not executed yet — it has, so re-run).
#
# shellcheck shell=bash

_src="${IAC_SOURCE_RESOLVED_DIR:-${IAC_SOURCE_DIR:-}}"
if [ -z "${_src}" ] || [ ! -d "${_src}/.git" ]; then
  skip "no source checkout resolved — module 15 must succeed first"
  return 0 2>/dev/null || exit 0
fi
iac_info "source: ${_src}"

_prefix="${IAC_BIN_PREFIX:-/usr/local}"

# ─── tier 1: guardian-core (python, free) ────────────────────────────────────
_gsrc="${_src}/scripts/auditor/guardian-core.py"
_gdst="${_prefix}/bin/guardian-core"

if [ ! -f "${_gsrc}" ]; then
  skip "guardian-core.py not in checkout"
elif [ -f "${_gdst}" ] && cmp -s "${_gsrc}" "${_gdst}"; then
  ok "guardian-core installed"
elif [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "install guardian-core → ${_gdst}"
else
  if install -d "${_prefix}/bin" 2>/dev/null && install -m 755 "${_gsrc}" "${_gdst}" 2>/dev/null; then
    changed "installed guardian-core → ${_gdst}"
  else
    fail "could not install guardian-core → ${_gdst}"
  fi
fi

# ─── tier 2: the Rust binaries ───────────────────────────────────────────────
if [ "${IAC_ENABLE_RUST_BINS:-0}" != 1 ]; then
  skip "Rust binaries not built (IAC_ENABLE_RUST_BINS=0) — gatewayd + telemetry stay held down by module 20"
  return 0 2>/dev/null || exit 0
fi

# Everything `make bins` installs, so we can tell "already built" cheaply.
_rust_bins="sovereign-telemetry sovereign-resource-control sovereign-gatewayd"

_all_present=1
for b in ${_rust_bins}; do
  [ -x "${_prefix}/bin/${b}" ] || _all_present=0
done
if [ "${_all_present}" = 1 ]; then
  ok "rust binaries present (${_rust_bins// /, })"
  return 0 2>/dev/null || exit 0
fi

# ---- toolchain ----
# rust-toolchain.toml pins 1.89.0 and rustup honours it automatically, so we
# only need rustup itself on PATH — not a specific system rustc.
_cargo="$(command -v cargo 2>/dev/null || true)"
if [ -z "${_cargo}" ] && [ -x "${HOME:-/root}/.cargo/bin/cargo" ]; then
  _cargo="${HOME:-/root}/.cargo/bin/cargo"
fi
if [ -z "${_cargo}" ]; then
  # Deliberately NOT auto-installing rustup: it is a curl|sh into root's home
  # and belongs to an explicit operator decision, not a converge side effect.
  fail "cargo not found — install the pinned toolchain first: ${_src}/scripts/install/rust-toolchain.sh (rustup, channel 1.89.0)"
  return 0 2>/dev/null || exit 0
fi
iac_info "cargo: ${_cargo}"

if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "build + install ${_rust_bins// /, } (cargo release build)"
  return 0 2>/dev/null || exit 0
fi

# `make bins` CPU-tunes via scripts/build/cpu-features.py against PROFILE.
# Build as the checkout's owner so target/ and ~/.cargo stay theirs, not root's.
_owner="$(stat -c '%U' "${_src}" 2>/dev/null || echo root)"
iac_info "building as ${_owner} — this takes a while"

if sudo -u "${_owner}" env PATH="$(dirname "${_cargo}"):${PATH}" \
      make -C "${_src}" bins PROFILE="${IAC_PROFILE_ID}" PREFIX="${_prefix}" >/dev/null 2>&1; then
  :
elif sudo -u "${_owner}" env PATH="$(dirname "${_cargo}"):${PATH}" \
      make -C "${_src}" bins PROFILE="${IAC_PROFILE_ID}" PREFIX="${_prefix}" SOVEREIGN_OS_BINS_TUNE=0 >/dev/null 2>&1; then
  # A CPU-tuned build can fail on RUSTFLAGS the host rustc rejects; the portable
  # build is the documented fallback (SOVEREIGN_OS_BINS_TUNE=0).
  iac_info "CPU-tuned build failed; portable build succeeded"
else
  fail "make bins failed — run manually: make -C ${_src} bins PROFILE=${IAC_PROFILE_ID}"
  return 0 2>/dev/null || exit 0
fi

# `make bins` installs as the build user, which cannot write /usr/local/bin.
# Re-install from target/release as root when the make step could not.
for b in ${_rust_bins}; do
  _art="${_src}/target/release/${b}"
  if [ -x "${_prefix}/bin/${b}" ]; then
    ok "binary ${b}"
  elif [ -x "${_art}" ]; then
    if install -m 755 "${_art}" "${_prefix}/bin/${b}" 2>/dev/null; then
      changed "installed ${b} → ${_prefix}/bin/${b}"
    else
      fail "could not install ${b}"
    fi
  else
    fail "${b} not produced by the build"
  fi
done

iac_info "re-run converge so module 20 promotes gatewayd + the telemetry timer"
