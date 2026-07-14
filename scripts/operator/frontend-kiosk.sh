#!/usr/bin/env bash
# scripts/operator/frontend-kiosk.sh — SDD-704 kiosk launcher.
#
# ExecStart of sovereign-frontend-kiosk.service: run a minimal Wayland kiosk
# compositor (cage) with a single fullscreen browser pointed at FRONTEND_KIOSK_URL.
# seatd (wired in the unit) grants the compositor seat/DRM/input access, so no login
# manager or PAM session is needed and NoNewPrivileges stays on. Browser preference:
# firefox-esr → firefox → chromium → chromium-browser; fails loudly if none is present
# so the unit surfaces the gap in the journal rather than silently black-screening.
#
# The URL comes from /etc/sovereign-os/frontend-kiosk.env (EnvironmentFile in the
# unit), rewritten by `sovereign-osctl frontend set <value>` — dashboards-kiosk points
# at the :8100 hub, open-computer-kiosk at the sandbox UI (SDD-706).
set -euo pipefail

URL="${FRONTEND_KIOSK_URL:-http://127.0.0.1:8100/}"

if ! command -v cage >/dev/null 2>&1; then
  echo "frontend-kiosk: cage (Wayland kiosk compositor) not installed — apt install cage" >&2
  exit 1
fi

if command -v firefox-esr >/dev/null 2>&1; then
  exec cage -- firefox-esr --kiosk "${URL}"
elif command -v firefox >/dev/null 2>&1; then
  exec cage -- firefox --kiosk "${URL}"
elif command -v chromium >/dev/null 2>&1; then
  exec cage -- chromium --kiosk --noerrdialogs --disable-infobars "${URL}"
elif command -v chromium-browser >/dev/null 2>&1; then
  exec cage -- chromium-browser --kiosk --noerrdialogs --disable-infobars "${URL}"
fi

echo "frontend-kiosk: no browser found (firefox-esr / firefox / chromium) — install one" >&2
exit 1
