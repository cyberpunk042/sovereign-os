#!/usr/bin/env bash
# scripts/install/install-gui-dashboards.sh — GUI desktop + dashboards, ON by default.
#
# Operator directive 2026-07-02 (verbatim):
#   "lets make with GUI by default when we install at the root of the machine,
#    I will keep Debian 13 GUI to explore the dashboards and lets make sure we
#    have them running by default and that I can easily find them on a fresh
#    install."
#
# This REVERSES the prior non-GUI-by-default stance (R225, scripts/dashboard/serve.py)
# specifically for the root-of-machine install. It:
#   1. installs a Debian 13 desktop environment (GNOME by default) + a browser
#   2. deploys the dashboard app tree to /usr/local/lib/sovereign-os
#   3. installs + enables the dashboard services so they run on boot (loopback)
#   4. drops a discoverable "Sovereign Dashboards" launcher into the app menu,
#      the desktop, and login autostart — so a fresh install lands you one click
#      from the hub at http://127.0.0.1:8100/
#
# Idempotent — re-running is safe. Runs both inside the install chroot (offline
# systemctl enable via wants-symlink) and on a live booted system.
#
# Tunable env:
#   SOVEREIGN_OS_SRC          repo source tree (default: two levels up from here)
#   SOVEREIGN_OS_LIB          deploy prefix   (default: /usr/local/lib/sovereign-os)
#   SOVEREIGN_OS_DESKTOP      gnome | minimal | none   (default: gnome)
#   SOVEREIGN_OS_DASHBOARD_PORT   hub port    (default: 8100)
set -euo pipefail

SRC="${SOVEREIGN_OS_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PREFIX_LIB="${SOVEREIGN_OS_LIB:-/usr/local/lib/sovereign-os}"
DESKTOP_ENV="${SOVEREIGN_OS_DESKTOP:-gnome}"
DASH_PORT="${SOVEREIGN_OS_DASHBOARD_PORT:-8100}"
SKEL="/etc/skel"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }
[ -d "${SRC}/webapp" ] || { red "ABORT: ${SRC}/webapp not found (set SOVEREIGN_OS_SRC)"; exit 1; }

# ── (1) desktop environment ──
step "1/5 desktop environment (${DESKTOP_ENV})"
if [ "${DESKTOP_ENV}" = none ]; then
  info "SOVEREIGN_OS_DESKTOP=none — skipping desktop install (headless dashboards only)"
else
  export DEBIAN_FRONTEND=noninteractive
  case "${DESKTOP_ENV}" in
    gnome)
      # gnome-core = a lean but complete GNOME (shell + gdm3 + settings). Swap
      # for task-gnome-desktop if you want the full default Debian app set.
      apt-get install -y --no-install-recommends gnome-core gdm3 firefox-esr xdg-utils
      ;;
    minimal)
      apt-get install -y --no-install-recommends xfce4 lightdm firefox-esr xdg-utils
      ;;
    *)
      red "ABORT: unknown SOVEREIGN_OS_DESKTOP='${DESKTOP_ENV}' (gnome|minimal|none)"; exit 1
      ;;
  esac
  # Boot into the GUI. In a chroot without systemd as PID 1 this is a no-op we
  # tolerate — the display-manager package already wires graphical.target.
  if systemctl set-default graphical.target 2>/dev/null; then
    info "default target → graphical.target"
  else
    info "set-default deferred (no running systemd); display manager still enabled by its package"
  fi
fi

# ── (2) deploy the dashboard app tree ──
# build-configurator-api.py resolves REPO = parents[2], so it must live at
# ${PREFIX_LIB}/scripts/operator/... and read ${PREFIX_LIB}/{webapp,profiles,config}.
step "2/5 deploy dashboard app tree → ${PREFIX_LIB}"
if [ -d "${SRC}/.git" ]; then
  # LIVE dev repo (has .git): symlink so an edit in the working tree is instantly
  # live and the deploy can't drift stale (matches provision-bake's image model).
  # A stale real-dir copy from an earlier `cp -a` install is replaced.
  [ -L "${PREFIX_LIB}" ] || { [ -e "${PREFIX_LIB}" ] && rm -rf "${PREFIX_LIB}"; }
  ln -sfn "${SRC}" "${PREFIX_LIB}"
  info "linked ${PREFIX_LIB} → ${SRC} (live repo — no drift)"
