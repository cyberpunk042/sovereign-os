#!/usr/bin/env python3
"""scripts/hardware/nvidia-persistence.py — R556 (E11.M19) NVIDIA persistence mode.

Operator §1g (verbatim, sacrosanct):
  "Dedicated to AI inference Mode" / "zero first-prompt thermal spike"

Persistence mode is a per-GPU knob exposed by the NVIDIA driver. With
it OFF (default), the driver tears down GPU state (kernels unloaded,
clocks reset, UVM mappings dropped) every time the last CUDA context
exits. The very next CUDA-using process pays ~2s of re-init cost to
load the driver back, walk the UVM topology, set clocks, etc. — and
that ~2s lands squarely on the operator's first prompt latency.

With persistence ON, the driver stays resident across context
boundaries. The cost: a few hundred MB of GPU RAM held by the
persistent daemon. The benefit: every subsequent CUDA process is
instantly hot.

Two surfaces achieve persistence:
  1. `nvidia-smi -pm 1`                 — runtime knob (this script).
  2. `nvidia-persistenced` systemd unit — daemon-driven, survives
                                          reboot. Provided by the
                                          NVIDIA driver package; we
                                          don't ship it, but the
                                          status verb reports whether
                                          it's running.

Verbs:
  show / status   — print per-GPU persistence + daemon state.
  list-gpus       — minimal index/name listing.
  enable          — runtime `nvidia-smi -pm 1`. Requires root.
                    Optional --gpu N to scope; default = all.
  disable         — runtime `nvidia-smi -pm 0`. Requires root.

Read-mostly philosophy: show/status/list-gpus NEVER write.

Exit codes:
  0  ok
  1  nvidia-smi reported an error on at least one GPU
  2  usage / not-root / nvidia-smi absent
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any


def nvidia_smi() -> str | None:
    return shutil.which("nvidia-smi")


def systemctl_state(unit: str) -> str | None:
    sc = shutil.which("systemctl")
    if not sc:
        return None
    try:
        r = subprocess.run(
            [sc, "is-active", unit],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def query_gpus() -> list[dict[str, Any]]:
    smi = nvidia_smi()
    if not smi:
        return []
    try:
        r = subprocess.run(
            [smi,
             "--query-gpu=index,name,persistence_mode,uuid",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    out: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        out.append({
            "index": idx,
            "name": parts[1],
            "persistence_mode": parts[2],
            "uuid": parts[3],
        })
    return out


def gather_state() -> dict[str, Any]:
    return {
        "nvidia_smi_present": nvidia_smi() is not None,
        "persistenced_active": systemctl_state("nvidia-persistenced"),
        "gpus": query_gpus(),
    }


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "[nvidia-persistence] this verb requires root. "
            "Re-run with sudo.",
            file=sys.stderr,
        )
        sys.exit(2)


def set_persistence(enabled: bool, gpu: int | None) -> int:
    require_root()
    smi = nvidia_smi()
    if not smi:
        print("[nvidia-persistence] nvidia-smi not present.",
              file=sys.stderr)
        return 2
    args = [smi, "-pm", "1" if enabled else "0"]
    if gpu is not None:
        args.extend(["-i", str(gpu)])
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                            check=False, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[nvidia-persistence] subprocess failure: {e}",
              file=sys.stderr)
        return 1
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0:
        if r.stderr:
            print(r.stderr.rstrip(), file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="nvidia-persistence",
        description="NVIDIA persistence mode controller (R556 / E11.M19).",
    )
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_list = sub.add_parser("list-gpus")
    sp_list.add_argument("--json", action="store_true", dest="json_sub")
    sp_en = sub.add_parser("enable")
    sp_en.add_argument("--gpu", type=int, default=None)
    sp_dis = sub.add_parser("disable")
    sp_dis.add_argument("--gpu", type=int, default=None)
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("show", "status"):
        state = gather_state()
        if json_out:
            print(json.dumps(state, indent=2))
            return 0
        print("── sovereign-os NVIDIA persistence (R556 / E11.M19) ──")
        if not state["nvidia_smi_present"]:
            print("  nvidia-smi: NOT PRESENT (no NVIDIA driver loaded?)")
            return 0
        print(f"  nvidia-persistenced: {state['persistenced_active'] or '(unknown)'}")
        for g in state["gpus"]:
            print(
                f"    gpu {g['index']:>2}  persistence={g['persistence_mode']:>8s}  "
                f"{g['name']}"
            )
        if not state["gpus"]:
            print("    (no GPUs reported by nvidia-smi)")
        return 0

    if verb == "list-gpus":
        gpus = query_gpus()
        if json_out:
            print(json.dumps({"gpus": gpus}, indent=2))
        else:
            for g in gpus:
                print(f"  gpu {g['index']:>2}  {g['name']}  ({g['uuid']})")
        return 0

    if verb == "enable":
        return set_persistence(True, args.gpu)
    if verb == "disable":
        return set_persistence(False, args.gpu)

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
