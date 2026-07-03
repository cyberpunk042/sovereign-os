#!/usr/bin/env bash
# scripts/install/dev-workstation.sh — the DEV WORKSTATION layer (NOT the
# OS build). Sets up the tools for WORKING ON the project: Node + the
# Claude Code CLI + the Claude VS Code extension + the ~/.claude env.
#
# This is deliberately separate from scripts/install/bootstrap-host.sh
# (the heavy toolchain that BUILDS the OS image — zfs/mkosi/qemu). You do
# NOT need this to build sovereign-os; it's operator convenience.
#
#   ⚡ YOU RUN (as your normal user — NOT root):
#       scripts/install/dev-workstation.sh          (or: make dev-setup)
#
# Privilege split (handled automatically, even if invoked via sudo):
#   root  → apt (node) · npm -g (system-global claude-code)
#   USER  → code --install-extension · ~/.claude   (must NOT be root)
#
# Tunable env:
#   DEV_DRY_RUN=1                 preview, change nothing
#   DEV_VSCODE_EXTENSION=<id>     default anthropic.claude-code
#   DEV_MIN_NODE=<major>          default 22 (claude-code's floor)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

DRY_RUN="${DEV_DRY_RUN:-}"
EXT="${DEV_VSCODE_EXTENSION:-anthropic.claude-code}"
MIN_NODE="${DEV_MIN_NODE:-22}"
for a in "$@"; do case "$a" in --dry-run) DRY_RUN=1 ;; -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac; done

bold='\033[1m'; grn='\033[32m'; ylw='\033[33m'; red='\033[31m'; cyn='\033[36m'; rst='\033[0m'
ok()   { echo -e "  ${grn}✓${rst} $*"; }
warn() { echo -e "  ${ylw}!${rst} $*"; }

# ── figure out the target (non-root) user for user-level installs ──
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
  TARGET_USER="${SUDO_USER}"
elif [ "$(id -u)" -ne 0 ]; then
  TARGET_USER="$(id -un)"
else
  echo -e "${red}Run dev-setup as your normal user, not root.${rst}"
  echo "  The VS Code extension + ~/.claude are user-level; only node-install needs root,"
  echo "  and the script elevates that step itself."
  echo "  e.g.:   su - <you> -c 'cd ${__REPO_ROOT} && make dev-setup'"
  exit 2
fi

as_user() {  # run as TARGET_USER (drop from root when needed)
  if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyn}dry-run[${TARGET_USER}]\$${rst} $*"; return 0; fi
  if [ "$(id -u)" -eq 0 ] && [ "${TARGET_USER}" != "root" ]; then sudo -u "${TARGET_USER}" -H "$@"; else "$@"; fi
}
as_root() {  # run as root (elevate when needed)
  if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyn}dry-run[root]\$${rst} $*"; return 0; fi
  if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }

echo -e "${bold}sovereign-os · dev workstation${rst}  (target user: ${TARGET_USER})${DRY_RUN:+  ${ylw}(dry-run)${rst}}"

# ── (1) node + npm, at the version claude-code needs ─────────────────
echo -e "\n${bold}[1/4] node ≥ ${MIN_NODE}${rst}"
node_major=0
have node && node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "${node_major}" -ge "${MIN_NODE}" ] 2>/dev/null; then
  ok "node $(node --version) · npm $(npm --version 2>/dev/null)"
else
  if [ "${node_major}" -eq 0 ]; then
    warn "node absent — installing Debian's nodejs (root)"
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs npm
    have node && node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  fi
  if [ "${node_major}" -lt "${MIN_NODE}" ] 2>/dev/null; then
    warn "node v${node_major} < ${MIN_NODE} — claude-code needs ≥${MIN_NODE}. Debian ships an older node."
    warn "  Upgrade path (pick one), then re-run dev-setup:"
    warn "    • NodeSource:  curl -fsSL https://deb.nodesource.com/setup_${MIN_NODE}.x | sudo -E bash - && sudo apt-get install -y nodejs"
    warn "    • nvm (per-user, no root):  nvm install ${MIN_NODE} && nvm use ${MIN_NODE}"
    warn "  Continuing — claude-code will install but may warn/misbehave on node v${node_major}."
  fi
fi

# ── (2) Claude Code CLI (system-global npm) ──────────────────────────
echo -e "\n${bold}[2/4] Claude Code CLI${rst}"
if have claude || have claude-code; then
  ok "claude-code already installed ($(command -v claude claude-code 2>/dev/null | head -1))"
elif have npm || [ -n "${DRY_RUN}" ]; then
  as_root npm install -g @anthropic-ai/claude-code
else
  warn "npm missing — resolve step 1 first"
fi

# ── (3) Claude VS Code extension — as the USER (not root) ────────────
echo -e "\n${bold}[3/4] Claude VS Code extension${rst}  (${EXT})"
if as_user bash -c 'command -v code >/dev/null 2>&1'; then
  if [ -z "${DRY_RUN}" ] && as_user code --list-extensions 2>/dev/null | grep -qix "${EXT}"; then
    ok "${EXT} already installed"
  else
    as_user code --install-extension "${EXT}" --force
  fi
else
  warn "VS Code ('code') not on ${TARGET_USER}'s PATH — GUI extension skipped"
fi

# ── (4) ~/.claude environment — as the USER (writes to their HOME) ───
echo -e "\n${bold}[4/4] ~/.claude environment${rst}"
apply="${__REPO_ROOT}/scripts/claude-code-env/apply.sh"
if [ -x "${apply}" ]; then
  as_user "${apply}"
else
  warn "scripts/claude-code-env/apply.sh not found — skipping"
fi

echo -e "\n${bold}dev workstation ${DRY_RUN:+dry-run }ready${rst}"
echo -e "  This is the DEV layer — separate from ${cyn}make bootstrap${rst} (the OS-build toolchain)."
