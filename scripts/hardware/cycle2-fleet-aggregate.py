#!/usr/bin/env python3
"""scripts/hardware/cycle2-fleet-aggregate.py — fleet-wide rollup
of per-host R187 cycle2-status JSON output (R199).

selfdef cycle-3 SDD-021 W-3: "Cross-host fleet aggregation API.
R187 cycle2-status runs per-host. Cycle 4: a sovereign-os-side
fleet aggregator that reads cycle2-status JSON from N hosts."
Closed in this round via file-based variant — operator collects
per-host JSON into a directory; this script rolls up.

Operator workflow:

  # On each host:
  $ sovereign-osctl ... | python3 scripts/hardware/cycle2-status.py --json > /tmp/host.json
  # Copy to a central machine, then:
  $ ls fleet/
  prod-01.json  prod-02.json  prod-03.json
  $ scripts/hardware/cycle2-fleet-aggregate.py --dir fleet/

Output:

  # R199: fleet rollup — 3 host(s)
  # caps present:        3/3
  # sain01 FullMatch:    2/3
  # modules-gate avg:    87% modules apply across fleet
  # models-gate avg:     95%
  # bitnet schedule:     2/3 hosts
  # wasm-AOT cache:      1/3 hosts
  # override events:     5 total (2× --ignore-hardware, 3× --strict-hardware)

CLI:
  cycle2-fleet-aggregate.py --dir <dir>           # human rollup
  cycle2-fleet-aggregate.py --dir <dir> --json    # machine output

Exit codes:
  0  rollup complete
  2  arg / I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_per_host(dir_: Path) -> list[tuple[str, dict[str, Any]]]:
    """Read every *.json under dir_; tuple is (host_name, status_dict).
    host_name = filename stem."""
    if not dir_.exists() or not dir_.is_dir():
        return []
    out = []
    for entry in sorted(dir_.iterdir()):
        if entry.suffix != ".json":
            continue
        try:
            doc = json.loads(entry.read_text())
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(f"WARN R199: skipping {entry}: {e}\n")
            continue
        out.append((entry.stem, doc))
    return out


def aggregate(hosts: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    total = len(hosts)
    if total == 0:
        return {
            "schema_version": "1.0.0",
            "host_count": 0,
            "rollups": {},
        }
    caps_present = sum(1 for _, d in hosts if d.get("caps_present"))
    full_match = sum(1 for _, d in hosts if d.get("sain01_verdict") == "FullMatch")
    bitnet_schedule = sum(1 for _, d in hosts if d.get("bitnet_schedule_present"))
    wasm_aot_present = sum(
        1 for _, d in hosts if (d.get("wasm_aot_cache") or {}).get("present")
    )
    # Gate aggregate: per-host (kept / total); fleet-wide mean.
    modules_pass_rates = []
    models_pass_rates = []
    for _, d in hosts:
        mg = d.get("modules_gate") or {}
        if mg.get("available") and mg.get("total", 0) > 0:
            modules_pass_rates.append(mg["kept"] / mg["total"])
        mdg = d.get("models_gate") or {}
        if mdg.get("available") and mdg.get("total", 0) > 0:
            models_pass_rates.append(mdg["kept"] / mdg["total"])
    modules_avg = (
        sum(modules_pass_rates) / len(modules_pass_rates)
        if modules_pass_rates
        else None
    )
    models_avg = (
        sum(models_pass_rates) / len(models_pass_rates)
        if models_pass_rates
        else None
    )
    # Override audit aggregate.
    override_total = 0
    override_by_cat: dict[str, int] = {}
    for _, d in hosts:
        a = d.get("override_audit") or {}
        override_total += int(a.get("count", 0) or 0)
        for k, v in (a.get("by_category", {}) or {}).items():
            override_by_cat[k] = override_by_cat.get(k, 0) + int(v)
    return {
        "schema_version": "1.0.0",
        "host_count": total,
        "rollups": {
            "caps_present": {"hosts": caps_present, "total": total},
            "sain01_full_match": {"hosts": full_match, "total": total},
            "bitnet_schedule_present": {"hosts": bitnet_schedule, "total": total},
            "wasm_aot_cache_present": {"hosts": wasm_aot_present, "total": total},
            "modules_gate_pass_rate_avg": modules_avg,
            "models_gate_pass_rate_avg": models_avg,
            "override_audit_total": override_total,
            "override_audit_by_category": override_by_cat,
        },
    }


def render_human(summary: dict[str, Any]) -> str:
    if summary["host_count"] == 0:
        return "# R199: fleet rollup — 0 host(s) found\n"
    out: list[str] = []
    out.append(f"# R199: fleet rollup — {summary['host_count']} host(s)")
    r = summary["rollups"]
    out.append(
        f"# caps present:           {r['caps_present']['hosts']}/{r['caps_present']['total']}"
    )
    out.append(
        f"# sain01 FullMatch:       {r['sain01_full_match']['hosts']}/{r['sain01_full_match']['total']}"
    )
    if r["modules_gate_pass_rate_avg"] is not None:
        out.append(
            f"# modules-gate avg:       {r['modules_gate_pass_rate_avg'] * 100:.0f}% modules apply across fleet"
        )
    if r["models_gate_pass_rate_avg"] is not None:
        out.append(
            f"# models-gate avg:        {r['models_gate_pass_rate_avg'] * 100:.0f}%"
        )
    out.append(
        f"# bitnet schedule:        {r['bitnet_schedule_present']['hosts']}/{r['bitnet_schedule_present']['total']} hosts"
    )
    out.append(
        f"# wasm-AOT cache:         {r['wasm_aot_cache_present']['hosts']}/{r['wasm_aot_cache_present']['total']} hosts"
    )
    if r["override_audit_total"] > 0:
        out.append(f"# override events:        {r['override_audit_total']} total")
        for cat, count in sorted(r["override_audit_by_category"].items()):
            label = {
                "selfdef.modules.override": "--ignore-hardware",
                "selfdef.modules.skip-strict": "--strict-hardware (refused)",
            }.get(cat, cat)
            out.append(f"#                          {count}× {label}")
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="fleet rollup of cycle2-status JSON (R199)")
    p.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Directory containing per-host *.json files",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not args.dir.exists() or not args.dir.is_dir():
        sys.stderr.write(f"ERROR: --dir not found or not a directory: {args.dir}\n")
        return 2
    hosts = load_per_host(args.dir)
    summary = aggregate(hosts)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        sys.stdout.write(render_human(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
