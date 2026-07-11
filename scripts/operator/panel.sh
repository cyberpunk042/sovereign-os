#!/usr/bin/env bash
# scripts/operator/panel.sh — ONE command to bring up every locally-runnable
# operator panel on the current OS. No sudo, no install, nothing leaves
# the box (both servers bind 127.0.0.1 by default).
#
#   ⚡ YOU RUN:   scripts/operator/panel.sh          (or: make panel)
#
# What it starts:
#   :8100  build configurator  — compose a build OR manage THIS host
#          (target toggle in the topbar). Also statically serves every
#          sibling panel: http://127.0.0.1:8100/master-dashboard/ etc.
#   :8443  runtime dashboard   — live GPU/CPU/network/FS/RAID cards
#          (scripts/dashboard/serve.py, R225)
#
# Ctrl-C stops both. Runbook: docs/src/ops/run-on-host.md
#
# Tunable env:
#   SOVEREIGN_OS_PANEL_CONFIGURATOR_PORT  (default 8100)
#   SOVEREIGN_OS_PANEL_DASHBOARD_BIND     (default 127.0.0.1:8443)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
cd "${__REPO_ROOT}"

CFG_PORT="${SOVEREIGN_OS_PANEL_CONFIGURATOR_PORT:-8100}"
DASH_BIND="${SOVEREIGN_OS_PANEL_DASHBOARD_BIND:-127.0.0.1:8443}"

bold='\033[1m'; green='\033[32m'; yellow='\033[33m'; cyan='\033[36m'; reset='\033[0m'

command -v python3 >/dev/null || { echo "python3 required"; exit 2; }

# Per-user log dir — a PRIOR `sudo` panel run left /tmp/sovereign-panels
# owned by root:root, and under /tmp's sticky bit a normal user can neither
# write into it NOR delete it (caught 2026-07-03: "Permission denied" on
# configurator.log killed the whole launch under `set -e`). Scoping the dir
# by UID means root's run and jfortin's run never share a directory, so no
# prior run can ever poison the next. If a legacy shared dir exists and we
# can't write it, we fall through to the per-user one rather than dying.
LOG_DIR="${TMPDIR:-/tmp}/sovereign-panels-$(id -u)"
if ! mkdir -p "${LOG_DIR}" 2>/dev/null || [ ! -w "${LOG_DIR}" ]; then
  # last resort: a mktemp dir we definitely own
  LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sovereign-panels.XXXXXX")"
fi

