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

# A service with ProtectHome=true cannot follow a live link into /home: systemd
# masks the source path in the service's mount namespace, then its ExecStart
# fails before Python runs.  Keep the rest of /home private and bind only this
# explicitly selected checkout read-only into every installed operator-panel
# service that resolves code under ${LIB}.  This makes the live link genuinely
# live while preserving the R171 hardening boundary.
_grant_service_source_access() {
  local src="$1" unit_file unit dropin seen_units=" "
  case "${src}" in
    /home/*) ;;
    *) return 0 ;;  # /opt and other non-home live trees need no exception.
  esac
  case "${src}" in
    *$'\n'*|*' '*)
      echo "refusing a live source path with whitespace/newlines: ${src}" >&2
      return 2
      ;;
  esac
  # Packaged units live in /usr/lib/systemd/system while local overrides often
  # live in /etc/systemd/system.  Inspect both: the control-exec API is a
  # packaged unit and must refresh with the same live source as D-21.
  for unit_file in /etc/systemd/system/sovereign-*.service /usr/lib/systemd/system/sovereign-*.service; do
    [ -f "${unit_file}" ] || continue
    grep -q '/usr/local/lib/sovereign-os/' "${unit_file}" || continue
    unit="$(basename "${unit_file}")"
    # A unit can have both its packaged definition and an /etc override; one
    # generated drop-in is enough.
    [[ "${seen_units}" == *" ${unit} "* ]] && continue
    seen_units+="${unit} "
    dropin="/etc/systemd/system/${unit}.d/dev-source.conf"
    if [ -n "${DRY}" ]; then
      info "dry-run: grant ${unit} read-only access to ${src}"
      continue
    fi
    _sudo mkdir -p "$(dirname "${dropin}")"
    printf '[Service]\nProtectHome=tmpfs\nBindReadOnlyPaths=%s\n' "${src}" \
      | _sudo tee "${dropin}" >/dev/null
    info "live-source access: ${unit} → ${src} (read-only)"
  done
  if [ -z "${DRY}" ]; then
    _sudo systemctl daemon-reload
    # The broker must see the new checkout to emit refresh notices, and panel
    # APIs already running retain their imported repository root until a
    # restart. Refresh every live-link owner needed for D-21: its read API,
    # update broker, and sanctioned write endpoint.
    for unit in sovereign-livereload-broker.service sovereign-lm-orchestration-api.service sovereign-control-exec-api.service; do
      if systemctl is-active --quiet "${unit}"; then
        _sudo systemctl try-restart "${unit}"
        info "restarted ${unit} to adopt the live checkout"
      fi
    done
  fi
}

_grant_service_source_access "${SRC}"

[ -n "${DRY}" ] || info "operator CLI + lib are now live-linked to ${SRC}"
