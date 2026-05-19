#!/usr/bin/env python3
"""scripts/hardware/cpu-isolation.py — R557 (E11.M20) CPU isolation cmdline.

Operator §1g (verbatim, sacrosanct):
  "sustained-burst / peak-inference" / "dedicated to AI inference Mode"

R554 (IRQ affinity) is necessary but not sufficient for true inference-
core isolation. IRQ pinning keeps hardware interrupts off the inference
cores, but the kernel scheduler is still free to migrate other user-
space tasks onto them, and the periodic scheduling tick + RCU
callbacks still run there. For sub-millisecond synchronous decode
budgets the trifecta is:

  isolcpus=<set>     Remove these CPUs from the scheduler's general
                     load-balance pool. Tasks land on them ONLY when
                     explicitly affined via taskset/cgroup.

  nohz_full=<set>    Disable the periodic scheduler tick on these
                     CPUs when only one task is runnable — the
                     dyntick / "full nohz" mode. Removes the ~1kHz
                     tick interrupts that would otherwise eat ~10µs
                     each cycle.

  rcu_nocbs=<set>    Offload RCU callback processing OFF these CPUs
                     onto a dedicated kthread on the housekeeping
                     CPUs. Without this, RCU callbacks can run on
                     isolated cores and spike latency.

The three sets MUST match for the isolation to work properly —
mismatch is the most common operator footgun (e.g. isolcpus=2-7 but
nohz_full=2-3 leaves cores 4-7 with periodic ticks). R557 computes
the trifecta from one operator input.

R557 NEVER edits GRUB — that's the operator-signed sovereignty
boundary (per R552 hugepages-sizer gigantic-cmdline pattern). The
fragment is emitted to /etc/sovereign-os/cpu-isolation.cmdline for
the operator to merge into their bootloader on their own terms.

Verbs:
  show / status   — print current /proc/cmdline isolation params +
                    online CPU count + suggested split.
  list-cpus       — emit online CPU list + topology snippets.
  recommend       — given --inference-cpus N-M, emit the trifecta
                    cmdline fragment (read-only).
  emit-cmdline    — write the fragment to
                    /etc/sovereign-os/cpu-isolation.cmdline (or
                    --target). Requires root for the default path.

Read-mostly philosophy: show/list-cpus/recommend NEVER write.

Exit codes:
  0  ok
  1  emit-cmdline write failure
  2  usage / not-root for default path / bad CPU spec / no CPUs online
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUT = Path("/etc/sovereign-os/cpu-isolation.cmdline")
PROC_CMDLINE = Path("/proc/cmdline")


# ── Probes ──────────────────────────────────────────────────────────


def online_cpus() -> list[int]:
    """Return list of online CPU indices, sorted."""
    p = Path("/sys/devices/system/cpu/online")
    if not p.is_file():
        # Fallback to /proc/cpuinfo count
        return _from_cpuinfo()
    try:
        return parse_cpu_list(p.read_text().strip())
    except (OSError, ValueError):
        return _from_cpuinfo()


def _from_cpuinfo() -> list[int]:
    p = Path("/proc/cpuinfo")
    if not p.is_file():
        return []
    out: list[int] = []
    try:
        for line in p.read_text().splitlines():
            if line.startswith("processor"):
                _, _, v = line.partition(":")
                try:
                    out.append(int(v.strip()))
                except ValueError:
                    pass
    except OSError:
        return []
    return sorted(set(out))


def proc_cmdline() -> str:
    try:
        return PROC_CMDLINE.read_text().strip()
    except OSError:
        return ""


def parse_cmdline_param(cmdline: str, key: str) -> str | None:
    m = re.search(rf"\b{re.escape(key)}=(\S+)", cmdline)
    return m.group(1) if m else None


def cmdline_isolation_state(cmdline: str) -> dict[str, str | None]:
    return {
        "isolcpus": parse_cmdline_param(cmdline, "isolcpus"),
        "nohz_full": parse_cmdline_param(cmdline, "nohz_full"),
        "rcu_nocbs": parse_cmdline_param(cmdline, "rcu_nocbs"),
    }


# ── CPU list parsing ────────────────────────────────────────────────


def parse_cpu_list(spec: str) -> list[int]:
    """Parse '0,2-4,7' → [0,2,3,4,7]. Strict — raises ValueError on
    malformed input."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def cpu_list_repr(cpus: list[int]) -> str:
    if not cpus:
        return ""
    cpus = sorted(set(cpus))
    runs: list[tuple[int, int]] = []
    start = prev = cpus[0]
    for c in cpus[1:]:
        if c == prev + 1:
            prev = c
            continue
        runs.append((start, prev))
        start = prev = c
    runs.append((start, prev))
    return ",".join(
        (str(a) if a == b else f"{a}-{b}") for a, b in runs
    )


# ── Recommendation ──────────────────────────────────────────────────


