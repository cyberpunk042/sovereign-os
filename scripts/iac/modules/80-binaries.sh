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

# PRESENT IS NOT CURRENT.
# This used to test only [ -x "${_prefix}/bin/${b}" ] and return early, so once
# the binaries existed the module never rebuilt again — a source change could be
# committed, tested, and converged with converge reporting "0 changed" while the
# running daemon kept the binary from days earlier. Exactly what happened after
# the end-of-turn fix landed: 213 tests green, gatewayd restarted, identical
# output, because /usr/local/bin/sovereign-gatewayd predated the source by a day.
#
# Compare the installed binary against the newest source that feeds it. Cargo
# already does precise dependency tracking; this only decides whether to ask it.
_newest_src=0
for d in "${_src}/crates" "${_src}/Cargo.toml" "${_src}/Cargo.lock"; do
  [ -e "${d}" ] || continue
  _t="$(find "${d}" \( -name '*.rs' -o -name 'Cargo.toml' -o -name 'Cargo.lock' \) \
        -printf '%T@\n' 2>/dev/null | cut -d. -f1 | sort -rn | head -1)"
  [ -n "${_t}" ] && [ "${_t}" -gt "${_newest_src}" ] 2>/dev/null && _newest_src="${_t}"
done

_all_current=1
_stale=""
for b in ${_rust_bins}; do
  if [ ! -x "${_prefix}/bin/${b}" ]; then
    _all_current=0; _stale="${_stale} ${b}(missing)"
    continue
  fi
  _bt="$(stat -c %Y "${_prefix}/bin/${b}" 2>/dev/null || echo 0)"
  if [ "${_newest_src}" -gt "${_bt}" ] 2>/dev/null; then
    _all_current=0; _stale="${_stale} ${b}(stale)"
  fi
done

if [ "${_all_current}" = 1 ]; then
  ok "rust binaries current (${_rust_bins// /, })"
  return 0 2>/dev/null || exit 0
fi
iac_info "rebuild needed —${_stale}"
iac_info "newest source $(date -d "@${_newest_src}" '+%Y-%m-%d %H:%M' 2>/dev/null)"

# ---- toolchain ----
# rust-toolchain.toml pins 1.89.0 and rustup honours it automatically, so we
# only need the rustup shim — not a specific system rustc.
#
# Resolve cargo from the CHECKOUT OWNER's home, not $HOME. rust-toolchain.sh
# installs user-level into ~/.cargo for the operator (deliberately, and it is
# $SUDO_USER-aware), but converge runs under sudo where $HOME is /root — so
# "${HOME}/.cargo/bin/cargo" looks in the one place it will never be. The build
# runs as the owner anyway, so ask about the owner.
_owner="$(stat -c '%U' "${_src}" 2>/dev/null || echo root)"
_owner_home="$(getent passwd "${_owner}" 2>/dev/null | cut -d: -f6)"
: "${_owner_home:=/root}"

_cargo=""
for c in "${_owner_home}/.cargo/bin/cargo" "$(command -v cargo 2>/dev/null || true)"; do
  [ -n "${c}" ] && [ -x "${c}" ] && { _cargo="${c}"; break; }
done
if [ -z "${_cargo}" ]; then
  # Deliberately NOT auto-installing rustup: it is a curl|sh into root's home
  # and belongs to an explicit operator decision, not a converge side effect.
  fail "cargo not found — install the pinned toolchain first: ${_src}/scripts/install/rust-toolchain.sh (rustup, channel 1.89.0)"
  return 0 2>/dev/null || exit 0
fi
iac_info "cargo: ${_cargo} (build user: ${_owner})"

if [ "${IAC_DRY_RUN}" = 1 ]; then
  changed "build + install ${_rust_bins// /, } (cargo release build)"
  return 0 2>/dev/null || exit 0
fi

# `make bins` CPU-tunes via scripts/build/cpu-features.py against PROFILE.
# Build as the checkout's owner so target/ and ~/.cargo stay theirs, not root's.
iac_info "building as ${_owner} — this takes a while"

# Build output goes to a LOG, never /dev/null. A compile failure is exactly the
# case where the operator needs the error, and discarding it turns a one-line
# rustc diagnostic into a blind "make bins failed". Learned the hard way.
_log="/var/log/sovereign-os/iac-build.log"
install -d "$(dirname "${_log}")" 2>/dev/null || true

