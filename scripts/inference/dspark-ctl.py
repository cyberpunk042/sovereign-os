#!/usr/bin/env python3
"""scripts/inference/dspark-ctl.py — DSpark speculative-decoding on/off control.

The actuation behind `sovereign-osctl dspark {status|enable|disable}` and the
control-systems.yaml `dspark-speculative-decoding` toggle. DSpark (the DFlash
M083 successor, DeepSeek 2026-06-27) is opt-in but ON BY DEFAULT for now; this
tool flips the persistent state file the wrapper (scripts/inference/dspark-
wrap.sh) and the D-21 features API (scripts/operator/lm-orchestration-api.py)
both read.

State model (identical across all three readers):
  * Absent state file            → ON  (opt-in default-on)
  * `enabled = false` in file    → OFF
  * DSPARK_DISABLE_OVERRIDE set  → OFF for that invocation (wins)
  * DSPARK_ENABLE_OVERRIDE set   → ON  for that invocation
The override env vars are per-invocation and do NOT change the persisted file;
`status` reports both the persisted state and the effective state.

Operations:
  status            — persisted + effective on/off (read-only)   [--json]
  enable            — persist ON  (writes `enabled = true`)      (needs write access)
  disable           — persist OFF (writes `enabled = false`)     (needs write access)

Read-mostly philosophy (mirrors cpu-mode.py): `status` NEVER writes; only
enable/disable write, and non-writable /etc prints the actionable sudo command
+ exits 2 rather than failing opaquely.

Env:
  DSPARK_STATE   state file path (default /etc/sovereign-os/dspark.toml)
  DSPARK_ENABLE_OVERRIDE / DSPARK_DISABLE_OVERRIDE   effective-state overrides
  SOVEREIGN_OS_METRICS_DIR   node_exporter textfile collector dir

Exit codes:
  0  ok            1  write partially failed
  2  usage error / not writable (non-root against /etc)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

STATE_PATH = Path(os.environ.get("DSPARK_STATE", "/etc/sovereign-os/dspark.toml"))
METRICS_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector"))

_HEADER = (
    "# /etc/sovereign-os/dspark.toml — DSpark speculative decoding toggle\n"
    "# Managed by `sovereign-osctl dspark {enable|disable}`. Absent file = ON\n"
    "# (opt-in, default-on). DSpark is the DFlash (M083) successor — lossless\n"
    "# speculative decoding; see config/inference/m083-dflash-speculative-\n"
    "# decoding.yaml (dspark:).\n"
)


def _persisted_off() -> bool:
    """True iff the state file exists and says `enabled = false`."""
    try:
        for line in STATE_PATH.read_text().splitlines():
            s = line.strip().replace(" ", "")
            if s.startswith("#"):
                continue
            if s.startswith("enabled=false"):
                return True
    except OSError:
        pass
    return False


def _effective(persisted_on: bool) -> tuple[bool, str]:
    """Effective state with the wrapper/api precedence:
    DSPARK_DISABLE_OVERRIDE > DSPARK_ENABLE_OVERRIDE > persisted > default-on."""
    if os.environ.get("DSPARK_DISABLE_OVERRIDE"):
        return False, "operator-override (DSPARK_DISABLE_OVERRIDE)"
    if os.environ.get("DSPARK_ENABLE_OVERRIDE"):
        return True, "operator-override (DSPARK_ENABLE_OVERRIDE)"
    if persisted_on:
        return True, "opt-in default-on" if not STATE_PATH.exists() else f"enabled in {STATE_PATH}"
    return False, f"disabled in {STATE_PATH}"


def _emit_metric(action: str) -> None:
    """Best-effort Layer-B toggle counter (exempt telemetry, sibling of the
    wrapper's sovereign_os_dspark_* namespace). Writes Prometheus HELP/TYPE
    headers once on a fresh file (no duplicate HELP on append). Never fails."""
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-dspark-toggle.prom"
        fresh = not prom.exists()
        with open(prom, "a") as f:
            if fresh:
                f.write("# HELP sovereign_os_dspark_toggle_total DSpark on/off flips via sovereign-osctl dspark.\n")
                f.write("# TYPE sovereign_os_dspark_toggle_total counter\n")
                f.write("# HELP sovereign_os_dspark_toggle_last_timestamp Unix time of the last DSpark on/off toggle.\n")
                f.write("# TYPE sovereign_os_dspark_toggle_last_timestamp gauge\n")
            f.write(f'sovereign_os_dspark_toggle_total{{action="{action}"}} 1\n')
            f.write(f'sovereign_os_dspark_toggle_last_timestamp {int(time.time())}\n')
    except OSError:
        pass


def cmd_status(json_out: bool) -> int:
    persisted_off = _persisted_off()
    persisted_on = not persisted_off
    effective, reason = _effective(persisted_on)
    if json_out:
        print(json.dumps({
            "control": "dspark-speculative-decoding",
            "opt_in": True,
            "default_enabled": True,
            "persisted_enabled": persisted_on,
            "effective_enabled": effective,
            "effective_reason": reason,
            "state_path": str(STATE_PATH),
            "state_file_present": STATE_PATH.exists(),
            "successor_to": "M083 DFlash",
        }, indent=2))
        return 0
    print("── DSpark speculative decoding (DFlash M083 successor) ──")
    print(f"  persisted:  {'ON' if persisted_on else 'OFF'}"
          f"  ({STATE_PATH}{'' if STATE_PATH.exists() else ' — absent → default-on'})")
    print(f"  effective:  {'ON' if effective else 'OFF'}  — {reason}")
    print("  model:      opt-in, ON by default · DSpark-5 · lossless")
    if persisted_on == effective:
        print("  toggle:     `sovereign-osctl dspark disable` to turn off"
              if effective else "  toggle:     `sovereign-osctl dspark enable` to turn on")
    return 0


def _write_state(enabled: bool) -> int:
    body = _HEADER + f"enabled = {'true' if enabled else 'false'}\n"
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(body)
    except OSError as e:
        verb = "enable" if enabled else "disable"
        print(f"# Cannot write {STATE_PATH}: {e}", file=sys.stderr)
        print(f"# Not writable (needs root for /etc) — run:\n"
              f"  sudo sovereign-osctl dspark {verb}", file=sys.stderr)
        return 2
    _emit_metric("enable" if enabled else "disable")
    print(f"# DSpark {'ENABLED' if enabled else 'DISABLED'} — wrote {STATE_PATH}")
    print(f"#   (takes effect on the next inference invocation via dspark-wrap.sh)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="DSpark speculative-decoding on/off control.")
    sub = p.add_subparsers(dest="action", required=True)
    p_status = sub.add_parser("status", help="persisted + effective on/off (read-only)")
    p_status.add_argument("--json", action="store_true")
    sub.add_parser("enable", help="persist ON (opt-in default-on)")
    sub.add_parser("disable", help="persist OFF")
    args = p.parse_args()
    if args.action == "status":
        return cmd_status(args.json)
    if args.action == "enable":
        return _write_state(True)
    if args.action == "disable":
        return _write_state(False)
    return 2


if __name__ == "__main__":
    sys.exit(main())
