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
#   5. ups / power      APC Smart-UPS via NUT apc_modbus        (ups-apc-setup.sh)
#   6. operator-rules   re-apply Claude Code interaction rules (operator-rules.py)
#   7. root-ghostproxy  OPTIONAL agent-safety env — endpoint mode, NO proxy (opt-out)
#
# Tunable env:
#   PROVISION_DRY_RUN=1              preview
#   PROVISION_SKIP="build,dev,selfdef,deps,ups,rules,ghostproxy"  comma-list to skip
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
step "[1/6] host bootstrap (build-host toolchain + operator CLI link)"
if skipped build; then warn "skipped (PROVISION_SKIP)"
elif command -v mkosi >/dev/null 2>&1 && command -v zpool >/dev/null 2>&1; then
  ok "build-host toolchain already present"
else
  run "scripts/install/bootstrap-host.sh${DRY_RUN:+ --dry-run}"
fi
# ALWAYS keep the operator CLI (`sovereign-osctl` on PATH) + deployed lib
# live-linked to this working tree, so an edit here is instantly live and a stale
# `make install` copy can't drift (the power-shutdown "schedule-manifest.py: No
# such file" bug). Idempotent; runs even when `build` is skipped.
run "scripts/install/link-operator-cli.sh"

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
  # operator-deps.py CLI: `--config <file> apply --confirm` (verb-based); it
  # shells `apt-get install` directly so it needs root → run via sudo_.
  if [ -n "${DRY_RUN}" ]; then
    python3 scripts/install/operator-deps.py --config "${deps}" plan || true
  else
    sudo_ python3 scripts/install/operator-deps.py --config "${deps}" apply --confirm \
      || warn "operator-deps returned non-zero (non-fatal; re-runnable)"
  fi
fi

# ── (5) UPS / power (APC Smart-UPS via NUT apc_modbus + graceful shutdown) ──
# Running-host parity with provision-bake §7: (a) ARM the graceful soft-shutdown
# guard in power.toml from the active profile's provisioning.power block, (b)
# install + enable the shutdown-guard timer (its /opt/sovereign-os unit paths
# resolve here via the /opt → repo symlink), (c) AUTO-DETECT the APC transport
# (Modbus TCP :502 → serial → USB-HID) + enable the NUT daemons. Idempotent; a
# no-op if NUT/UPS absent. Needs root. NUT comes from the step-4 overlay
# (nut-server + nut-client + nut-modbus — the apc_modbus driver Debian splits out).
step "[5/7] UPS / power (APC Smart-UPS — NUT apc_modbus + graceful shutdown)"
UPS_HOOK="${__REPO_ROOT}/scripts/hooks/post-install/ups-apc-setup.sh"
if skipped ups; then warn "skipped (PROVISION_SKIP)"
elif [ ! -x "${UPS_HOOK}" ]; then warn "ups-apc-setup hook not present — skipping"
elif [ -z "${DRY_RUN}" ] && ! command -v upsc >/dev/null 2>&1; then
  warn "NUT not installed (add nut-server + nut-client + nut-modbus to operator-deps.toml) — skipping"
else
  # graceful-shutdown policy from the active profile's provisioning.power block
  # (master toggle enabled · arm · shutdown_minutes · warn_lead_minutes)
  ups_prof="${SOVEREIGN_OS_PROFILE:-sain-01}"
  ups_pol="$(python3 -c "
import yaml
try: p=(yaml.safe_load(open('profiles/${ups_prof}.yaml')).get('provisioning') or {}).get('power') or {}
except Exception: p={}
print(1 if p.get('enabled', True) else 0, 1 if p.get('graceful_shutdown') else 0, int(p.get('shutdown_minutes',30)), int(p.get('warn_lead_minutes',15)))" 2>/dev/null || echo '1 1 30 15')"
  read -r ups_on ups_arm ups_min ups_lead <<< "${ups_pol}"
  if [ "${ups_on}" != "1" ]; then
    warn "provisioning.power.enabled=false in ${ups_prof} — UPS + graceful shutdown NOT provisioned"
  elif [ -n "${DRY_RUN}" ]; then
    echo -e "  ${cyn}dry-run\$${rst} arm power.toml (enabled=${ups_arm}, shutdown=${ups_min}m, warn_lead=${ups_lead}m) · install manifest + guard timer · run detection"
  else
    # (a) arm the graceful-shutdown guard (power.toml) — mirrors provision-bake §7a
    sudo_ mkdir -p /etc/sovereign-os
    [ -f /etc/sovereign-os/power.toml ] || sudo_ cp "${__REPO_ROOT}/config/power.toml.example" /etc/sovereign-os/power.toml
    if [ "${ups_arm}" = "1" ]; then
      sudo_ sed -i -E 's|^[#[:space:]]*enabled[[:space:]]*=.*|enabled = true|' /etc/sovereign-os/power.toml
    fi
    sudo_ sed -i -E "s|^[#[:space:]]*shutdown_minutes[[:space:]]*=.*|shutdown_minutes = ${ups_min}|" /etc/sovereign-os/power.toml
    sudo_ sed -i -E "s|^[#[:space:]]*warn_lead_minutes[[:space:]]*=.*|warn_lead_minutes = ${ups_lead}|" /etc/sovereign-os/power.toml
    # (b) install the staged soft-exit manifest (announce→drain→unload→stop→poweroff)
    [ -f /etc/sovereign-os/shutdown-manifest.toml ] || \
      sudo_ cp "${__REPO_ROOT}/config/shutdown-manifest.toml.example" /etc/sovereign-os/shutdown-manifest.toml 2>/dev/null || true
    # (c) install + enable the shutdown-guard timer (the trigger)
    for f in sovereign-power-shutdown-guard.service sovereign-power-shutdown-guard.timer; do
      [ -f "${__REPO_ROOT}/systemd/system/${f}" ] && sudo_ install -m 644 "${__REPO_ROOT}/systemd/system/${f}" /etc/systemd/system/
    done
    sudo_ systemctl daemon-reload 2>/dev/null || true
    if [ "${ups_arm}" = "1" ]; then
      sudo_ systemctl enable --now sovereign-power-shutdown-guard.timer 2>/dev/null \
        || warn "could not enable power-shutdown-guard.timer (non-fatal)"
    fi
    # (d) detect + configure the UPS transport, enable the NUT daemons
    sudo_ bash "${UPS_HOOK}" || warn "ups-apc-setup returned non-zero (non-fatal; re-runnable)"
    ok "graceful soft-exit armed=${ups_arm} (shutdown <${ups_min}m, warn ${ups_lead}m ahead); manifest + guard timer installed"
  fi
fi

# ── (6) operator rules: re-apply Claude Code interaction rules ───────
# The operator's behaviour rules live in per-project Claude memory, which a
# fresh flash wipes. Re-apply them from the versioned store (self-contained —
# NO dependency on root-ghostproxy). Idempotent; runs as the operator so the
# rules land in the operator's ~/.claude, never /root.
step "[6/7] operator rules (Claude Code interaction rules → ~/.claude memory)"
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
step "[7/7] root-ghostproxy (optional — endpoint mode, NO proxy)"
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
