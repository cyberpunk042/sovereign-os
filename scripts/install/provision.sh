#!/usr/bin/env bash
# scripts/install/provision.sh — ONE idempotent, resumable command that
# completes the workstation setup. This is what "resume setup after a flash"
# means: run it (or let firstboot run it) and the box provisions itself —
# build-host toolchain, dev tools, and selfdef built+installed+enabled with
# NO manual `make -C selfdef build`.
#
#   ⚡ YOU RUN:   scripts/install/provision.sh          (or: make provision)
#               scripts/install/provision.sh --dry-run  (preview, no changes)
#
# Safe to re-run: each step is idempotent and self-skips when already done,
# so an interrupted provision resumes cleanly from where it stopped.
#
# Steps:
#   1. host bootstrap   apt components + build-host toolchain  (bootstrap-host.sh)
#   2. dev workstation  node22 + Claude Code + VS Code ext     (dev-workstation.sh)
#   3. selfdef          build + install units + enable         (auto — no manual compile)
#   4. operator-deps    declared apt/pip/npm overlay           (operator-deps.py)
#   5. operator-rules   re-apply Claude Code interaction rules (operator-rules.py)
#   6. root-ghostproxy  OPTIONAL agent-safety env — endpoint mode, NO proxy (opt-out)
#
# Tunable env:
#   PROVISION_DRY_RUN=1              preview
#   PROVISION_SKIP="build,dev,selfdef,deps,rules,ghostproxy"  comma-list to skip
#   PROVISION_GHOSTPROXY=0           opt OUT of the default-on root-ghostproxy step
#   SOVEREIGN_OS_SELFDEF_DIR=<path>     selfdef checkout (default ~/selfdef)
#   SOVEREIGN_OS_GHOSTPROXY_DIR=<path>  root-ghostproxy checkout (default ~/root-ghostproxy)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
cd "${__REPO_ROOT}"

DRY_RUN="${PROVISION_DRY_RUN:-}"
SKIP="${PROVISION_SKIP:-}"
: "${SOVEREIGN_OS_SELFDEF_DIR:=${HOME}/selfdef}"
MARKER_DIR="${HOME}/.sovereign-os"
for a in "$@"; do case "$a" in --dry-run) DRY_RUN=1 ;; -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac; done

bold='\033[1m'; grn='\033[32m'; ylw='\033[33m'; cyn='\033[36m'; rst='\033[0m'
step() { echo -e "\n${bold}$*${rst}"; }
ok()   { echo -e "  ${grn}✓${rst} $*"; }
warn() { echo -e "  ${ylw}!${rst} $*"; }
run()  { if [ -n "${DRY_RUN}" ]; then echo -e "  ${cyn}dry-run\$${rst} $*"; else eval "$*"; fi; }
skipped() { case ",${SKIP}," in *,"$1",*) return 0 ;; *) return 1 ;; esac; }
sudo_() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }
# Run as the operator (NOT root) — ~/.claude is user-level. If provision was
# invoked via sudo, drop back to $SUDO_USER so rules land in the operator's
# home, never /root (mirrors dev-workstation.sh's as_user).
as_user_() {
  if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
    sudo -u "${SUDO_USER}" "$@"
  else
    "$@"
  fi
}

echo -e "${bold}sovereign-os · provision (resume setup)${rst}${DRY_RUN:+  ${ylw}(dry-run)${rst}}"
[ -n "${DRY_RUN}" ] || mkdir -p "${MARKER_DIR}"

# ── (1) host bootstrap: build-host toolchain + apt components ─────────
step "[1/6] host bootstrap (build-host toolchain)"
if skipped build; then warn "skipped (PROVISION_SKIP)"
elif command -v mkosi >/dev/null 2>&1 && command -v zpool >/dev/null 2>&1; then
  ok "build-host toolchain already present"
else
  run "scripts/install/bootstrap-host.sh${DRY_RUN:+ --dry-run}"
fi

# ── (2) dev workstation: node + Claude Code + VS Code extension ───────
step "[2/6] dev workstation (node + Claude Code + editor)"
if skipped dev; then warn "skipped (PROVISION_SKIP)"
else run "scripts/install/dev-workstation.sh${DRY_RUN:+ --dry-run}"; fi

# ── (3) selfdef: build + install units + enable (NO manual compile) ──
step "[3/6] selfdef (build · install · enable)"
if skipped selfdef; then warn "skipped (PROVISION_SKIP)"
elif [ ! -d "${SOVEREIGN_OS_SELFDEF_DIR}/.git" ]; then
  warn "no selfdef checkout at ${SOVEREIGN_OS_SELFDEF_DIR} — skipping (set SOVEREIGN_OS_SELFDEF_DIR)"
