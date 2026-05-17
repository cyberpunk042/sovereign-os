#!/usr/bin/env python3
"""scripts/hardware/posture.py — R210 (mirror of selfdef SD-R67).

Reads the selfdef-emitted hardware-capabilities JSON (default:
/var/lib/selfdef/hardware-capabilities.json) and renders the
operator-readable hardware-exploit posture summary:

  - Sain01 verdict
  - Target CPU + features (Wasm-AOT / bitnet.cpp tunings)
  - Ternary AOT capability (SD-R64)
  - ZMM INT8 lane capacity (SD-R64, master spec § 16)
  - Operator-readable kernel selection hint (SD-R66)

The summary lets operators answer "does this box actually exploit
the AVX-512 + ZMM hot path?" without parsing the capabilities JSON
themselves.

CLI:
  posture.py                                read default caps path
  posture.py --caps-path /path/to/file      explicit path
  posture.py --json                         emit JSON instead of banner

Exit codes:
  0  capabilities JSON read + posture rendered (Sain01 FullMatch or
     PartialMatch). Sain01 NoMatch is reported but exit stays 0 —
     the script is informational, not gating.
  1  capabilities JSON unreadable or malformed.
  2  usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_CAPS_PATH = Path(
    os.environ.get(
        "SELFDEF_CAPS_PATH",
        "/var/lib/selfdef/hardware-capabilities.json",
    )
)


def render_posture(caps: dict[str, Any]) -> str:
    cpu = caps.get("cpu", {}) or {}
    wasm_aot = caps.get("wasm_aot", {}) or {}
    sain01 = caps.get("sain01_match", {}) or {}

    target_features = wasm_aot.get("target_features", "") or ""
    target_features_display = (
        target_features if target_features else "(none — pre-AVX-512 host)"
    )
    ternary_capable = bool(cpu.get("ternary_aot_capable", False))
    ternary_display = (
        "yes (VNNI + (BF16 or FP16))"
        if ternary_capable
        else "no — host lacks VNNI or small-FP path"
    )
    lanes = int(cpu.get("zmm_int8_lane_capacity", 0) or 0)
    kernel_hint = wasm_aot.get("ternary_kernel_hint", "") or ""
    kernel_display = (
        kernel_hint if kernel_hint else "(no INT8 SIMD path on this host)"
    )
    verdict = sain01.get("overall", "NoMatch")

    lines = [
        "── selfdef hardware-exploit posture (R210/SD-R67) ──",
        f"  Sain01 verdict          : {verdict}",
        f"  Target CPU (LLVM)       : {wasm_aot.get('target_cpu', '?')}",
        f"  Target features         : {target_features_display}",
        f"  Ternary AOT capable     : {ternary_display}",
        f"  ZMM INT8 lane capacity  : {lanes} (master spec § 16 reading)",
        f"  Kernel hint             : {kernel_display}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "sovereign-os bridge to selfdef SD-R67 hardware-exploit "
            "posture (R210)."
        )
    )
    p.add_argument(
        "--caps-path",
        type=Path,
        default=DEFAULT_CAPS_PATH,
        help="capabilities JSON path (default: %(default)s)",
    )
    p.add_argument("--json", action="store_true", help="emit JSON instead of banner")
    args = p.parse_args()

    if not args.caps_path.exists():
        print(
            f"ERROR capabilities JSON not found at {args.caps_path}\n"
            "  (run `selfdefctl hardware export "
            "--output /var/lib/selfdef/hardware-capabilities.json` "
            "on a host with selfdef installed)",
            file=sys.stderr,
        )
        return 1
    try:
        caps = json.loads(args.caps_path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR malformed capabilities JSON: {e}", file=sys.stderr)
        return 1

    if args.json:
        # Flat summary that mirrors selfdefctl --json shape.
        cpu = caps.get("cpu", {}) or {}
        wasm_aot = caps.get("wasm_aot", {}) or {}
        sain01 = caps.get("sain01_match", {}) or {}
        doc = {
            "ternary_aot_capable": bool(cpu.get("ternary_aot_capable", False)),
            "zmm_int8_lane_capacity": int(
                cpu.get("zmm_int8_lane_capacity", 0) or 0
            ),
            "ternary_kernel_hint": wasm_aot.get("ternary_kernel_hint", "") or "",
            "target_cpu": wasm_aot.get("target_cpu", "") or "",
            "target_features": wasm_aot.get("target_features", "") or "",
            "sain01_match": sain01.get("overall", "NoMatch"),
        }
        print(json.dumps(doc, indent=2))
    else:
        sys.stdout.write(render_posture(caps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
