#!/usr/bin/env python3
"""scripts/inference/lib/pick-gpu.py — consume the SD-R28 selfdef
schedule + emit CUDA_VISIBLE_DEVICES for a requested role.

selfdef R28 (`bitnet-gpu-inference` module) writes
/etc/selfdef/bitnet/schedule.json containing a per-GPU role
assignment derived from the SD-R25 HardwareCapabilities (largest-VRAM
GPU → `model_inference`, secondary → `auxiliary`, etc.).

sovereign-os inference start scripts (start-pulse.sh /
start-logic-engine.sh / start-oracle-core.sh) can source this
helper to pin workloads on the right GPU without each script
re-deriving the mapping.

CLI:
  pick-gpu.py <role>           # → prints "CUDA_VISIBLE_DEVICES=<idx>"
                               # → exits 0 if found
                               # → exits 1 + prints unset line if not
  pick-gpu.py <role> --json    # full schedule entry for the role

Env overrides:
  SELFDEF_BITNET_SCHEDULE_FILE  path to schedule.json
                                (default: /etc/selfdef/bitnet/schedule.json)
  PICK_GPU_DEFAULT              fallback role:idx (e.g. "model_inference:0")
                                used when schedule.json is missing

Exit codes:
  0  picked successfully (role matched OR fallback returned an idx)
  1  schedule.json present but no entry matches role + no fallback
  2  bad args (e.g. missing role)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_SCHEDULE = Path("/etc/selfdef/bitnet/schedule.json")
VALID_ROLES = {"model_inference", "auxiliary", "spare"}


def read_schedule(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"WARN  pick-gpu: schedule file unreadable: {e}\n")
        return None
    sched = doc.get("schedule")
    if not isinstance(sched, list):
        return None
    return sched


def parse_fallback(s: str | None) -> tuple[str, int] | None:
    if not s or ":" not in s:
        return None
    role, idx_str = s.split(":", 1)
    try:
        return role, int(idx_str)
    except ValueError:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description="Pick a GPU index for an inference role")
    p.add_argument("role", help="One of: model_inference, auxiliary, spare")
    p.add_argument(
        "--schedule",
        type=Path,
        default=Path(
            os.environ.get("SELFDEF_BITNET_SCHEDULE_FILE", str(DEFAULT_SCHEDULE))
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="emit the full schedule entry as JSON instead of an env-line",
    )
    args = p.parse_args()

    if args.role not in VALID_ROLES:
        sys.stderr.write(
            f"ERROR pick-gpu: role must be one of {sorted(VALID_ROLES)}, got: {args.role}\n"
        )
        return 2

    schedule = read_schedule(args.schedule)
    fallback = parse_fallback(os.environ.get("PICK_GPU_DEFAULT"))

    if schedule:
        matches = [s for s in schedule if s.get("role") == args.role]
        if matches:
            entry = matches[0]
            idx = int(entry.get("gpu_index", -1))
            if idx >= 0:
                if args.json:
                    print(json.dumps(entry))
                else:
                    print(f"CUDA_VISIBLE_DEVICES={idx}")
                return 0

    if fallback and fallback[0] == args.role:
        sys.stderr.write(
            f"INFO  pick-gpu: schedule miss for `{args.role}` — using"
            f" PICK_GPU_DEFAULT={fallback[1]}\n"
        )
        if args.json:
            print(json.dumps({"role": args.role, "gpu_index": fallback[1],
                              "source": "fallback"}))
        else:
            print(f"CUDA_VISIBLE_DEVICES={fallback[1]}")
        return 0

    # No schedule + no fallback — print an explicit "unset" line so
    # downstream `eval $(...)` style invocations clear stale state.
    if args.json:
        print("null")
    else:
        print("CUDA_VISIBLE_DEVICES=")
    return 1


if __name__ == "__main__":
    sys.exit(main())
