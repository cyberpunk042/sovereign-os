#!/usr/bin/env python3
"""scripts/hardware/thermal-oc-budget.py — R296 (E2.M10).

Operator-named (§1b mandate row, verbatim, on R292/R294): "considering
XMP profile and OC profile and room for each and estimated at 100%
usage and then real time tracking and intelligence around it.
(Possibly heat too I guess)". Closes E2.M10.

Composes the three independent vantage points the operator named:

  - R172 thermal-watch       — per-sensor °C readings + warn/critical
                                breach severity
  - R292 oc-headroom         — projected 100%-usage PSU headroom
  - R294 psu-oc              — operator-declared OC-mode state +
                                effective wattage budget

…into ONE operator-pull "is your OC posture thermally + electrically
safe?" verdict. The verb is read-only — composes JSON probes; never
mutates.

Combined verdict matrix:

  thermal\\psu     headroom-safe       headroom-tight    over-budget
  -----------     -------------       --------------    ------------
  no breach       safe                psu-watch         pull-oc-now
  warn            thermal-watch       both-tight        pull-oc-now
  critical        thermal-critical    thermal-critical  pull-oc-now

`pull-oc-now` always wins — operator must drop OC profile / reduce
GPU power_limit BEFORE the next sustained-load event.

CLI:
  thermal-oc-budget.py status   [--config P] [--json|--human]
  thermal-oc-budget.py advisory [--config P] [--json|--human]
  thermal-oc-budget.py inputs   [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): `/etc/sovereign-os/thermal-oc-budget.toml`
for thermal headroom margins + verdict weights.

Exit codes:
  0  safe
  1  watch / tight (operator-pull investigate)
  2  pull-oc-now (operator-pull act-NOW)
"""
from __future__ import annotations

import argparse
import json
import subprocess
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
ROUND = "R296"
SDD_VECTOR = "E2.M10"


DEFAULTS = {
    # Headroom-from-tjmax that triggers "thermal-watch" verdict
    # (operator should investigate before OC-mode load).
    "cpu_tjmax_watch_margin_c": 10,
    # Headroom-from-tjmax that triggers "thermal-critical"
    # (operator must drop OC profile NOW).
    "cpu_tjmax_critical_margin_c": 5,
    # GPU thresholds — Blackwell PRO 6000 + Ampere 3090 both spec'd
    # for sustained ~83 °C, throttle around 88 °C.
    "gpu_temp_watch_c": 80,
    "gpu_temp_critical_c": 87,
    # Operator-pinned CPU tjmax (Zen5 9900X = 95°C per datasheet).
    # Real tjmax is queryable from MSR but requires root + arch-
    # specific code; operator-pinned is the safe fallback.
    "cpu_tjmax_c": 95,
}


