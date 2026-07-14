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

# SDD-704 swappable frontend selector. FRONTEND = what the box PRESENTS at boot
# (gnome | dashboards-kiosk | open-computer-kiosk | none); FRONTEND_INSTALL =
# which stacks to STAGE so `sovereign-osctl frontend set <value>` can switch live.
# Back-compat: if SOVEREIGN_OS_FRONTEND is unset, derive from the legacy
# SOVEREIGN_OS_DESKTOP (none→none, else gnome) so pre-SDD-704 callers are unchanged.
FRONTEND="${SOVEREIGN_OS_FRONTEND:-}"
if [ -z "${FRONTEND}" ]; then
  case "${DESKTOP_ENV}" in none) FRONTEND=none ;; *) FRONTEND=gnome ;; esac
fi
FRONTEND_INSTALL="${SOVEREIGN_OS_FRONTEND_INSTALL:-${FRONTEND}}"
# The dashboards-kiosk points here; open-computer-kiosk overrides it to the sandbox UI.
FRONTEND_KIOSK_URL="${SOVEREIGN_OS_FRONTEND_KIOSK_URL:-http://127.0.0.1:${DASH_PORT}/}"
KIOSK_ENV_FILE="/etc/sovereign-os/frontend-kiosk.env"
KIOSK_UNIT_SRC="${SRC}/systemd/system/sovereign-frontend-kiosk.service"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }
[ -d "${SRC}/webapp" ] || { red "ABORT: ${SRC}/webapp not found (set SOVEREIGN_OS_SRC)"; exit 1; }

# ── (1) frontend: stage each requested stack, then activate the default ──
# SDD-704: two concerns kept distinct — INSTALL the stacks in FRONTEND_INSTALL so a
# later live switch works, then ACTIVATE the FRONTEND default (target + which units
# are enabled). Every apt/systemctl step is best-effort so a hiccup never bricks the
# build (the image just lands headless or on a partial frontend, recoverable post-flash).
export DEBIAN_FRONTEND=noninteractive
step "1/5 frontend stacks (install: ${FRONTEND_INSTALL} · default: ${FRONTEND})"

install_gnome_de() {
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
      red "unknown SOVEREIGN_OS_DESKTOP='${DESKTOP_ENV}' (gnome|minimal) — defaulting to gnome-core"
      apt-get install -y --no-install-recommends gnome-core gdm3 firefox-esr xdg-utils
      ;;
  esac
}

install_kiosk_stack() {
  # A kiosk = a minimal Wayland compositor (cage) + a browser, launched fullscreen
  # at a URL by sovereign-frontend-kiosk.service. No full desktop shell. seatd gives
  # the compositor seat/DRM access without a login manager. Non-fatal — if cage isn't
  # available the unit still installs (disabled) and the operator can install it later.
  apt-get install -y --no-install-recommends cage seatd firefox-esr xdg-utils || \
    info "kiosk stack apt hiccup (cage/seatd) — unit still staged; install post-flash"
  systemctl enable seatd.service 2>/dev/null || true
  # Stage the kiosk unit (DISABLED — the default-activation step below enables it
  # only when a kiosk frontend is the chosen default).
  if [ -f "${KIOSK_UNIT_SRC}" ]; then
    install -Dm644 "${KIOSK_UNIT_SRC}" /etc/systemd/system/sovereign-frontend-kiosk.service
    info "kiosk unit staged: /etc/systemd/system/sovereign-frontend-kiosk.service (disabled until selected)"
  else
    info "kiosk unit source not found at ${KIOSK_UNIT_SRC} (staged separately)"
  fi
}

write_kiosk_env() {
  # The kiosk unit reads FRONTEND_KIOSK_URL from here; the runtime switch
  # (sovereign-osctl frontend set) rewrites it without touching the unit.
  install -d -m 755 /etc/sovereign-os
  cat > "${KIOSK_ENV_FILE}" <<EOF
# /etc/sovereign-os/frontend-kiosk.env — SDD-704 kiosk target (rewritten by
# 'sovereign-osctl frontend set <value>'). FRONTEND_KIOSK_URL is what the
# fullscreen browser opens.
FRONTEND_KIOSK_URL=${1}
EOF
  info "kiosk target → ${1}  (${KIOSK_ENV_FILE})"
}

set_target() {
  # Boot target. In a chroot (no systemd as PID 1) set-default is a tolerated no-op —
  # the display-manager/kiosk unit's [Install] already wires graphical.target.
  if systemctl set-default "${1}" 2>/dev/null; then
    info "default target → ${1}"
  else
    info "set-default ${1} deferred (no running systemd); [Install] wiring still applies"
  fi
}