def recommend(inference_cpus: list[int]) -> dict[str, Any]:
    online = online_cpus()
    if not online:
        return {
            "online_count": 0,
            "error": "no online CPUs detected",
        }
    # Sanity: every inference CPU must actually be online.
    invalid = [c for c in inference_cpus if c not in online]
    if invalid:
        return {
            "online_count": len(online),
            "online": online,
            "inference_cpus": inference_cpus,
            "error": f"inference CPUs not online: {invalid}",
        }
    if len(inference_cpus) >= len(online):
        return {
            "online_count": len(online),
            "inference_cpus": inference_cpus,
            "error": "must leave at least one CPU for housekeeping",
        }
    housekeeping = [c for c in online if c not in set(inference_cpus)]
    inf_repr = cpu_list_repr(inference_cpus)
    hk_repr = cpu_list_repr(housekeeping)
    fragment = (
        f"isolcpus={inf_repr} nohz_full={inf_repr} rcu_nocbs={inf_repr}"
    )
    return {
        "online_count": len(online),
        "online": online,
        "inference_cpus": inference_cpus,
        "inference_list": inf_repr,
        "housekeeping_cpus": housekeeping,
        "housekeeping_list": hk_repr,
        "cmdline_fragment": fragment,
        "params": {
            "isolcpus": inf_repr,
            "nohz_full": inf_repr,
            "rcu_nocbs": inf_repr,
        },
    }


# ── Emit cmdline fragment ───────────────────────────────────────────


def emit_cmdline(rec: dict[str, Any], target: Path,
                 default_path: bool) -> dict[str, Any]:
    if "error" in rec:
        return {"ok": False, "error": rec["error"]}
    if default_path and os.geteuid() != 0:
        return {"ok": False, "error": "writing to /etc requires root"}
    body = (
        "# R557 (E11.M20) — sovereign-os cpu-isolation cmdline\n"
        "# Generated for inference-core dedication; merge into the\n"
        "# bootloader cmdline of your choice (GRUB / systemd-boot /\n"
        "# rEFInd). NEVER edit GRUB from this script — operator-\n"
        "# signed sovereignty boundary.\n"
        f"{rec['cmdline_fragment']}\n"
    )
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "wrote": str(target), "bytes": len(body)}


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="cpu-isolation",
        description="CPU isolation cmdline emitter (R557 / E11.M20).",
    )
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_list = sub.add_parser("list-cpus")
    sp_list.add_argument("--json", action="store_true", dest="json_sub")
    sp_rec = sub.add_parser("recommend")
    sp_rec.add_argument("--inference-cpus", required=True)
    sp_rec.add_argument("--json", action="store_true", dest="json_sub")
    sp_emit = sub.add_parser("emit-cmdline")
    sp_emit.add_argument("--inference-cpus", required=True)
    sp_emit.add_argument("--target", type=Path, default=DEFAULT_OUT)
    sp_emit.add_argument("--json", action="store_true", dest="json_sub")
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("show", "status"):
        online = online_cpus()
        cmdline = proc_cmdline()
        state = {
            "online_count": len(online),
            "online_list": cpu_list_repr(online),
            "cmdline": cmdline,
            "current": cmdline_isolation_state(cmdline),
        }
        if json_out:
            print(json.dumps(state, indent=2))
        else:
            print(f"── sovereign-os CPU isolation (R557 / E11.M20) ──")
            print(f"  online CPUs : {state['online_list']} "
                  f"({state['online_count']} total)")
            cur = state["current"]
            for k in ("isolcpus", "nohz_full", "rcu_nocbs"):
                print(f"  {k:11s}: {cur[k] or '(unset)'}")
            if (cur["isolcpus"] != cur["nohz_full"]
                    or cur["nohz_full"] != cur["rcu_nocbs"]):
                if any(cur.values()):
                    print("  WARNING: isolcpus/nohz_full/rcu_nocbs are "
                          "MISMATCHED — fix via emit-cmdline.")
        return 0

    if verb == "list-cpus":
        online = online_cpus()
        if json_out:
            print(json.dumps({
                "online": online,
                "online_list": cpu_list_repr(online),
                "online_count": len(online),
            }, indent=2))
        else:
            print(f"online CPUs: {cpu_list_repr(online)} "
                  f"({len(online)} total)")
        return 0

    if verb == "recommend":
        try:
            inf = parse_cpu_list(args.inference_cpus)
        except ValueError as e:
            print(f"[cpu-isolation] bad --inference-cpus: {e}",
                  file=sys.stderr)
            return 2
        rec = recommend(inf)
        if json_out:
            print(json.dumps(rec, indent=2))
        else:
            if "error" in rec:
                print(f"ERROR: {rec['error']}")
                return 2
            print(f"── R557 cpu-isolation recommendation ──")
            print(f"  inference   : {rec['inference_list']}")
            print(f"  housekeeping: {rec['housekeeping_list']}")
            print(f"  cmdline fragment:")
            print(f"    {rec['cmdline_fragment']}")
        return 0 if "error" not in rec else 2

    if verb == "emit-cmdline":
        try:
            inf = parse_cpu_list(args.inference_cpus)
        except ValueError as e:
            print(f"[cpu-isolation] bad --inference-cpus: {e}",
                  file=sys.stderr)
            return 2
        rec = recommend(inf)
        if "error" in rec:
            print(f"[cpu-isolation] {rec['error']}", file=sys.stderr)
            return 2
        result = emit_cmdline(
            rec, args.target, default_path=(args.target == DEFAULT_OUT))
        if json_out:
            print(json.dumps({"recommendation": rec, "emit": result},
                              indent=2))
        else:
            if result["ok"]:
                print(f"[cpu-isolation] wrote {result['wrote']} "
                      f"({result['bytes']}B)")
                print(f"  fragment: {rec['cmdline_fragment']}")
                print("  NEXT: merge into your bootloader cmdline. "
                      "R557 never touches GRUB.")
            else:
                print(f"[cpu-isolation] emit failed: {result['error']}",
                      file=sys.stderr)
        return 0 if result["ok"] else 1

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
