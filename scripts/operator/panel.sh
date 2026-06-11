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

LOG_DIR="${TMPDIR:-/tmp}/sovereign-panels"
mkdir -p "${LOG_DIR}"

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
    *build-configurator-api.py*|*dashboard/serve.py*|*master-dashboard-api.py*|\
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
start_server runtime-dashboard "${DASH_PORT}" / \
  python3 scripts/dashboard/serve.py --bind "${DASH_BIND}" && dash_ok=1

# Cockpit data APIs — the master dashboard's live tiles. Ports mirror the
# systemd units; the configurator's /api/* dev gateway proxies to them.
declare -A COCKPIT_APIS=(
  ["master-dashboard-api"]=8090
  ["m060-health-api"]=8160
  ["ms022-sse-quota-api"]=7711
  ["four-watchdog-api"]=7712
)
cockpit_up=0
for api in "${!COCKPIT_APIS[@]}"; do
  port="${COCKPIT_APIS[$api]}"
  if [ -f "scripts/operator/${api}.py" ]; then
    start_server "${api}" "${port}" /healthz \
      python3 "scripts/operator/${api}.py" && cockpit_up=$((cockpit_up+1))
  fi
done
panel_count="$(find "${__REPO_ROOT}/webapp" -mindepth 2 -maxdepth 2 -name index.html | wc -l)"
[ "${cfg_ok}" = 1 ] || echo -e "  ${yellow}✗ CONFIGURATOR DOWN — see ${LOG_DIR}/configurator.log${reset}"
[ "${dash_ok}" = 1 ] || echo -e "  ${yellow}✗ runtime dashboard down — see ${LOG_DIR}/runtime-dashboard.log${reset}"
echo -e "  ${green}●${reset} build configurator   ${cyan}http://127.0.0.1:${CFG_PORT}/${reset}"
echo -e "      ├ Run console: ▶ validate · ▶ preflight work now; ▶ BUILD needs ${bold}sudo -E scripts/operator/panel.sh${reset}"
echo -e "      └ manage THIS host: click ${bold}target: image build${reset} in the topbar"
echo -e "  ${green}●${reset} ALL ${panel_count} PANELS        ${cyan}http://127.0.0.1:${CFG_PORT}/panels${reset}"
echo -e "  ${green}●${reset} cockpit (LIVE)       ${cyan}http://127.0.0.1:${CFG_PORT}/master-dashboard/${reset}"
echo -e "      └ ${cockpit_up}/4 data APIs up (m060 :8160 · ms022 :7711 · four-watchdog :7712 · registry :8090)"
echo -e "  ${green}●${reset} runtime dashboard    ${cyan}http://${DASH_BIND}/${reset}"
echo
echo -e "  Host-mutating commands stay ${bold}⚡ YOU RUN${reset}; the Run console executes"
echo -e "  whitelisted build actions server-side with live streamed logs."
echo -e "  Runbook: ${cyan}docs/src/ops/run-on-host.md${reset}"
echo
echo -e "  ${bold}Ctrl-C stops both servers.${reset}"

wait