else
  if command -v cargo >/dev/null 2>&1 || [ -n "${DRY_RUN}" ]; then
    run "make -C '${SOVEREIGN_OS_SELFDEF_DIR}' build"
  else
    warn "cargo absent — installing rust (rustup, user-level) to build selfdef"
    run "curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal"
    # shellcheck disable=SC1091
    [ -n "${DRY_RUN}" ] || . "${HOME}/.cargo/env" 2>/dev/null || true
    run "make -C '${SOVEREIGN_OS_SELFDEF_DIR}' build"
  fi
  run "sudo_ sovereign-osctl selfdef install-units"
  run "sudo_ sovereign-osctl selfdef on"
fi

# ── (4) operator-deps overlay (declared apt/pip/npm) ─────────────────
step "[4/6] operator deps (apt/pip/npm overlay)"
if skipped deps; then warn "skipped (PROVISION_SKIP)"
else
  deps="/etc/sovereign-os/operator-deps.toml"
  [ -f "${deps}" ] || deps="${__REPO_ROOT}/config/operator-deps.toml.example"
  if [ -n "${DRY_RUN}" ]; then
    echo -e "  ${cyn}dry-run\$${rst} python3 scripts/install/operator-deps.py --deps ${deps} --apply --confirm"
  else
    python3 scripts/install/operator-deps.py --deps "${deps}" --apply --confirm \
      || warn "operator-deps returned non-zero (non-fatal; re-runnable)"
  fi
fi

# ── (5) operator rules: re-apply Claude Code interaction rules ───────
# The operator's behaviour rules live in per-project Claude memory, which a
# fresh flash wipes. Re-apply them from the versioned store (self-contained —
# NO dependency on root-ghostproxy). Idempotent; runs as the operator so the
# rules land in the operator's ~/.claude, never /root.
step "[5/6] operator rules (Claude Code interaction rules → ~/.claude memory)"
if skipped rules; then warn "skipped (PROVISION_SKIP)"
elif [ -n "${DRY_RUN}" ]; then
  echo -e "  ${cyn}dry-run\$${rst} python3 scripts/operator/operator-rules.py apply  (as ${SUDO_USER:-$(id -un)})"
else
  as_user_ python3 scripts/operator/operator-rules.py apply \
    || warn "operator-rules apply returned non-zero (non-fatal; re-runnable)"
fi

# ── (6) root-ghostproxy: OPTIONAL agent-safety env (endpoint, NO proxy) ─
# Complementary AI-agent safety at ~/.claude (settings/hooks/rules). We install
# it in ENDPOINT mode with --no-bridge --no-wifi so NONE of the L2 bridge /
# Suricata / PolarProxy proxy half comes along. Default-selected but fully
# opt-out (PROVISION_GHOSTPROXY=0), and skipped silently if not checked out —
# everything works fine without it. Disjoint from our rules (it owns ~/.claude
# global config; we own ~/.claude/projects/<project>/memory) so no collision.
step "[6/6] root-ghostproxy (optional — endpoint mode, NO proxy)"
GHOSTPROXY_DIR="${SOVEREIGN_OS_GHOSTPROXY_DIR:-${HOME}/root-ghostproxy}"
if skipped ghostproxy; then warn "skipped (PROVISION_SKIP)"
elif [ "${PROVISION_GHOSTPROXY:-1}" != "1" ]; then warn "opt-out (PROVISION_GHOSTPROXY=0)"
elif [ ! -x "${GHOSTPROXY_DIR}/install.sh" ]; then
  warn "no root-ghostproxy checkout at ${GHOSTPROXY_DIR} — skipping (optional; not required)"
elif [ -n "${DRY_RUN}" ]; then
  echo -e "  ${cyn}dry-run\$${rst} ${GHOSTPROXY_DIR}/install.sh --mode endpoint --no-bridge --no-wifi  (as ${SUDO_USER:-$(id -un)})"
else
  as_user_ "${GHOSTPROXY_DIR}/install.sh" --mode endpoint --no-bridge --no-wifi \
    || warn "root-ghostproxy endpoint install returned non-zero (non-fatal; optional)"
fi

# ── done ─────────────────────────────────────────────────────────────
if [ -z "${DRY_RUN}" ]; then
  date -u --iso-8601=seconds > "${MARKER_DIR}/provision-complete" 2>/dev/null || true
fi
step "provision ${DRY_RUN:+dry-run }complete"
echo -e "  verify:  ${cyn}sovereign-osctl doctor${rst} · ${cyn}sovereign-osctl selfdef status${rst}"
