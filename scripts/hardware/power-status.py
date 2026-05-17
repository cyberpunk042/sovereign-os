#!/usr/bin/env python3
"""scripts/hardware/power-status.py — R252 (SDD-026 Z-18 new vector).

Operator-named (verbatim, 2026-05-17 expansion): "Adapting / Considering
the given PSU (probably not detectable ?) wattage and rating ? (me: be
Quiet! Dark Power Pro 13 1600W Power Supply | ATX 3.1 Compliant | 80
Plus Titanium) [...] Then there is the PSU/APC integration with the
power management and the scheduled shutdown when battery reach a
certain point as one default profile."

Opens Z-18: power-supply / UPS / wattage budget surface.

PSU detection (operator-supplied, OS can't probe ATX rails directly):
operators declare their PSU in /etc/sovereign-os/power.toml. The
script computes the wattage budget = PSU rated W × derating factor
(default 0.85 for sustained loads) and reports it alongside the live
power draw aggregate from R219 GPU watch metrics + estimated CPU TDP.

UPS detection (live, via apcupsd or NUT):
  apcaccess              when apcupsd is installed + apcupsd.conf points
                         at a UPS (APC-branded only)
  upsc <ups>@localhost   when nut is installed (any NUT-compatible UPS)

Battery thresholds drive the operator's "schedule graceful shutdown
when battery hits N%" profile. Hook surface (R252 ships the probe; a
follow-up round wires the actual systemd Conditional + shutdown
sequence).

CLI:
  power-status.py psu [--json]        operator-declared PSU + budget
  power-status.py ups [--json]        live UPS state (apc or nut)
  power-status.py budget [--json]     PSU rated W vs draw aggregate
  power-status.py advisories [--json] graceful-shutdown thresholds

Exit codes:
  0  rendered
  1  battery below operator-set critical-shutdown threshold
  2  usage error
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

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/power.toml")
DEV_CONFIG = REPO_ROOT / "config" / "power.toml.example"
DEFAULT_METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR",
        "/var/lib/node_exporter/textfile_collector",
    )
)


def resolve_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("SOVEREIGN_OS_POWER_CONFIG")
    if env:
        return Path(env)
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"_source": "(missing)"}
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    doc["_source"] = str(path)
    return doc


def _read_prom_lines(name: str) -> list[str]:
    p = DEFAULT_METRICS_DIR / name
    if not p.exists():
        return []
    try:
        return p.read_text(errors="replace").splitlines()
    except OSError:
        return []


def _sum_metric(lines: list[str], prefix: str) -> float:
    total = 0.0
    for line in lines:
        if line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        try:
            total += float(parts[1])
        except ValueError:
            continue
    return total


def detect_ups_apc() -> dict[str, Any] | None:
    """apcaccess status — APC UPS via apcupsd."""
    if not shutil.which("apcaccess"):
        return None
    try:
        r = subprocess.run(
            ["apcaccess", "status"], capture_output=True, text=True, timeout=5, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    fields: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    if not fields:
        return None
    # Common fields apcaccess exposes:
    #   STATUS, BCHARGE, TIMELEFT, MBATTCHG, NOMPOWER, LOADPCT, ITEMP
    def _f(k: str) -> float | None:
        v = fields.get(k, "")
        try:
            return float(v.split()[0])
        except (ValueError, IndexError):
            return None

    return {
        "source": "apcupsd",
        "model": fields.get("MODEL"),
        "status": fields.get("STATUS"),
        "battery_charge_pct": _f("BCHARGE"),
        "time_left_minutes": _f("TIMELEFT"),
        "min_battery_charge_pct": _f("MBATTCHG"),
        "nominal_power_watts": _f("NOMPOWER"),
        "load_pct": _f("LOADPCT"),
        "internal_temp_c": _f("ITEMP"),
        "raw_status": dict(fields),
    }


def detect_ups_nut() -> dict[str, Any] | None:
    """upsc <ups>@localhost — NUT-compatible UPS."""
    if not shutil.which("upsc"):
        return None
    # `upsc -l` lists configured devices.
    try:
        list_r = subprocess.run(
            ["upsc", "-l"], capture_output=True, text=True, timeout=5, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if list_r.returncode != 0 or not list_r.stdout.strip():
        return None
    ups_id = list_r.stdout.strip().splitlines()[0].strip()
    if not ups_id:
        return None
    try:
        r = subprocess.run(
            ["upsc", f"{ups_id}@localhost"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    fields: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    if not fields:
        return None

    def _f(k: str) -> float | None:
        v = fields.get(k, "")
        try:
            return float(v)
        except ValueError:
            return None

    return {
        "source": "nut",
        "ups_id": ups_id,
        "model": fields.get("ups.model"),
        "status": fields.get("ups.status"),
        "battery_charge_pct": _f("battery.charge"),
        "time_left_minutes": (_f("battery.runtime") or 0) / 60.0
            if _f("battery.runtime") else None,
        "nominal_power_watts": _f("ups.realpower.nominal"),
        "load_pct": _f("ups.load"),
        "raw_status": dict(fields),
    }


def detect_ups() -> dict[str, Any] | None:
    return detect_ups_apc() or detect_ups_nut()


def cmd_psu(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    psu = cfg.get("psu") or {}
    derating = float(cfg.get("derating", 0.85))
    rated_w = float(psu.get("rated_watts", 0))
    budget_w = rated_w * derating
    out = {
        "round": "R252",
        "vector": "SDD-026 Z-18 (psu)",
        "config_source": cfg.get("_source"),
        "psu": {
            "model": psu.get("model"),
            "rated_watts": rated_w if rated_w > 0 else None,
            "rating": psu.get("rating"),
            "atx_revision": psu.get("atx_revision"),
            "overclock_mode_supported": psu.get("overclock_mode_supported"),
            "overclock_mode_enabled": psu.get("overclock_mode_enabled"),
        },
        "derating_factor": derating,
        "sustained_budget_watts": budget_w if rated_w > 0 else None,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R252 sovereign-os power-status psu (SDD-026 Z-18) ──")
    print(f"  config:    {cfg.get('_source')}")
    print(f"  model:     {psu.get('model') or '(operator must declare)'}")
    if rated_w > 0:
        print(f"  rated:     {rated_w:.0f} W ({psu.get('rating') or '?'})")
        print(f"  budget:    {budget_w:.0f} W (derated × {derating})")
    else:
        print(f"  rated:     (not declared; set [psu].rated_watts in config)")
    return 0


def cmd_ups(args: argparse.Namespace) -> int:
    ups = detect_ups()
    out = {
        "round": "R252",
        "vector": "SDD-026 Z-18 (ups)",
        "detected": ups is not None,
        "ups": ups,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R252 sovereign-os power-status ups ──")
    if ups is None:
        print("  (no UPS detected — install apcupsd or nut + configure to surface here)")
        return 0
    print(f"  source:    {ups.get('source')}")
    print(f"  model:     {ups.get('model')}")
    print(f"  status:    {ups.get('status')}")
    print(f"  battery:   {ups.get('battery_charge_pct')}% (time_left ≈ "
          f"{ups.get('time_left_minutes')} min)")
    print(f"  load:      {ups.get('load_pct')}%")
    if ups.get("nominal_power_watts"):
        print(f"  nominal:   {ups['nominal_power_watts']} W")
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    psu = cfg.get("psu") or {}
    rated_w = float(psu.get("rated_watts", 0))
    derating = float(cfg.get("derating", 0.85))
    # R259 (SDD-029 R259): PSU overclock mode lifts the rated-W
    # ceiling for transient spikes. When operator has flipped the
    # physical switch AND declared overclock_mode_enabled=true in
    # power.toml, the sustained budget gets the OC bonus (operator-
    # configurable, defaults to 1.10× — be Quiet! Dark Power Pro 13
    # advertises a transient bump but treats sustained as ~10% over).
    oc_supported = bool(psu.get("overclock_mode_supported"))
    oc_enabled = bool(psu.get("overclock_mode_enabled"))
    oc_multiplier = float(psu.get("overclock_multiplier", 1.10))
    if oc_supported and oc_enabled:
        effective_rated_w = rated_w * oc_multiplier
        budget_w = effective_rated_w * derating
        oc_active = True
    else:
        effective_rated_w = rated_w
        budget_w = rated_w * derating
        oc_active = False

    # Sum live GPU draw from R219 .prom file.
    gpu_lines = _read_prom_lines("sovereign-os-gpu-watch.prom")
    gpu_draw_w = _sum_metric(gpu_lines, "sovereign_os_gpu_power_draw_watts")

    # Estimate CPU TDP from config (operator-declared because there's
    # no portable userspace probe for live AMD CPU package power).
    cpu_tdp_w = float((cfg.get("cpu") or {}).get("tdp_watts", 0))

    # Drive: operator-declared other-component overhead (drives, fans).
    overhead_w = float(cfg.get("estimated_overhead_watts", 75))

    estimated_load_w = gpu_draw_w + cpu_tdp_w + overhead_w
    headroom_w = budget_w - estimated_load_w if budget_w > 0 else None
    utilization_pct = (estimated_load_w / budget_w * 100) if budget_w > 0 else None

    out = {
        "round": "R252",
        "vector": "SDD-026 Z-18 (budget)",
        "psu_rated_watts": rated_w if rated_w > 0 else None,
        "psu_sustained_budget_watts": budget_w if rated_w > 0 else None,
        # R259: OC mode metadata so dashboards distinguish "have
        # headroom because OC is on" from "have headroom because
        # we're sized larger than needed".
        "psu_overclock": {
            "supported": oc_supported,
            "enabled": oc_enabled,
            "multiplier": oc_multiplier if oc_supported else None,
            "active": oc_active,
            "effective_rated_watts": effective_rated_w if oc_active else None,
        },
        "components": {
            "gpu_draw_watts": gpu_draw_w,
            "cpu_tdp_watts_declared": cpu_tdp_w,
            "estimated_overhead_watts": overhead_w,
        },
        "estimated_load_watts": estimated_load_w,
        "headroom_watts": headroom_w,
        "utilization_pct": utilization_pct,
        "warnings": [],
    }
    if oc_supported and not oc_enabled and utilization_pct is not None and utilization_pct >= 70:
        out["warnings"].append(
            f"PSU supports overclock mode but it is DISABLED. Flip the "
            f"physical switch + set [psu] overclock_mode_enabled=true in "
            f"power.toml to lift the sustained budget by ~{round((oc_multiplier - 1) * 100)}%."
        )
    if budget_w > 0 and utilization_pct is not None:
        if utilization_pct >= 100:
            out["warnings"].append(
                f"estimated load {estimated_load_w:.0f}W EXCEEDS sustained budget "
                f"{budget_w:.0f}W — PSU may trip / age faster"
            )
        elif utilization_pct >= 85:
            out["warnings"].append(
                f"estimated load {estimated_load_w:.0f}W at {utilization_pct:.0f}% "
                "of sustained budget — consider enabling PSU overclock mode if "
                "supported, OR cap GPU power limit"
            )
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R252 sovereign-os power-status budget (SDD-026 Z-18) ──")
    if rated_w > 0:
        print(f"  PSU rated:  {rated_w:.0f} W  → sustained budget {budget_w:.0f} W")
    else:
        print(f"  PSU rated:  (operator must declare in /etc/sovereign-os/power.toml)")
    print(f"  GPU draw:   {gpu_draw_w:.0f} W (live, R219 .prom)")
    print(f"  CPU TDP:    {cpu_tdp_w:.0f} W (operator-declared)")
    print(f"  Overhead:   {overhead_w:.0f} W (drives + fans estimate)")
    print(f"  Est. load:  {estimated_load_w:.0f} W")
    if headroom_w is not None:
        print(f"  Headroom:   {headroom_w:.0f} W  ({utilization_pct:.0f}% utilization)")
    for w in out["warnings"]:
        print(f"  ⚠ {w}")
    return 0


def cmd_advisories(args: argparse.Namespace) -> int:
    cfg = load_config(resolve_config_path(args.config))
    profile = cfg.get("graceful_shutdown") or {}
    critical_pct = float(profile.get("battery_critical_pct", 15))
    runtime_min_warn_min = float(profile.get("runtime_warn_minutes", 5))
    shutdown_min_min = float(profile.get("shutdown_minutes", 2))
    ups = detect_ups()
    bat_pct = (ups or {}).get("battery_charge_pct")
    runtime = (ups or {}).get("time_left_minutes")
    out = {
        "round": "R252",
        "vector": "SDD-026 Z-18 (graceful shutdown advisories)",
        "thresholds": {
            "battery_critical_pct": critical_pct,
            "runtime_warn_minutes": runtime_min_warn_min,
            "shutdown_minutes": shutdown_min_min,
        },
        "ups_present": ups is not None,
        "live": {
            "battery_charge_pct": bat_pct,
            "time_left_minutes": runtime,
        },
        "verdict": "no-ups",
        "advisories": [],
    }
    rc = 0
    if ups is not None:
        if bat_pct is not None and bat_pct <= critical_pct:
            out["verdict"] = "critical"
            out["advisories"].append(
                f"battery at {bat_pct}% ≤ critical threshold {critical_pct}% — "
                "GRACEFUL SHUTDOWN should trigger now (this script doesn't "
                "execute it; wire to systemd via R252.future-round timer)"
            )
            rc = 1
        elif runtime is not None and runtime <= shutdown_min_min:
            out["verdict"] = "critical"
            out["advisories"].append(
                f"time_left {runtime:.1f} min ≤ shutdown threshold "
                f"{shutdown_min_min} min — shutdown should trigger"
            )
            rc = 1
        elif runtime is not None and runtime <= runtime_min_warn_min:
            out["verdict"] = "attention"
            out["advisories"].append(
                f"time_left {runtime:.1f} min — save work + prepare for "
                "shutdown"
            )
        else:
            out["verdict"] = "ok"
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R252 sovereign-os power-status advisories ──")
    print(f"  verdict:   {out['verdict']}")
    print(f"  battery_critical_pct:   {critical_pct}%")
    print(f"  runtime_warn_minutes:   {runtime_min_warn_min}")
    print(f"  shutdown_minutes:       {shutdown_min_min}")
    if ups is None:
        print(f"  (no UPS detected)")
    else:
        print(f"  live battery:           {bat_pct}%")
        print(f"  live time_left:         {runtime} min")
    for a in out["advisories"]:
        print(f"  ⚠ {a}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="power-status.py",
        description="R252 (SDD-026 Z-18) — PSU + UPS + wattage budget + graceful-shutdown advisories.",
    )
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("psu", cmd_psu, "operator-declared PSU + sustained budget"),
        ("ups", cmd_ups, "live UPS state (apcupsd / nut)"),
        ("budget", cmd_budget, "PSU rated vs estimated load"),
        ("advisories", cmd_advisories, "graceful-shutdown verdict"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
