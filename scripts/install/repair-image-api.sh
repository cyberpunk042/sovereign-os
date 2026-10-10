#!/usr/bin/env bash
# Repair only the image cockpit API's access to a home-backed live checkout.
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
unit=sovereign-image-generation-api.service
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: bash $0" >&2
  exit 1
fi
if [ "$(readlink -f /usr/local/lib/sovereign-os)" != "$repo" ]; then
  echo 'Installed tree differs from this checkout; refusing to change service access.' >&2
  exit 1
fi
case "$repo" in
  *[[:space:]%]*) echo 'Unsupported checkout path' >&2; exit 1 ;;
esac
systemctl cat "$unit" >/dev/null
case "$repo" in
  /home/*)
    install -d -m 0755 "/etc/systemd/system/$unit.d"
    printf '[Service]\nProtectHome=tmpfs\nBindReadOnlyPaths=%s\n' "$repo" > "/etc/systemd/system/$unit.d/dev-source.conf"
    ;;
esac
systemctl daemon-reload
systemctl reset-failed "$unit"
systemctl restart "$unit"
systemctl is-active "$unit"
