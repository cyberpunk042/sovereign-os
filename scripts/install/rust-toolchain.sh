#!/usr/bin/env bash
# scripts/install/rust-toolchain.sh — install the Rust toolchain the sovereign-os
# intelligence layer (crates/ — the Deterministic Cortex Runtime, Memory OS,
# retrieval/reasoning stack) builds with. A FIRST-CLASS build-host toolchain, not
# an opportunistic side-effect: rust-toolchain.toml pins the version (currently
# 1.89.0 — edition 2024 / rust-version 1.89). Debian stable ships 1.85 (< 1.89),
# so we install via rustup, user-level (~/.cargo, ~/.rustup) — NEVER apt.
#
#   ⚡ YOU RUN:  scripts/install/rust-toolchain.sh        (or via make provision)
#              --dry-run to preview (changes nothing).
#
# Idempotent (skips when a new-enough cargo is already present). Root-aware: under
# sudo it installs for the invoking operator ($SUDO_USER) — the build runs as the
# operator, not root.
set -euo pipefail

DRY_RUN=""; [ "${1:-}" = "--dry-run" ] && DRY_RUN=1
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ── resolve the operator user + home (install for THEM, even under sudo) ──
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
  U="${SUDO_USER}"; H="$(getent passwd "${U}" | cut -d: -f6)"
  as_user() { sudo -u "${U}" -H "$@"; }
else
  U="$(id -un)"; H="${HOME}"
  as_user() { "$@"; }
fi
CARGO="${H}/.cargo/bin/cargo"; RUSTUP="${H}/.cargo/bin/rustup"

# ── idempotent: is a new-enough cargo (>= 1.89) already there FOR THE OPERATOR? ──
# Probe AS the operator (as_user): running their cargo as root would use root's
# RUSTUP_HOME and mis-report. The trailing `|| true` guarantees the command
# substitution never returns non-zero, so a probe miss can't trip `set -e`.
cur="$(as_user bash -c '{ [ -x "$HOME/.cargo/bin/cargo" ] && "$HOME/.cargo/bin/cargo" --version; } 2>/dev/null || true' \
        2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || true)"
if [ -n "${cur}" ] && awk -v v="${cur}" \
     'BEGIN{split(v,a,".");exit !(a[1]>1||(a[1]==1&&a[2]>=89))}'; then
  echo "  ✓ rust ${cur} already present for ${U} (>= 1.89)"
  exit 0
fi

if [ -n "${DRY_RUN}" ]; then
  echo "  dry-run: would install rustup (user-level) + the rust-toolchain.toml-pinned toolchain for ${U}"
  exit 0
fi

# ── install rustup (user-level) if absent, then materialise the pinned channel ──
if [ ! -x "${RUSTUP}" ]; then
  echo "  installing rustup for ${U} (apt ships 1.85 < 1.89; rustup honours rust-toolchain.toml)…"
  as_user bash -c 'curl --proto "=https" --tlsv1.2 -fsSL https://sh.rustup.rs \
                   | sh -s -- -y --profile minimal --no-modify-path'
fi
# `rustup show` in the repo reads rust-toolchain.toml and fetches the pinned channel
as_user bash -c "cd '${REPO}' && '${RUSTUP}' show >/dev/null"
echo "  ✓ rust ready for ${U}: $(as_user "${CARGO}" --version 2>/dev/null || echo 'pinned via rust-toolchain.toml')"
