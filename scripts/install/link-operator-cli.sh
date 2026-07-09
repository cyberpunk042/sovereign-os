#!/usr/bin/env bash
# scripts/install/link-operator-cli.sh — keep the operator CLI + deployed lib
# LIVE-LINKED to the working tree so `sovereign-osctl` on PATH always reflects
# the current code (no drifting `make install` copy).
#
# The bug this fixes (2026-07-08): `make install` copied sovereign-osctl to
# /usr/local/bin and the tree to /usr/local/lib/sovereign-os. On a dev host the
# repo keeps changing, so that copy silently went a month stale — `sovereign-osctl
# power-shutdown` failed with "schedule-manifest.py: No such file or directory"
# because the deployed copy predated the file. On a persistent-repo host the
# right model is a SYMLINK (what provision-bake already does for the image), so
# an edit in the repo is instantly live everywhere.
#
# Idempotent. Needs root for /usr/local (self-elevates via sudo). Safe: only
# symlinks when the source is a live tree (has scripts/); never touches a
# genuine self-contained install that isn't backed by a repo.
set -euo pipefail

SRC="${SOVEREIGN_OS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BIN="${SOVEREIGN_OS_BINDIR:-/usr/local/bin}/sovereign-osctl"
LIB="${SOVEREIGN_OS_LIB:-/usr/local/lib/sovereign-os}"
DRY="${SOVEREIGN_OS_DRY_RUN:-}"

_sudo() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }
info() { printf '  %s\n' "$*"; }

[ -d "${SRC}/scripts" ] || { echo "not a live tree (${SRC}/scripts absent) — leaving install as-is"; exit 0; }

_relink() {  # <target> <link>  — replace whatever is at <link> with a symlink
  local target="$1" link="$2"
  if [ -L "${link}" ] && [ "$(readlink -f "${link}")" = "$(readlink -f "${target}")" ]; then
    info "ok  ${link} → ${target} (already linked)"; return 0
  fi
  if [ -n "${DRY}" ]; then info "dry-run: link ${link} → ${target}"; return 0; fi
  # a real dir/file (stale copy) must be removed before we can symlink over it
  if [ -e "${link}" ] && [ ! -L "${link}" ]; then _sudo rm -rf "${link}"; fi
  _sudo mkdir -p "$(dirname "${link}")"
  _sudo ln -sfn "${target}" "${link}"
  info "linked ${link} → ${target}"
}

# CLI entrypoint → the repo's osctl (which is symlink-aware, so it self-resolves
# __REPO_ROOT to the real working tree).
_relink "${SRC}/scripts/sovereign-osctl" "${BIN}"
# Deployed lib tree → the repo (the dashboards resolve REPO from here).
_relink "${SRC}" "${LIB}"

[ -n "${DRY}" ] || info "operator CLI + lib are now live-linked to ${SRC}"