# ── Sibling-probe runners (read-only; degrade gracefully) ───────────
def _run_json(rel: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / "scripts" / "hardware" / rel
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # thermal-watch returns 0/1/2 by severity, oc-headroom returns
    # 0/1/2 by verdict, psu-oc returns 0/2. All "data emitted".
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def probe_thermal() -> dict[str, Any] | None:
    return _run_json("thermal-watch.py", ["--json"])


def probe_oc_headroom() -> dict[str, Any] | None:
    return _run_json("oc-headroom.py", ["status", "--json"])


def probe_psu_oc() -> dict[str, Any] | None:
    return _run_json("psu-oc.py", ["state", "--json"])


# ── Verdict derivation ──────────────────────────────────────────────
def derive_thermal_status(t: dict | None, cfg: dict) -> dict[str, Any]:
    if t is None:
        return {"verdict": "thermal-probe-unavailable",
                "detail": "thermal-watch JSON unavailable on this host",
                "hottest_cpu_c": None, "hottest_gpu_c": None}
    sensors = t.get("sensors") or []
    cpu_sensors = [s for s in sensors if "k10temp" in (s.get("name") or "")
                   or "coretemp" in (s.get("name") or "")
                   or "tctl" in (s.get("name") or "").lower()]
    gpu_sensors = [s for s in sensors if "nvidia" in (s.get("name") or "").lower()
                   or "gpu" in (s.get("name") or "").lower()]
    def _max_c(rows):
        vals = [s.get("celsius") for s in rows
                if isinstance(s.get("celsius"), (int, float))]
        return max(vals) if vals else None
    cpu_max = _max_c(cpu_sensors)
    gpu_max = _max_c(gpu_sensors)
    cpu_tjmax = float(cfg["cpu_tjmax_c"])
    crit_m = float(cfg["cpu_tjmax_critical_margin_c"])
    watch_m = float(cfg["cpu_tjmax_watch_margin_c"])
    gpu_crit = float(cfg["gpu_temp_critical_c"])
    gpu_watch = float(cfg["gpu_temp_watch_c"])

    verdict = "no-breach"
    notes = []
    if cpu_max is not None:
        if cpu_max >= cpu_tjmax - crit_m:
            verdict = "critical"
            notes.append(f"CPU {cpu_max} °C ≥ tjmax-{crit_m} ({cpu_tjmax-crit_m} °C)")
        elif cpu_max >= cpu_tjmax - watch_m:
            verdict = "warn" if verdict == "no-breach" else verdict
            notes.append(f"CPU {cpu_max} °C ≥ tjmax-{watch_m} ({cpu_tjmax-watch_m} °C)")
    if gpu_max is not None:
        if gpu_max >= gpu_crit:
            verdict = "critical"
            notes.append(f"GPU {gpu_max} °C ≥ critical ({gpu_crit} °C)")
        elif gpu_max >= gpu_watch:
            if verdict != "critical":
                verdict = "warn"
            notes.append(f"GPU {gpu_max} °C ≥ watch ({gpu_watch} °C)")
    return {
        "verdict": verdict,
        "detail": "; ".join(notes) if notes else "all sensors within margins",
        "hottest_cpu_c": cpu_max,
        "hottest_gpu_c": gpu_max,
        "cpu_tjmax_c": cpu_tjmax,
    }


def derive_combined_verdict(thermal: dict, oc: dict | None,
                            psu_oc: dict | None) -> dict[str, Any]:
    psu_verdict = (oc or {}).get("verdict", "probe-unavailable")
    therm = thermal["verdict"]

    # The matrix (rc reflects severity: 0 safe, 1 investigate, 2 act-NOW).
    if therm == "critical":
        v, rc = "pull-oc-now", 2
        msg = "Thermal CRITICAL — operator must drop OC profile NOW."
    elif psu_verdict == "over-budget":
        v, rc = "pull-oc-now", 2
        msg = "PSU over-budget — operator must drop OC profile or GPU power_limit NOW."
    elif therm == "warn" and psu_verdict == "headroom-tight":
        v, rc = "both-tight", 1
        msg = ("Both thermal AND PSU posture are tight — operator should "
               "investigate before sustained 100% load.")
    elif therm == "warn":
        v, rc = "thermal-watch", 1
        msg = "Thermal posture is tight (PSU has headroom)."
    elif psu_verdict == "headroom-tight":
        v, rc = "psu-watch", 1
        msg = "PSU posture is tight (thermal has headroom)."
    elif therm == "thermal-probe-unavailable" and psu_verdict == "probe-unavailable":
        v, rc = "probes-unavailable", 1
        msg = "Both probes unavailable — operator should check on a real SAIN-01 host."
    else:
        v, rc = "safe", 0
        msg = "Thermal + PSU posture both safe. OC profile is sustainable."

    return {"verdict": v, "rc": rc, "message": msg,
            "psu_verdict": psu_verdict, "thermal_verdict": therm}


# ── Assembly ────────────────────────────────────────────────────────
def build_report(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("thermal-oc-budget", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]

    thermal_raw = probe_thermal()
    oc_raw = probe_oc_headroom()
    psu_oc_raw = probe_psu_oc()

    thermal = derive_thermal_status(thermal_raw, cfg)
    combined = derive_combined_verdict(thermal, oc_raw, psu_oc_raw)

    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "thermal": thermal,
        "psu_headroom_verdict": (oc_raw or {}).get("verdict"),
        "psu_oc_mode_enabled": ((psu_oc_raw or {}).get("oc_mode_enabled")),
        "operator_psu_model": ((psu_oc_raw or {}).get("operator_psu_model")),
        "verdict": combined["verdict"],
        "rc": combined["rc"],
        "message": combined["message"],
        "sources": {
            "thermal": ("scripts/hardware/thermal-watch.py" if thermal_raw is not None
                        else "(unavailable)"),
            "oc_headroom": ("scripts/hardware/oc-headroom.py" if oc_raw is not None
                            else "(unavailable)"),
            "psu_oc": ("scripts/hardware/psu-oc.py" if psu_oc_raw is not None
                       else "(unavailable)"),
        },
        "overlay": meta,
    }


def render_human(doc: dict) -> str:
    lines = ["── R296 sovereign-os thermal+OC combined budget (E2.M10) ──"]
    lines.append(f"  verdict:            {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  thermal verdict:    {doc['thermal']['verdict']}")
    if doc["thermal"]["hottest_cpu_c"] is not None:
        lines.append(f"  hottest CPU:        {doc['thermal']['hottest_cpu_c']} °C")
    if doc["thermal"]["hottest_gpu_c"] is not None:
        lines.append(f"  hottest GPU:        {doc['thermal']['hottest_gpu_c']} °C")
    lines.append(f"  PSU headroom:       {doc['psu_headroom_verdict']}")
    lines.append(f"  PSU OC-mode:        {doc['psu_oc_mode_enabled']}")
    lines.append(f"  operator PSU:       {doc['operator_psu_model']}")
    lines.append("")
    lines.append(f"  {doc['message']}")
    lines.append("")
    lines.append(f"  thermal detail:     {doc['thermal']['detail']}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="thermal-oc-budget.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "advisory", "inputs"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    doc = build_report(args.config)

    if args.verb == "inputs":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "config": doc["config"],
                "sources": doc["sources"],
                "thermal": doc["thermal"],
                "psu_headroom_verdict": doc["psu_headroom_verdict"],
                "psu_oc_mode_enabled": doc["psu_oc_mode_enabled"],
                "overlay": doc["overlay"],
            }, indent=2))
        else:
            print(f"── R296 inputs (E2.M10) ──")
            for k, v in doc["sources"].items():
                print(f"  {k:14s} ← {v}")
            print(f"  thermal_verdict: {doc['thermal']['verdict']}")
            print(f"  psu_verdict:     {doc['psu_headroom_verdict']}")
        return 0

    if args.verb == "advisory":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": doc["verdict"],
                "message": doc["message"],
                "rc": doc["rc"],
            }, indent=2))
        else:
            print(f"verdict: {doc['verdict']}")
            print(f"  {doc['message']}")
        return doc["rc"]

    # status
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
