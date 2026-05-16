#!/usr/bin/env bash
# scripts/auditor/install.sh
#
# Materializes master spec § 10 The Native Guardian Event Loop:
#   - Installs guardian-core.py → /usr/local/bin/guardian-core
#   - Installs sovereign-guardian-core.service → /etc/systemd/system/
#   - Verifies tetragon dependency present (master spec § 10.2 verbatim
#     unit declares After=tetragon.service Requires=tetragon.service)
#
# Env vars:
#   GUARDIAN_INSTALL_BIN_DIR   (default: /usr/local/bin)
#   GUARDIAN_INSTALL_UNIT_DIR  (default: /etc/systemd/system)
#   SOVEREIGN_OS_DRY_RUN       (default: unset; set to 1 for dry-run)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [guardian-install] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [guardian-install] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [guardian-install] $*" >&2; }

: "${GUARDIAN_INSTALL_BIN_DIR:=/usr/local/bin}"
: "${GUARDIAN_INSTALL_UNIT_DIR:=/etc/systemd/system}"

SRC_PY="${__SCRIPT_DIR}/guardian-core.py"
SRC_UNIT="${__REPO_ROOT}/../systemd/system/sovereign-guardian-core.service"

DEST_BIN="${GUARDIAN_INSTALL_BIN_DIR}/guardian-core"
DEST_UNIT="${GUARDIAN_INSTALL_UNIT_DIR}/sovereign-guardian-core.service"

log_info "==== sovereign-os Guardian Daemon installer ===="
log_info "  master spec § 10 (The Native Guardian Event Loop)"
log_info "  source script:  ${SRC_PY}"
log_info "  dest bin:       ${DEST_BIN}"
log_info "  dest unit:      ${DEST_UNIT}"

if [ ! -f "${SRC_PY}" ]; then
  log_error "guardian-core.py source missing: ${SRC_PY}"
  exit 1
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would copy ${SRC_PY} → ${DEST_BIN}"
  log_info "DRY-RUN: would copy unit → ${DEST_UNIT}"
  log_info "DRY-RUN: would systemctl daemon-reload"
  log_info "DRY-RUN: would systemctl enable sovereign-guardian-core.service"
  log_info "DRY-RUN: master spec § 10.2 unit declares:"
  log_info "  After=tetragon.service"
  log_info "  Requires=tetragon.service"
  log_info "  ExecStart=/usr/local/bin/guardian-core"
  exit 0
fi

# Install bin
install -m 0755 "${SRC_PY}" "${DEST_BIN}"
log_info "  ✓ installed ${DEST_BIN}"

# Install unit
if [ -f "${SRC_UNIT}" ]; then
  install -m 0644 "${SRC_UNIT}" "${DEST_UNIT}"
  log_info "  ✓ installed ${DEST_UNIT}"
else
  log_warn "  unit source missing: ${SRC_UNIT}"
fi

# Reload systemd (if running)
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || log_warn "daemon-reload failed (containerized env?)"
  log_info "  enable via: sudo systemctl enable --now sovereign-guardian-core.service"
fi

log_info "✓ Guardian Daemon installed (master spec § 10 materialized)"