# (1a) stage every requested stack
for _f in ${FRONTEND_INSTALL//,/ }; do
  case "${_f}" in
    gnome)                             info "stage: gnome desktop"; install_gnome_de ;;
    dashboards-kiosk|open-computer-kiosk) info "stage: kiosk stack (${_f})"; install_kiosk_stack ;;
    none)                              : ;;
    *)                                 red "unknown frontend stack '${_f}' — skipping" ;;
  esac
done

# (1b) activate the default
case "${FRONTEND}" in
  none)
    info "frontend=none — headless (multi-user.target); gdm + kiosk disabled"
    systemctl disable gdm3.service 2>/dev/null || true
    systemctl disable sovereign-frontend-kiosk.service 2>/dev/null || true
    set_target multi-user.target
    ;;
  gnome)
    info "frontend=gnome — desktop + dashboards launcher (gdm on graphical.target)"
    systemctl disable sovereign-frontend-kiosk.service 2>/dev/null || true
    set_target graphical.target
    ;;
  dashboards-kiosk|open-computer-kiosk)
    _url="${FRONTEND_KIOSK_URL}"
    [ "${FRONTEND}" = open-computer-kiosk ] && \
      _url="${SOVEREIGN_OS_FRONTEND_KIOSK_URL:-http://127.0.0.1:3000/}"
    write_kiosk_env "${_url}"
    # A kiosk owns the display — disable gdm so it doesn't contend for the seat.
    systemctl disable gdm3.service 2>/dev/null || true
    systemctl enable sovereign-frontend-kiosk.service 2>/dev/null \
      && info "kiosk ENABLED (default frontend=${FRONTEND})" \
      || info "kiosk enable deferred (no running systemd / unit absent)"
    set_target graphical.target
    ;;
  *)
    red "unknown SOVEREIGN_OS_FRONTEND='${FRONTEND}' — falling back to gnome default"
    set_target graphical.target
    ;;
esac

# ── (1b) build the cockpit-wasm full bridge so the panels' crate features run ──
# The panels load webapp/_shared/cockpit-wasm/cockpit_wasm_full.js (~3.8 MB) to run the real
# sovereign-cockpit-* crates in-browser (F-2026-001 / SDD-800). It is gitignored + built on
# demand, so WITHOUT this step the panels deploy but every crate feature silently no-ops (they
# still render — graceful degradation). Build it HERE, into SRC, before the deploy serves webapp/.
# Build as the invoking (non-root) user, who owns the rustup toolchain; graceful if it is absent.
step "1b/5 build cockpit-wasm full bridge (crate features → panels)"
FULL_BRIDGE="${SRC}/webapp/_shared/cockpit-wasm/cockpit_wasm_full.js"
BUILD_USER="${SUDO_USER:-$(id -un)}"
info "building the full cockpit-wasm bridge as '${BUILD_USER}' (needs rustup wasm32-unknown-unknown + wasm-bindgen 0.2.100)…"
if su - "${BUILD_USER}" -c "cd '${SRC}' && bash cockpit-wasm/build.sh --full" >/dev/null 2>&1 && [ -f "${FULL_BRIDGE}" ]; then
  info "built full bridge ($(du -h "${SRC}/webapp/_shared/cockpit-wasm/cockpit_wasm_full_bg.wasm" 2>/dev/null | cut -f1)) — the cockpit crates now run live in the panels"
elif [ -f "${FULL_BRIDGE}" ]; then
  red "WARN: rebuild failed — serving the existing prebuilt full bridge (it may be stale)."
else
  red "WARN: full cockpit-wasm bridge unavailable (wasm toolchain absent?)."
  red "      Panels will run WITHOUT crate features — they still render, degraded gracefully."
  red "      Fix: run 'make cockpit-wasm' as a user with rustup wasm32-unknown-unknown + wasm-bindgen 0.2.100, then re-run this installer."
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
# Enable EVERY read-only panel API so the dashboards are LIVE (not just served
# HTML) on a fresh install — operator directive "dashboards running by default".
# The privileged execution panels (flash/emulate/ups) + the sole write daemon
# (control-exec) are the ONLY exceptions — deploy-only, operator-launched (below).
_API_MANAGED=" sovereign-flash-api sovereign-emulate-api sovereign-ups-api sovereign-control-exec-api sovereign-master-dashboard-api "
_apin=0
for _svc in "${SRC}"/systemd/system/sovereign-*-api.service; do
  [ -f "${_svc}" ] || continue
  _base="$(basename "${_svc}" .service)"
  case "${_API_MANAGED}" in *" ${_base} "*) continue;; esac
  enable_unit "${_base}.service"; _apin=$((_apin+1))
done
info "read-only panel APIs enabled: ${_apin} (dashboards live; flash/emulate/ups + control-exec stay operator-launched)"

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