# Take over a port we own: previous panel runs (any user) leave servers
# behind; "assumed running" turned out to be a footgun — the old server
# could be STALE CODE or die right after, leaving a dark port (caught
# 2026-06-12: connection-refused on :8100 after a sudo relaunch). Only
# processes matching OUR server scripts are killed; anything else on the
# port is a loud error.
takeover_port() { # <port> → 0 if free (possibly after takeover), 1 if foreign
  local port="$1" pid cmd
  pid="$(fuser -n tcp "${port}" 2>/dev/null | tr -d '[:space:]')" || true
  [ -z "${pid}" ] && return 0
  cmd="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  case "${cmd}" in
    # Every panel process THIS launcher starts is reclaimable on restart:
    # the two main servers, AND all scripts/operator/*-api.py data services
    # (the wildcard). Without the *-api.py wildcard, a prior run's data
    # APIs are seen as FOREIGN and block a fresh `make panel` (caught
    # 2026-07-03: :8107/:8110/… "held by a FOREIGN process" after an
    # abandoned run — the launcher could not restart itself).
    *scripts/operator/*-api.py*|*build-configurator-api.py*|\
    *dashboard/serve.py*|*master-dashboard-api.py*|\
    *m060-health-api.py*|*ms022-sse-quota-api.py*|*four-watchdog-api.py*)
      echo -e "  ${yellow}↻${reset} :${port} held by previous panel (pid ${pid}) — replacing"
      kill "${pid}" 2>/dev/null || sudo -n kill "${pid}" 2>/dev/null || {
        echo -e "  ${yellow}✗${reset} cannot kill pid ${pid} on :${port} (other user?) — stop it manually"; return 1; }
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        fuser -n tcp "${port}" >/dev/null 2>&1 || return 0; sleep 0.3
      done
      echo -e "  ${yellow}✗${reset} :${port} still busy after kill"; return 1 ;;
    "")
      return 0 ;;  # raced away
    *)
      echo -e "  ${yellow}✗${reset} :${port} held by a FOREIGN process (pid ${pid}: ${cmd%% }) — not touching it"
      return 1 ;;
  esac
}

probe() { # <port> <path> → 0 when HTTP answers
  curl -sf --max-time 3 -o /dev/null "http://127.0.0.1:$1$2" 2>/dev/null
}

pids=()
cleanup() {
  trap - EXIT INT TERM   # fire once (INT also triggers EXIT)
  echo
  echo -e "${yellow}stopping panels…${reset}"
  for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo -e "${bold}sovereign-os · operator panels${reset}  (logs: ${LOG_DIR}/)"
echo

start_server() { # <name> <port> <probe-path> <cmd...>
  local name="$1" port="$2" path="$3"; shift 3
  takeover_port "${port}" || return 1
  "$@" >"${LOG_DIR}/${name}.log" 2>&1 &
  pids+=($!)
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    probe "${port}" "${path}" && return 0
    sleep 0.4
  done
  echo -e "  ${yellow}✗ ${name} did NOT come up on :${port} — last log lines:${reset}"
  tail -3 "${LOG_DIR}/${name}.log" 2>/dev/null | sed 's/^/      /'
  return 1
}

cfg_ok=0; dash_ok=0
start_server configurator "${CFG_PORT}" /healthz \
  env BUILD_CONFIGURATOR_API_PORT="${CFG_PORT}" \
  python3 scripts/operator/build-configurator-api.py && cfg_ok=1

DASH_PORT="${DASH_BIND##*:}"
start_server runtime-dashboard "${DASH_PORT}" /healthz \
  python3 scripts/dashboard/serve.py --bind "${DASH_BIND}" && dash_ok=1

# Panel data APIs — start EVERY scripts/operator/*-api.py so the panels
# have live data (not empty tiles). Each API's port comes from its systemd
# unit (Environment=…PORT=NNNN). Best-effort: an API that can't bind/start
# is logged and skipped, never blocks the others. Set
# SOVEREIGN_OS_PANEL_APIS_OFF=1 to skip them all (lean: just the builder).
cockpit_up=0; cockpit_total=0
if [ -z "${SOVEREIGN_OS_PANEL_APIS_OFF:-}" ]; then
  for api in scripts/operator/*-api.py; do
    [ -f "${api}" ] || continue
    name="$(basename "${api}" -api.py)"
    # build-configurator-api IS the main configurator (started above on
    # :8100) and ships no systemd unit — never re-manage it here.
    [ "${name}" = "build-configurator" ] && continue
    unit="systemd/system/sovereign-${name}-api.service"
    # `|| true` is load-bearing: with pipefail, a missing unit or a
    # unit with no PORT= makes this pipe exit non-zero, and under set -e
    # the bare assignment would ABORT the whole launcher (caught 2026-07-03:
    # build-configurator-api.py has no unit → the trap tore down every
    # panel right after the banner). The `[ -n … ] || continue` below is
    # the intended skip path; keep the assignment from ever aborting.
    port="$(grep -oiE '[A-Z0-9_]*PORT=[0-9]+' "${unit}" 2>/dev/null | head -1 | grep -oE '[0-9]+$' || true)"
    [ -n "${port}" ] || continue   # no port declared → can't manage it here
    # Collision guard: NEVER start a data API on the configurator's or the
    # runtime-dashboard's port. Those are owned by the two main servers started
    # above, and start_server's takeover would otherwise EVICT the configurator
    # — leaving the wrong daemon on :8100 so every panel 404s (caught
    # 2026-07-03: sovereign-ux-design-audit-api ships PORT=8100 == CFG_PORT).
    # The configurator serves that panel statically anyway; its data API just
    # can't share :8100 in this dev launcher.
    if [ "${port}" = "${CFG_PORT}" ] || [ "${port}" = "${DASH_PORT}" ]; then
      echo -e "  ${yellow}⚠${reset} ${name}-api declares :${port} (owned by a main server) — not started (collision guard)"
      continue
    fi
    cockpit_total=$((cockpit_total+1))
    start_server "${name}-api" "${port}" /healthz python3 "${api}" \
      && cockpit_up=$((cockpit_up+1))
  done
fi
[ "${cfg_ok}" = 1 ] || echo -e "  ${yellow}✗ CONFIGURATOR DOWN — see ${LOG_DIR}/configurator.log${reset}"
[ "${dash_ok}" = 1 ] || echo -e "  ${yellow}✗ runtime dashboard down — see ${LOG_DIR}/runtime-dashboard.log${reset}"
echo -e "  ${green}●${reset} build configurator   ${cyan}http://127.0.0.1:${CFG_PORT}/${reset}"
echo -e "      ├ Run console: ▶ validate · ▶ preflight work now; ▶ BUILD needs ${bold}sudo -E scripts/operator/panel.sh${reset}"
echo -e "      └ manage THIS host: click ${bold}target: image build${reset} in the topbar"
echo -e "  ${green}●${reset} GLOBAL VIEW          ${cyan}http://127.0.0.1:${CFG_PORT}/panels${reset}  ${bold}← every surface, described${reset}"
echo -e "  ${green}●${reset} cockpit              ${cyan}http://127.0.0.1:${CFG_PORT}/master-dashboard/${reset}"
echo -e "      └ ${cockpit_up}/${cockpit_total} panel data APIs up (SOVEREIGN_OS_PANEL_APIS_OFF=1 for lean mode)"
echo -e "  ${green}●${reset} runtime dashboard    ${cyan}http://${DASH_BIND}/${reset}"
echo
echo -e "  Host-mutating commands stay ${bold}⚡ YOU RUN${reset}; the Run console executes"
echo -e "  whitelisted build actions server-side with live streamed logs."
echo -e "  Runbook: ${cyan}docs/src/ops/run-on-host.md${reset}"
echo
echo -e "  ${bold}Ctrl-C stops both servers.${reset}"

wait
