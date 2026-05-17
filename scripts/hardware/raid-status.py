#!/usr/bin/env python3
"""scripts/hardware/raid-status.py — R223 (SDD-026 Z-9).

Operator-named: "It allow to see the management of the software raid
and observe and operate and configure".

READ-ONLY first cut. Two sub-modes:

  status   Compact list of every md array on this host: level,
           device member count, sync state, rebuild progress.
           Reads /proc/mdstat.

  detail   For one array (or all if --all): per-disk health,
           failed/spare slots, last bitmap update, scrub schedule
           pulled from `mdadm --detail /dev/mdX`. Read-only.

Operator workflow: scheduled invocation (e.g. via timer) into the
fs-insights-style alert flow when an array drops to degraded.
Write verbs (add-spare / fail / replace / scrub-now) defer to a
follow-up round behind explicit SOVEREIGN_OS_CONFIRM_DESTROY gate
+ per-operator opt-in. Cycle 8 is read-only.

Composes with:
  - R219 gpu-watch + R220 network status + R221 cpu-mode + R222
    fs-insights — same operator-card UX
  - The future Z-1 dashboard's "Storage" tab consumes the JSON
  - The future Z-6 autohealth notifier flags degraded arrays

Exit codes:
  0  every array reports healthy (or no arrays present)
  1  at least one array is degraded / rebuilding / has failed slot
  2  usage error / mdadm absent on a host that DOES carry md arrays
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# --------------------------------------------------------- /proc/mdstat


def parse_mdstat(text: str) -> list[dict[str, Any]]:
    """Parse /proc/mdstat into per-array rows.

    Format (kernel-documented):

      Personalities : [raid1] [raid0] [linear]
      md0 : active raid1 sda1[0] sdb1[1]
            487168 blocks super 1.2 [2/2] [UU]

      md1 : active raid1 sdc1[0] sdd1[1] (F)
            1953382400 blocks super 1.2 [2/1] [_U]
            [===>.................]  recovery = 18.5% (361580160/1953382400) ...
            bitmap: 12/15 pages [48KB], 65536KB chunk

      unused devices: <none>
    """
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            if current is not None:
                rows.append(current)
                current = None
            continue
        if line.startswith("Personalities") or line.startswith("unused devices"):
            continue
        # Array header: `md0 : active raid1 sda1[0] sdb1[1]`
        if not line.startswith(" "):
            parts = line.split()
            if len(parts) < 3 or parts[1] != ":":
                continue
            name = parts[0]
            state = parts[2]  # active / inactive
            level = parts[3] if len(parts) > 3 else "unknown"
            members = []
            for tok in parts[4:]:
                # `sda1[0]` or `sda1[0](F)` or `sda1[0](S)`
                bracket = tok.find("[")
                if bracket == -1:
                    continue
                dev = tok[:bracket]
                flags = tok[bracket:]
                role: str = "active"
                if "(F)" in flags:
                    role = "failed"
                elif "(S)" in flags:
                    role = "spare"
                elif "(R)" in flags:
                    role = "replacement"
                members.append({"device": dev, "role": role})
            current = {
                "name": name,
                "state": state,
                "level": level,
                "members": members,
                "bracket_state": None,  # filled by second line
                "size_blocks": None,
                "rebuild_pct": None,
                "rebuild_op": None,
                "bitmap": None,
            }
            continue
        # Continuation lines (indented).
        if current is None:
            continue
        s = line.strip()
        if "blocks" in s and "[" in s and "]" in s:
            # `487168 blocks super 1.2 [2/2] [UU]`
            words = s.split()
            try:
                current["size_blocks"] = int(words[0])
            except ValueError:
                pass
            # [N/M] member count + [U/_] slot map
            bracket_state = None
            for w in words:
                if w.startswith("[") and w.endswith("]"):
                    bracket_state = w  # keep last one (slot map)
            current["bracket_state"] = bracket_state
        elif "recovery" in s or "resync" in s or "reshape" in s or "check" in s:
            # `[===>.....] recovery = 18.5% ...`
            for tok in s.split():
                if tok.endswith("%"):
                    try:
                        current["rebuild_pct"] = float(tok.rstrip("%"))
                    except ValueError:
                        pass
                    break
            for op_token in ("recovery", "resync", "reshape", "check"):
                if op_token in s:
                    current["rebuild_op"] = op_token
                    break
        elif s.startswith("bitmap:"):
            current["bitmap"] = s
    if current is not None:
        rows.append(current)
    return rows


def array_health(row: dict[str, Any]) -> str:
    """Return `ok` / `rebuilding` / `degraded` / `failed`."""
    if row["rebuild_pct"] is not None:
        return "rebuilding"
    if any(m["role"] == "failed" for m in row["members"]):
        return "failed"
    # Bracket state like [2/1] [_U] — second word is slot map; if
    # any `_` is present a slot is missing.
    bracket = row.get("bracket_state") or ""
    if bracket.startswith("[") and "_" in bracket:
        return "degraded"
    return "ok"


def read_mdstat(path: str = "/proc/mdstat") -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        return parse_mdstat(p.read_text())
    except OSError:
        return []


# --------------------------------------------------------- detail subcmd


def mdadm_detail(name: str) -> str | None:
    if not shutil.which("mdadm"):
        return None
    try:
        r = subprocess.run(
            ["mdadm", "--detail", f"/dev/{name}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


# --------------------------------------------------------- rendering


HEALTH_GLYPH = {
    "ok": "✓",
    "rebuilding": "↻",
    "degraded": "⚠",
    "failed": "✗",
}


def render_status(arrays: list[dict[str, Any]]) -> str:
    lines = ["── R223 sovereign-os raid status (SDD-026 Z-9) ──"]
    if not arrays:
        lines.append("  (no md arrays present on this host)")
        return "\n".join(lines) + "\n"
    for a in arrays:
        h = array_health(a)
        glyph = HEALTH_GLYPH.get(h, "?")
        members_str = " ".join(
            f"{m['device']}({m['role'][:1].upper()})"
            for m in a["members"]
        )
        lines.append(
            f"  {glyph} {a['name']:<6} {a['level']:<8} state={a['state']:<8} "
            f"health={h:<11} members=[{members_str}]"
        )
        if a.get("bracket_state"):
            lines.append(f"      slot-map: {a['bracket_state']}")
        if a["rebuild_pct"] is not None:
            lines.append(
                f"      → {a['rebuild_op']}: {a['rebuild_pct']:.1f}% complete"
            )
    return "\n".join(lines) + "\n"


def cmd_status(json_out: bool, mdstat_path: str) -> int:
    arrays = read_mdstat(mdstat_path)
    healths = [array_health(a) for a in arrays]
    has_attention = any(h != "ok" for h in healths)
    if json_out:
        out = {
            "arrays": [
                {**a, "health": array_health(a)}
                for a in arrays
            ],
            "count": len(arrays),
            "attention_needed": has_attention,
        }
        print(json.dumps(out, indent=2))
    else:
        sys.stdout.write(render_status(arrays))
    return 1 if has_attention else 0


def cmd_detail(name: str | None, all_arrays: bool, json_out: bool, mdstat_path: str) -> int:
    arrays = read_mdstat(mdstat_path)
    if not arrays:
        if json_out:
            print(json.dumps({"arrays": [], "note": "no md arrays present"}))
        else:
            print("(no md arrays present on this host)")
        return 0
    selected = arrays if all_arrays else [a for a in arrays if a["name"] == name]
    if not selected:
        print(f"ERROR no array named {name!r}; arrays present: {[a['name'] for a in arrays]}",
              file=sys.stderr)
        return 2
    out: list[dict[str, Any]] = []
    for a in selected:
        detail_text = mdadm_detail(a["name"])
        out.append({
            **a,
            "health": array_health(a),
            "mdadm_detail": detail_text,
        })
    if json_out:
        print(json.dumps({"arrays": out}, indent=2))
        return 0
    for entry in out:
        print(f"── {entry['name']} (level={entry['level']} health={entry['health']}) ──")
        if entry["mdadm_detail"]:
            print(entry["mdadm_detail"])
        else:
            print("  (mdadm --detail unavailable — mdadm absent or array unreadable)")
        print()
    return 0


# --------------------------------------------------------- entrypoint


def main() -> int:
    p = argparse.ArgumentParser(description="R223 (SDD-026 Z-9) — software RAID surface.")
    sub = p.add_subparsers(dest="action", required=True)
    p_st = sub.add_parser("status", help="compact list of every md array")
    p_st.add_argument("--json", action="store_true")
    p_st.add_argument("--mdstat-path", default="/proc/mdstat",
                      help=argparse.SUPPRESS)
    p_dt = sub.add_parser("detail", help="mdadm --detail for one (or --all) array(s)")
    p_dt.add_argument("name", nargs="?", help="array name (e.g. md0); use --all to dump every array")
    p_dt.add_argument("--all", action="store_true")
    p_dt.add_argument("--json", action="store_true")
    p_dt.add_argument("--mdstat-path", default="/proc/mdstat",
                      help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.action == "status":
        return cmd_status(args.json, args.mdstat_path)
    if args.action == "detail":
        if not args.all and not args.name:
            print("ERROR detail requires <name> or --all", file=sys.stderr)
            return 2
        return cmd_detail(args.name, args.all, args.json, args.mdstat_path)
    return 2


if __name__ == "__main__":
    sys.exit(main())
