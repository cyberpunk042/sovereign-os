#!/usr/bin/env bash
# scripts/operator/open-computer-run.sh — SDD-706 open-computer runtime launcher.
#
# ExecStart of sovereign-open-computer.service: boot the sandbox VM + serve its agent
# UI (base port from PORT / the profile, default 9800). Reads HOME + OPEN_COMPUTER_*
# from /etc/sovereign-os/open-computer.env (the unit EnvironmentFiles it). Ensures the
# default agent overlay exists, then runs `open-computer up` in the foreground so
# systemd supervises it. If the CLI daemonizes instead of staying foreground on the
# real box, switch the unit to Type=forking (documented in SDD-706 as unverified).
set -euo pipefail

OC_ROOT="${HOME:-/var/lib/sovereign-os/open-computer}"
OC_APP="${OC_ROOT}/src/open-computer"
AGENT="${OPEN_COMPUTER_AGENT:-sovereign}"

if [ ! -x "${OC_APP}/open-computer" ]; then
  echo "open-computer not provisioned at ${OC_APP} — run: sovereign-osctl open-computer install" >&2
  exit 1
fi

cd "${OC_APP}"
# Create the per-agent overlay if it doesn't exist yet (idempotent; ~100MB delta on
# the shared read-only base), then boot it. `|| true` — a present agent is fine.
./open-computer create "${AGENT}" >/dev/null 2>&1 || true
exec ./open-computer up "${AGENT}"