# `make bins` is build-THEN-install in one target. The build must run as the
# checkout owner (so target/ and ~/.cargo stay theirs, and so rustup resolves
# the pinned toolchain), but its install step writes to PREFIX/bin — which is
# root:root drwxr-xr-x. Run wholesale as the owner, the compile succeeds and
# then `install` dies with permission denied, so make exits non-zero and the
# whole step reads as "build failed" when the binaries are sitting in
# target/release perfectly fine.
#
# Stage into a DESTDIR the owner CAN write, so make completes honestly, then
# copy into place as root below. DESTDIR is exactly what the Makefile's
# $(DESTDIR)$(PREFIX) install lines are for.
_stage="$(mktemp -d)"
chown "${_owner}" "${_stage}" 2>/dev/null || true

_mk() {
  sudo -u "${_owner}" env PATH="$(dirname "${_cargo}"):${PATH}" \
    make -C "${_src}" bins PROFILE="${IAC_PROFILE_ID}" PREFIX="${_prefix}" \
      DESTDIR="${_stage}" "$@"
}

if _mk >"${_log}" 2>&1; then
  :
elif _mk SOVEREIGN_OS_BINS_TUNE=0 >>"${_log}" 2>&1; then
  # A CPU-tuned build can fail on RUSTFLAGS the host rustc rejects; the portable
  # build is the documented fallback (SOVEREIGN_OS_BINS_TUNE=0).
  iac_info "CPU-tuned build failed; portable build succeeded"
else
  # Surface the actual reason inline — the operator should not have to go
  # hunting for a log to learn what broke.
  _err="$(grep -oE '^error(\[[A-Z0-9]+\])?: .*' "${_log}" 2>/dev/null | head -3)"
  [ -z "${_err}" ] && _err="$(tail -5 "${_log}" 2>/dev/null)"
  fail "make bins failed"
  printf '%s\n' "${_err}" | while IFS= read -r l; do [ -n "${l}" ] && iac_info "${l}"; done
  iac_info "full log: ${_log}"
  iac_info "reproduce: make -C ${_src} bins PROFILE=${IAC_PROFILE_ID}"
  rm -rf "${_stage}" 2>/dev/null || true
  return 0 2>/dev/null || exit 0
fi

# ---- promote the staged binaries into place, as root ----
# Prefer the staged copy (what make just produced); fall back to target/release
# so a partially-staged build still lands something verifiable.
for b in ${_rust_bins}; do
  _art="${_stage}${_prefix}/bin/${b}"
  [ -x "${_art}" ] || _art="${_src}/target/release/${b}"

  if [ ! -x "${_art}" ]; then
    fail "${b} not produced by the build"
    continue
  fi
  if [ -x "${_prefix}/bin/${b}" ] && cmp -s "${_art}" "${_prefix}/bin/${b}"; then
    ok "binary ${b}"
  elif install -m 755 "${_art}" "${_prefix}/bin/${b}" 2>/dev/null; then
    changed "installed ${b} → ${_prefix}/bin/${b}"
    # Remember it: the restart loop below only touches units whose binary
    # actually changed on this run.
    _installed_bins="${_installed_bins:-} ${b}"
  else
    fail "could not install ${b}"
  fi
done

rm -rf "${_stage}" 2>/dev/null || true

# ---- restart whatever is RUNNING an old copy of a binary we just replaced ----
# Installing a binary does nothing to a process already holding the previous
# one. This module used to end by saying "re-run converge so module 20 promotes
# gatewayd" — but module 20 only asserts enabled/active, and the daemon is
# already active, so nothing ever restarted it. Net effect: a rebuilt binary
# landed on disk, converge reported success, and the old process kept serving
# indefinitely. Exactly how the end-of-turn fix appeared to do nothing despite
# 213 passing tests.
#
# Own the consequence of the change, the way module 50 does for the NUT driver
# and module 60 for the patched QEMU args.
_restart_for() {
  case "$1" in
    sovereign-gatewayd)          echo "sovereign-gatewayd.service" ;;
    sovereign-telemetry)         echo "" ;;  # timer-driven oneshot; next tick picks it up
    sovereign-resource-control)  echo "" ;;  # invoked ad hoc, no long-lived unit
    *)                           echo "" ;;
  esac
}

for b in ${_installed_bins:-}; do
  for u in $(_restart_for "${b}"); do
    systemctl list-unit-files "${u}" --no-legend >/dev/null 2>&1 || continue
    systemctl is-active --quiet "${u}" 2>/dev/null || continue
    if run "restart-consumer" systemctl restart "${u}"; then
      changed "restarted ${u} onto the new ${b}"
    else
      fail "installed ${b} but could not restart ${u}"
    fi
  done
done
