#!/usr/bin/env bash
# sovereign-telemetry textfile writer (M045 E0430 / M013).
#
# Runs the `sovereign-telemetry` probe in --prometheus mode and writes its
# exposition ATOMICALLY (tmp + rename) to the node_exporter textfile_collector
# directory, so a scrape never sees a half-written file. Honest-offline: if the
# probe fails, a `sovereign_telemetry_probe_failed 1` sentinel is published
# instead of a stale or empty file, matching the codebase's textfile_emit
# doctrine.
set -euo pipefail

BIN="${SOVEREIGN_TELEMETRY_BIN:-/opt/sovereign-os/bin/sovereign-telemetry}"
OUT_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
OUT="${OUT_DIR}/sovereign-telemetry.prom"

tmp="$(mktemp "${OUT}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

if "$BIN" --prometheus >"$tmp" 2>/dev/null; then
    chmod 0644 "$tmp"
    mv -f "$tmp" "$OUT"
else
    {
        printf '# HELP sovereign_telemetry_probe_failed 1 when the probe could not sample.\n'
        printf '# TYPE sovereign_telemetry_probe_failed gauge\n'
        printf 'sovereign_telemetry_probe_failed 1\n'
    } >"$tmp"
    chmod 0644 "$tmp"
    mv -f "$tmp" "$OUT"
    exit 1
fi
