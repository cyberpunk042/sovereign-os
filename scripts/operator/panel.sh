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

port_busy() { python3 - "$1" <<'EOF'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1]))); print("free")
except OSError:
    print("busy")
EOF
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

echo -e "${bold}sovereign-os · operator panels${reset}"
echo

if [ "$(port_busy "${CFG_PORT}")" = "busy" ]; then
  echo -e "  ${yellow}!${reset} :${CFG_PORT} already in use — configurator assumed running"
else
  BUILD_CONFIGURATOR_API_PORT="${CFG_PORT}" \
    python3 scripts/operator/build-configurator-api.py 2>/dev/null &
  pids+=($!)
fi

DASH_PORT="${DASH_BIND##*:}"
if [ "$(port_busy "${DASH_PORT}")" = "busy" ]; then
  echo -e "  ${yellow}!${reset} :${DASH_PORT} already in use — runtime dashboard assumed running"
else
  python3 scripts/dashboard/serve.py --bind "${DASH_BIND}" 2>/dev/null &
  pids+=($!)
fi

sleep 0.7
panel_count="$(find "${__REPO_ROOT}/webapp" -mindepth 2 -maxdepth 2 -name index.html | wc -l)"
echo -e "  ${green}●${reset} build configurator   ${cyan}http://127.0.0.1:${CFG_PORT}/${reset}"
echo -e "      ├ Run console: ▶ validate · ▶ preflight work now; ▶ BUILD needs ${bold}sudo -E scripts/operator/panel.sh${reset}"
echo -e "      └ manage THIS host: click ${bold}target: image build${reset} in the topbar"
echo -e "  ${green}●${reset} ALL ${panel_count} PANELS        ${cyan}http://127.0.0.1:${CFG_PORT}/panels${reset}"
echo -e "  ${green}●${reset} cockpit              ${cyan}http://127.0.0.1:${CFG_PORT}/master-dashboard/${reset}"
echo -e "  ${green}●${reset} runtime dashboard    ${cyan}http://${DASH_BIND}/${reset}"
echo
echo -e "  Host-mutating commands stay ${bold}⚡ YOU RUN${reset}; the Run console executes"
echo -e "  whitelisted build actions server-side with live streamed logs."
echo -e "  Runbook: ${cyan}docs/src/ops/run-on-host.md${reset}"
echo
echo -e "  ${bold}Ctrl-C stops both servers.${reset}"

wait