else
  # Staged/image source (no .git): self-contained copy.
  mkdir -p "${PREFIX_LIB}"
  for d in scripts webapp profiles config; do
    if [ -d "${SRC}/${d}" ]; then
      mkdir -p "${PREFIX_LIB}/${d}"
      cp -a "${SRC}/${d}/." "${PREFIX_LIB}/${d}/"
      info "deployed ${d}/"
    fi
  done
fi

# ── (3) install + enable the dashboard services ──
step "3/5 install + enable dashboard services (loopback)"
enable_unit() { # <unit> — enable via systemctl, else offline wants-symlink
  local unit="$1"
  install -m 644 "${SRC}/systemd/system/${unit}" /etc/systemd/system/
  if systemctl enable "${unit}" 2>/dev/null; then
    info "enabled ${unit}"
  else
    mkdir -p /etc/systemd/system/multi-user.target.wants
    ln -sf "/etc/systemd/system/${unit}" \
      "/etc/systemd/system/multi-user.target.wants/${unit}"
    info "enabled ${unit} (offline wants-symlink)"
  fi
}
enable_unit sovereign-dashboards.service
[ -f "${SRC}/systemd/system/sovereign-master-dashboard-api.service" ] \
  && enable_unit sovereign-master-dashboard-api.service
# R558 (SDD-070) — the science-tools panel API is read-only observability
# (catalog + NVIDIA Warp status; no privileged writes), so it is normally
# enabled like the mirror panels — NOT deploy-only like flash/emulate/ups.
[ -f "${SRC}/systemd/system/sovereign-science-api.service" ] \
  && enable_unit sovereign-science-api.service

# Deploy-ONLY (copy, do not enable) the execution-surface panels — flash +
# emulate. They carry the hardened posture for the lint, but their privileged
# actions (dd via pkexec · QEMU/KVM) do NOT work under the systemd sandbox;
# they are meant to be launched from the operator panel session, where
# scripts/operator/panel.sh runs the .py directly (no sandbox) and discovers
# the port from these unit files. Copying (not enabling) makes them
# discoverable without a half-working boot service.
deploy_unit_only() { # <unit> — install the file, never enable
  local unit="$1"
  [ -f "${SRC}/systemd/system/${unit}" ] || return 0
  install -m 644 "${SRC}/systemd/system/${unit}" /etc/systemd/system/
  info "deployed ${unit} (operator-launched via panel.sh — not auto-enabled)"
}
deploy_unit_only sovereign-flash-api.service
deploy_unit_only sovereign-emulate-api.service
deploy_unit_only sovereign-ups-api.service

# ── (4) discoverable launcher: app menu + desktop + login autostart ──
step "4/5 discoverable launcher (app menu · desktop · autostart)"
LAUNCHER="${SRC}/share/applications/sovereign-dashboards.desktop"
install -Dm644 "${LAUNCHER}" /usr/share/applications/sovereign-dashboards.desktop
info "app menu    : /usr/share/applications/sovereign-dashboards.desktop"
# every new user gets it auto-opened at login + an icon on the desktop
install -Dm644 "${LAUNCHER}" "${SKEL}/.config/autostart/sovereign-dashboards.desktop"
info "autostart   : ${SKEL}/.config/autostart/ (opens the hub at login)"
install -Dm755 "${LAUNCHER}" "${SKEL}/Desktop/sovereign-dashboards.desktop"
info "desktop icon: ${SKEL}/Desktop/"
# refresh the app-menu cache when running on a live system
command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

# ── (5) done ──
step "5/5 done"
grn "GUI + dashboards installed."
cat <<EOF

  Desktop     : ${DESKTOP_ENV} (boots to graphical.target)
  Dashboards  : running on boot, loopback only
  Entry point : http://127.0.0.1:${DASH_PORT}/   ← the hub (every panel + /panels/ index)
  Find it     : "Sovereign Dashboards" in the app menu, on the desktop,
                and auto-opened on first login.

  Expose beyond loopback (headless / LAN / tailscale) by dropping an override:
    /etc/systemd/system/sovereign-dashboards.service.d/bind.conf
      [Service]
      Environment=BUILD_CONFIGURATOR_API_BIND=0.0.0.0
EOF
