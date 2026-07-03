#!/usr/bin/env bash
# scripts/install/dev-workstation.sh — set up the Dev workstation layer:
# Node + Claude Code (CLI) + the Claude VS Code extension + the ~/.claude
# environment. GUI-aware (only touches VS Code when `code` is present).
# Idempotent, re-runnable; --dry-run previews and changes nothing.
#
#   ⚡ YOU RUN:   scripts/install/dev-workstation.sh   (or: make dev-setup)
#
# What it ensures, in order:
#   1. node + npm            (apt via the host bootstrap; self-sudo)
#   2. @anthropic-ai/claude-code  (npm global — the Claude Code CLI)
#   3. Claude VS Code extension   (code --install-extension; GUI only —
#                                  skipped cleanly if `code` is absent)
#   4. ~/.claude environment      (scripts/claude-code-env/apply.sh)
#
# The heavy build-host toolchain (zfs/mkosi/qemu/…) is a DIFFERENT layer —
# see scripts/install/bootstrap-host.sh. This one is the dev surface only.
#
# Tunable env:
#   DEV_DRY_RUN=1                 same as --dry-run
#   DEV_VSCODE_EXTENSION=<id>     override (default anthropic.claude-code)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

DRY_RUN="${DEV_DRY_RUN:-}"
EXT="${DEV_VSCODE_EXTENSION:-anthropic.claude-code}"
for a in "$@"; do case "$a" in --dry-run) DRY_RUN=1 ;; -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac; done

bold='\033[1m'; grn='\033[32m'; ylw='\033[33m'; cyn='\033[36m'; rst='\033[0m'
ok()   { echo -e "  ${grn}✓${rst} $*"; }
warn() { echo -e "  ${ylw}!${rst} $*"; }
run()  { if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyn}dry-run\$${rst} $*"; else eval "$*"; fi; }

echo -e "${bold}sovereign-os · dev workstation${rst}${DRY_RUN:+  ${ylw}(dry-run)${rst}}"

# ── (1) node + npm ───────────────────────────────────────────────────
echo -e "\n${bold}[1/4] node + npm${rst}"
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  ok "node $(node --version 2>/dev/null) · npm $(npm --version 2>/dev/null)"
else
  warn "node/npm absent — installing via apt (needs root)"
  if [ -n "${DRY_RUN}" ]; then
    echo -e "  ${cyn}dry-run\$${rst} sudo apt-get install -y nodejs npm"
  else
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm
  fi
fi

# ── (2) Claude Code CLI (npm global) ─────────────────────────────────
echo -e "\n${bold}[2/4] Claude Code CLI${rst}"
if command -v claude >/dev/null 2>&1 || command -v claude-code >/dev/null 2>&1; then
  ok "claude-code already installed"
elif command -v npm >/dev/null 2>&1 || [ -n "${DRY_RUN}" ]; then
  run "npm install -g @anthropic-ai/claude-code"
else
  warn "npm missing — rerun after step 1 installs node"
fi

# ── (3) Claude VS Code extension (GUI only) ──────────────────────────
echo -e "\n${bold}[3/4] Claude VS Code extension${rst}  (${EXT})"
if command -v code >/dev/null 2>&1; then
  if [ -z "${DRY_RUN}" ] && code --list-extensions 2>/dev/null | grep -qix "${EXT}"; then
    ok "${EXT} already installed"
  else
    run "code --install-extension '${EXT}' --force"
  fi
else
  warn "VS Code ('code') not on PATH — GUI extension skipped (install VS Code first)"
fi

# ── (4) ~/.claude environment ────────────────────────────────────────
echo -e "\n${bold}[4/4] ~/.claude environment${rst}"
apply="${__REPO_ROOT}/scripts/claude-code-env/apply.sh"
if [ -x "${apply}" ]; then
  if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyn}dry-run\$${rst} ${apply}"; else "${apply}"; fi
else
  warn "scripts/claude-code-env/apply.sh not found — skipping ~/.claude setup"
fi

echo -e "\n${bold}dev workstation ${DRY_RUN:+dry-run }ready${rst}"
echo -e "  selfdef management:  ${cyn}sovereign-osctl selfdef status${rst}"
echo -e "  build-host toolchain: ${cyn}scripts/install/bootstrap-host.sh${rst}"
