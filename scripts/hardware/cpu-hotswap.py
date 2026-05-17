#!/usr/bin/env python3
"""scripts/hardware/cpu-hotswap.py — R307 (E1.M31).

Operator-named (§1b mandate row, verbatim): "Hotswap, CPU mode and
option(s)". Closes E1.M31 — fills the stop-hook-flagged "no hotswap
CPU mode detection" gap.

R221 (cpu-mode) + R230 (auto-recommender, E1.M10) ship the EMIT side
(operator can pick + apply modes). R307 ships the DETECT side: parses
/sys/devices/system/cpu/cpu*/cpufreq/* to surface per-CPU CURRENT
state + available transitions (which governors are loaded; which EPP
profiles the active driver supports).

CLI:
  cpu-hotswap.py status     [--config P] [--json|--human]
                        all CPUs with current governor / EPP / driver
  cpu-hotswap.py per-cpu    [--cpu N] [--config P] [--json|--human]
                        single CPU detail or all
  cpu-hotswap.py transitions [--config P] [--json|--human]
                        what modes can the operator swap TO from here?
  cpu-hotswap.py swap-hint  <mode> [--config P] [--json|--human]
                        operator-runnable command to swap to <mode>

Modes catalog (per operator-named §1b "options"):
  performance       max boost; sustained; AI-training workload
  schedutil         (default) load-aware EAS; balanced
  powersave         floor frequency; idle / batt
  ondemand          legacy; rapid up/down

EPP (Intel/AMD HW perf preference, when driver supports):
  performance / balance_performance / balance_power / power

Operator-overlay (R283/SDD-030): /etc/sovereign-os/cpu-hotswap.toml
adds custom mode catalogs.

Exit codes:
  0  rendered (all CPUs on operator-pinned mode OR no pin)
  1  ≥1 CPU off the operator-pinned mode (drift)
  2  /sys/devices/system/cpu/* unreadable
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R307"
SDD_VECTOR = "E1.M31"


DEFAULTS = {
    # When pinned_mode is set, status verb compares each CPU's current
    # governor against this name. Drift → rc=1.
    "pinned_mode": "",   # "" = no pin, all modes accepted
    # When pinned_epp is set, status verb compares CPU's EPP too.
    "pinned_epp": "",
}


MODE_CATALOG: list[dict[str, Any]] = [
    {
        "mode": "performance",
        "axis": "governor",
        "rationale": "Max sustained boost — ideal for AI training "
                     "(GPU-bound, CPU contention-free) where CPU "
                     "frequency variance hurts kernel ringbuffer ops.",
        "operator_caveat": "Sustained higher idle wattage; pair with "
                           "R296 thermal-oc-budget to verify.",
    },
    {
        "mode": "schedutil",
        "axis": "governor",
        "rationale": "Load-aware EAS — balanced; modern Linux default. "
                     "Operator's safe baseline.",
        "operator_caveat": None,
    },
    {
        "mode": "powersave",
        "axis": "governor",
        "rationale": "Floor frequency — battery-backed or idle hours; "
                     "minimizes wattage at cost of latency.",
        "operator_caveat": "AI inference latency suffers; only when host "
                           "is genuinely idle or on UPS battery.",
    },
    {
        "mode": "ondemand",
        "axis": "governor",
        "rationale": "Legacy rapid scaler. Pre-schedutil baseline.",
        "operator_caveat": "Operator usually prefers schedutil today.",
    },
    {
        "mode": "performance",
        "axis": "epp",
        "rationale": "EPP performance — driver tells HW 'optimize for "
                     "perf'. Subtly different from governor performance.",
        "operator_caveat": "Pairs with intel_pstate / amd-pstate driver.",
    },
    {
        "mode": "balance_performance",
        "axis": "epp",
        "rationale": "EPP balance_performance — operator-pinned baseline "
                     "for the SAIN-01 mixed workload.",
        "operator_caveat": None,
    },
    {
        "mode": "balance_power",
        "axis": "epp",
        "rationale": "EPP balance_power — favors power efficiency "
                     "without dropping to pure powersave.",
        "operator_caveat": None,
    },
    {
        "mode": "power",
        "axis": "epp",
        "rationale": "EPP power — driver optimizes for lowest power. "
                     "Battery-backed runtime.",
        "operator_caveat": "Same caveat as governor=powersave.",
    },
]


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def probe_cpus() -> list[dict[str, Any]]:
    """Walk /sys/devices/system/cpu/cpu*/cpufreq/ and return per-CPU state."""
    base = Path("/sys/devices/system/cpu")
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if not (name.startswith("cpu") and name[3:].isdigit()):
            continue
        cpu_idx = int(name[3:])
        cf = entry / "cpufreq"
        if not cf.is_dir():
            continue
        gov = _read(cf / "scaling_governor")
        epp = _read(cf / "energy_performance_preference")
        driver = _read(cf / "scaling_driver")
        cur_freq = _read(cf / "scaling_cur_freq")
        max_freq = _read(cf / "scaling_max_freq")
        min_freq = _read(cf / "scaling_min_freq")
        govs_available = _read(cf / "scaling_available_governors")
        epp_available = _read(cf / "energy_performance_available_preferences")
        out.append({
            "cpu": cpu_idx,
            "governor": gov,
            "epp": epp,
            "driver": driver,
            "freq_cur_khz": int(cur_freq) if cur_freq and cur_freq.isdigit() else None,
            "freq_max_khz": int(max_freq) if max_freq and max_freq.isdigit() else None,
            "freq_min_khz": int(min_freq) if min_freq and min_freq.isdigit() else None,
            "governors_available": govs_available.split() if govs_available else [],
            "epp_available": epp_available.split() if epp_available else [],
        })
    return out


def derive_transitions(cpus: list[dict]) -> dict[str, Any]:
    """Cross-cut: what governor/EPP options are common across all CPUs?"""
    if not cpus:
        return {"governors_common": [], "epp_common": [], "drivers": []}
    govs = set(cpus[0]["governors_available"] or [])
    epp = set(cpus[0]["epp_available"] or [])
    drivers = {c["driver"] for c in cpus if c["driver"]}
    for c in cpus[1:]:
        govs &= set(c["governors_available"] or [])
        epp &= set(c["epp_available"] or [])
    return {
        "governors_common": sorted(govs),
        "epp_common": sorted(epp),
        "drivers": sorted(drivers),
    }


def derive_verdict(cpus: list[dict], cfg: dict) -> dict[str, Any]:
    if not cpus:
        return {"verdict": "no-cpus", "rc": 2,
                "message": "no /sys/devices/system/cpu/cpu*/cpufreq/* "
                           "entries found"}
    pinned_mode = cfg["pinned_mode"]
    pinned_epp = cfg["pinned_epp"]
    if not pinned_mode and not pinned_epp:
        # No operator pin → no drift to detect.
        return {"verdict": "no-pin", "rc": 0,
                "message": "no operator pin set; all states accepted"}
    drift = []
    for c in cpus:
        if pinned_mode and c["governor"] != pinned_mode:
            drift.append({"cpu": c["cpu"], "field": "governor",
                          "current": c["governor"], "pinned": pinned_mode})
        if pinned_epp and c["epp"] and c["epp"] != pinned_epp:
            drift.append({"cpu": c["cpu"], "field": "epp",
                          "current": c["epp"], "pinned": pinned_epp})
    if drift:
        return {"verdict": "drift", "rc": 1,
                "drift": drift,
                "message": f"{len(drift)} CPU(s) off operator-pinned mode"}
    return {"verdict": "matches-pin", "rc": 0,
            "message": "all CPUs match operator pin"}


def swap_hint(mode: str, scope: str) -> dict[str, Any]:
    """Operator-runnable command for swapping to <mode>."""
    if scope == "governor":
        return {
            "command": (f"echo {mode} | sudo tee "
                        f"/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"),
            "alt_persistent": (f"sudo cpupower frequency-set --governor {mode}"),
            "note": "First form is non-persistent (lost on reboot). "
                    "Use cpupower OR a systemd unit for persistence.",
        }
    if scope == "epp":
        return {
            "command": (f"echo {mode} | sudo tee "
                        f"/sys/devices/system/cpu/cpu*/cpufreq/"
                        f"energy_performance_preference"),
            "alt_persistent": None,
            "note": "EPP changes don't have a cpupower convenience; "
                    "persist via systemd or /etc/default/grub.",
        }
    return {"command": None, "note": f"unknown scope: {scope}"}


def build_report(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("cpu-hotswap", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    cpus = probe_cpus()
    transitions = derive_transitions(cpus)
    verdict = derive_verdict(cpus, cfg)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "cpu_count": len(cpus),
        "cpus": cpus,
        "transitions": transitions,
        "verdict": verdict["verdict"],
        "rc": verdict["rc"],
        "message": verdict["message"],
        "drift": verdict.get("drift", []),
        "modes_catalog": MODE_CATALOG,
        "overlay": meta,
    }


def render_status_human(doc: dict) -> str:
    lines = ["── R307 sovereign-os CPU hotswap mode detection (E1.M31) ──"]
    lines.append(f"  cpu_count: {doc['cpu_count']}")
    lines.append(f"  verdict:   {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  message:   {doc['message']}")
    lines.append(f"  drivers:   {', '.join(doc['transitions']['drivers']) or '(none)'}")
    lines.append(f"  governors_common: {doc['transitions']['governors_common']}")
    lines.append(f"  epp_common:       {doc['transitions']['epp_common']}")
    lines.append("")
    if doc["cpus"]:
        # Show first 4 CPUs (or all if fewer).
        for c in doc["cpus"][:8]:
            lines.append(f"  cpu{c['cpu']:>3}  gov={c['governor']:<12} "
                         f"epp={c['epp'] or '-':<22}  "
                         f"freq {c['freq_cur_khz']}/{c['freq_max_khz']} kHz")
        if len(doc["cpus"]) > 8:
            lines.append(f"  ... and {len(doc['cpus']) - 8} more CPUs")
    if doc["drift"]:
        lines.append("")
        lines.append(f"  drift:")
        for d in doc["drift"]:
            lines.append(f"    cpu{d['cpu']} {d['field']}: {d['current']} != {d['pinned']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cpu-hotswap.py")
    sub = p.add_subparsers(dest="verb", required=True)

    for verb in ("status", "transitions"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    pcpu = sub.add_parser("per-cpu")
    pcpu.add_argument("--cpu", type=int, help="restrict to one CPU index")
    pcpu.add_argument("--config", type=Path)
    fcpu = pcpu.add_mutually_exclusive_group()
    fcpu.add_argument("--json", dest="fmt", action="store_const", const="json")
    fcpu.add_argument("--human", dest="fmt", action="store_const", const="human")
    pcpu.set_defaults(fmt="json")

    psh = sub.add_parser("swap-hint")
    psh.add_argument("mode")
    psh.add_argument("--scope", choices=("governor", "epp"), default="governor")
    psh.add_argument("--config", type=Path)
    fsh = psh.add_mutually_exclusive_group()
    fsh.add_argument("--json", dest="fmt", action="store_const", const="json")
    fsh.add_argument("--human", dest="fmt", action="store_const", const="human")
    psh.set_defaults(fmt="json")

    args = p.parse_args(argv)

    if args.verb == "swap-hint":
        # No overlay needed for swap-hint; pure mode → command mapping.
        hint = swap_hint(args.mode, args.scope)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mode": args.mode,
                "scope": args.scope,
                "command": hint.get("command"),
                "alt_persistent": hint.get("alt_persistent"),
                "note": hint.get("note"),
            }, indent=2))
        else:
            print(f"── R307 swap-hint: {args.scope}={args.mode} (E1.M31) ──")
            print(f"  command:        {hint.get('command')}")
            if hint.get("alt_persistent"):
                print(f"  alt persistent: {hint['alt_persistent']}")
            print(f"  note:           {hint.get('note')}")
        return 0

    doc = build_report(args.config)

    if args.verb == "transitions":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "cpu_count": doc["cpu_count"],
                "transitions": doc["transitions"],
                "modes_catalog": MODE_CATALOG,
                "overlay": doc["overlay"],
            }, indent=2))
        else:
            print(f"── R307 transitions (E1.M31) ──")
            print(f"  drivers:          {', '.join(doc['transitions']['drivers'])}")
            print(f"  governors common: {doc['transitions']['governors_common']}")
            print(f"  epp common:       {doc['transitions']['epp_common']}")
        return 0

    if args.verb == "per-cpu":
        cpus = doc["cpus"]
        if args.cpu is not None:
            cpus = [c for c in cpus if c["cpu"] == args.cpu]
            if not cpus:
                print(json.dumps({
                    "error": f"unknown CPU: {args.cpu}",
                    "known_cpus": [c["cpu"] for c in doc["cpus"]],
                    "round": ROUND,
                }, indent=2), file=sys.stderr)
                return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "filter_cpu": args.cpu,
                "cpus": cpus,
                "overlay": doc["overlay"],
            }, indent=2))
        else:
            for c in cpus:
                print(f"  cpu{c['cpu']}  gov={c['governor']}  epp={c['epp']}  driver={c['driver']}")
        return 0

    # status (default)
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_status_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