# ── (3b) system runtime: recurrent timers + config defaults + metrics sink ──
# Not GUI-specific, but this is the shared in-chroot install point (root reflash +
# standalone), so make the box self-maintaining + land the config defaults here too
# (provision-bake does the same on the mkosi image path).
step "3b/5 recurrent maintenance timers + config defaults + node_exporter"
# metrics: the textfile-collector sink + its scraper
mkdir -p /var/lib/node_exporter/textfile_collector 2>/dev/null || true
if systemctl enable prometheus-node-exporter.service 2>/dev/null; then info "node_exporter enabled (textfile scraper)"; fi
# runtime config defaults → /etc/sovereign-os (copy-if-ABSENT, never clobber)
mkdir -p /etc/sovereign-os
_cn=0
for _ex in "${SRC}"/config/*.toml.example "${SRC}"/config/*.yaml.example "${SRC}"/config/science/*.toml.example; do
  [ -f "${_ex}" ] || continue
  _dst="/etc/sovereign-os/$(basename "${_ex}" .example)"
  [ -e "${_dst}" ] || { install -m 644 "${_ex}" "${_dst}" 2>/dev/null && _cn=$((_cn+1)); }
done
info "config defaults → /etc/sovereign-os (${_cn} file(s))"
# recurrent maintenance timers — enable them all so the box self-maintains
# (power-shutdown-guard is armed separately by the UPS/power path)
_tn=0
for _tmr in "${SRC}"/systemd/system/sovereign-*.timer; do
  [ -f "${_tmr}" ] || continue
  _tb="$(basename "${_tmr}" .timer)"
  [ "${_tb}" = "sovereign-power-shutdown-guard" ] && continue
  [ -f "${SRC}/systemd/system/${_tb}.service" ] \
    && install -m 644 "${SRC}/systemd/system/${_tb}.service" /etc/systemd/system/ 2>/dev/null || true
  if enable_unit "${_tb}.timer"; then _tn=$((_tn+1)); fi
done
info "recurrent maintenance timers enabled (${_tn})"

# ── (3c) live-reload — keep developing on the deployed tree (SDD-203; ON default) ──
# A broker watches the tree + offers open panels a refresh; each enabled panel API
# is wrapped through reload-run.py via a drop-in so an edit to its OWN .py re-execs
# it in place (same PID, no kill). Webapp/shelled-script edits are already a pure
# refresh (daemons read fresh). The shipped units stay byte-identical — the wrap
# lives only in a drop-in. Set SOVEREIGN_OS_BAKE_LIVERELOAD=0 for a locked build.
step "3c/5 live-reload broker + self-re-exec wrapping (bake.livereload; default on)"
if [ "${SOVEREIGN_OS_BAKE_LIVERELOAD:-1}" = "1" ]; then
  _RR="/usr/local/lib/sovereign-os/scripts/operator/lib/reload-run.py"
  [ -f "${SRC}/systemd/system/sovereign-livereload-broker.service" ] \
    && enable_unit sovereign-livereload-broker.service
  _lr=0
  for _u in /etc/systemd/system/sovereign-*-api.service \
            /etc/systemd/system/sovereign-dashboards.service; do
    [ -f "${_u}" ] || continue
    _b="$(basename "${_u}")"
    _s="$(grep -oE '/usr/local/lib/sovereign-os/scripts/operator/[a-z0-9-]+\.py' "${_u}" | head -1)"
    [ -n "${_s}" ] || continue
    mkdir -p "/etc/systemd/system/${_b}.d"
    printf '[Service]\nEnvironment=SOVEREIGN_OS_LIVERELOAD=1\nExecStart=\nExecStart=/usr/bin/python3 %s %s\n' \
      "${_RR}" "${_s}" > "/etc/systemd/system/${_b}.d/livereload.conf"
    _lr=$((_lr+1))
  done
  systemctl daemon-reload 2>/dev/null || true
  info "live-reload ON — broker + ${_lr} service(s) self-re-exec on edit (SOVEREIGN_OS_BAKE_LIVERELOAD=0 to disable)"
else
  info "live-reload disabled (SOVEREIGN_OS_BAKE_LIVERELOAD=0)"
fi

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
grn "Frontend + dashboards installed."
cat <<EOF

  Frontend    : ${FRONTEND} (default; staged: ${FRONTEND_INSTALL})
  Dashboards  : running on boot, loopback only
  Entry point : http://127.0.0.1:${DASH_PORT}/   ← the hub (every panel + /panels/ index)
  Find it     : "Sovereign Dashboards" in the app menu, on the desktop,
                and auto-opened on first login (gnome frontend).

  Switch frontend live (no reflash):
    sovereign-osctl frontend list                  # what's staged / active
    sovereign-osctl frontend set dashboards-kiosk  # fullscreen kiosk → the hub
    sovereign-osctl frontend set gnome             # back to the desktop

  Expose beyond loopback (headless / LAN / tailscale) by dropping an override:
    /etc/systemd/system/sovereign-dashboards.service.d/bind.conf
      [Service]
      Environment=BUILD_CONFIGURATOR_API_BIND=0.0.0.0
EOF
