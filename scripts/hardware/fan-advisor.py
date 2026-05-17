#!/usr/bin/env python3
"""scripts/hardware/fan-advisor.py — R337 (E1.M39).

Operator-named (§1b verbatim spec drop): "is it also going to be
aware of my fans ? or my fan settings? bios and such ? and what it
should be vs what it is and software side override? ... obviously
for a AI workstation there are certain recommandations especially
during training and whatever mode that require readiness of
inference".

Composes:
  - lm-sensors fan RPM readout (current state)
  - per-mode recommended curves (idle / inference-ready /
    training / oc-burst)
  - software-override gating advice (board-specific BIOS gates;
    ASUS X870E-Creator WiFi needs "Q-Fan Tuning enabled" +
    "Allow Software Override = true")

CLI:
  fan-advisor.py status     [--config P] [--json|--human]
                              current RPM readings + per-fan state
  fan-advisor.py recommend  [--mode M] [--config P] [--json|--human]
                              per-mode recommended fan curve
  fan-advisor.py modes      [--config P] [--json|--human]
                              list available modes + descriptions
  fan-advisor.py bios-gate  [--config P] [--json|--human]
                              board-specific BIOS knobs required
                              for software fan control

Operator-overlay (R283/SDD-030): /etc/sovereign-os/fan-advisor.toml
  - declared_board       (default operator's X870E-Creator WiFi)
  - active_mode          (default inference-ready)
  - [[fan_curves.<mode>]] operator-pinned per-mode curves

Exit codes:
  0  fans probable + match recommended for active mode
  1  fans probable but ≥1 fan off recommended curve (operator action)
  2  lm-sensors unavailable / fan data unprobable
"""
from __future__ import annotations

import argparse
import json
import shutil
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
ROUND = "R337"
SDD_VECTOR = "E1.M39"


DEFAULTS = {
    "declared_board": "asus-proart-x870e-creator-wifi",
    "active_mode": "inference-ready",
    "min_safe_rpm": 400,    # Below this with load present → flag
    "max_safe_rpm": 3000,   # Above this sustained → noise floor warn
}


# Per-mode recommended fan curves. Each entry: mode name + target
# CPU/GPU temp range + recommended fan-duty % (operator-readable).
MODE_CATALOG: list[dict[str, Any]] = [
    {
        "mode": "idle",
        "axis": "cooling",
        "description": "Host is idle; minimize noise + power; "
                        "fans at floor RPM.",
        "cpu_target_c_max": 50,
        "gpu_target_c_max": 50,
        "fan_duty_pct_chassis": 30,
        "fan_duty_pct_cpu": 30,
        "fan_duty_pct_gpu": 0,
        "operator_caveat": "Below 30% PWM many fans don't spin at all; "
                            "GPU 0% means zero-RPM mode active.",
    },
    {
        "mode": "inference-ready",
        "axis": "cooling",
        "description": "Inference workload ready to fire at any moment; "
                        "fans pre-warmed to avoid first-prompt thermal "
                        "spike.",
        "cpu_target_c_max": 65,
        "gpu_target_c_max": 70,
        "fan_duty_pct_chassis": 50,
        "fan_duty_pct_cpu": 50,
        "fan_duty_pct_gpu": 40,
        "operator_caveat": "Trades a few extra W of fan power for "
                            "zero thermal-throttle on first prompt.",
    },
    {
        "mode": "training",
        "axis": "cooling",
        "description": "Sustained AI training (hours-long) — fans at "
                        "high duty + max airflow; thermal headroom > "
                        "noise concerns.",
        "cpu_target_c_max": 80,
        "gpu_target_c_max": 80,
        "fan_duty_pct_chassis": 75,
        "fan_duty_pct_cpu": 80,
        "fan_duty_pct_gpu": 70,
        "operator_caveat": "Sustained 75%+ chassis fans = audible. "
                            "Pair with R296 thermal-oc-budget to verify "
                            "you have thermal margin for the OC profile.",
    },
    {
        "mode": "oc-burst",
        "axis": "cooling",
        "description": "Short-duration OC burst (benchmark / one-off "
                        "render); fans at max so transient heat "
                        "dissipates fast.",
        "cpu_target_c_max": 85,
        "gpu_target_c_max": 83,
        "fan_duty_pct_chassis": 100,
        "fan_duty_pct_cpu": 100,
        "fan_duty_pct_gpu": 100,
        "operator_caveat": "Max-RPM mode = loud (>50dB); only for "
                            "short bursts. NOT for sustained 24/7 use.",
    },
]


# Per-board BIOS-gate catalog (extends R312 board-advisor with the
# fan-specific knobs).
BIOS_GATE_CATALOG: dict[str, dict[str, Any]] = {
    "asus-proart-x870e-creator-wifi": {
        "board_name": "ASUS ProArt X870E-Creator WiFi",
        "bios_knobs_for_software_fan_override": [
            {"knob": "Q-Fan Tuning",
             "required": "Enabled",
             "menu": "Monitor → Q-Fan Configuration → Q-Fan Tuning",
             "rationale": "Tunes the per-fan PWM-vs-RPM curve before "
                          "software can override safely. Without it, "
                          "software duty% may not map predictably to "
                          "RPM."},
            {"knob": "Allow Software Fan Control",
             "required": "Enabled / Auto",
             "menu": "Monitor → Q-Fan Configuration → <each fan> → "
                     "Allow Software Override",
             "rationale": "Lets Linux fancontrol / lm-sensors PWM "
                          "writes actually take effect. Some boards "
                          "ignore PWM writes when this is Disabled."},
            {"knob": "Fan Profile",
             "required": "Manual",
             "menu": "Monitor → Q-Fan Configuration → CPU Fan Profile",
             "rationale": "Auto / Standard / Silent profiles override "
                          "software writes. Set Manual so the OS curve "
                          "is authoritative."},
        ],
        "lm_sensors_required_packages": ["lm-sensors", "fancontrol"],
        "post_bios_setup_steps": [
            "1. After BIOS changes, reboot",
            "2. sudo sensors-detect --auto",
            "3. sudo pwmconfig (interactive — pick fans + curves)",
            "4. sudo systemctl enable --now fancontrol",
            "5. Verify via `sensors` that fan PWM writes take effect",
        ],
        "operator_caveat": (
            "Some ASUS BIOSes ship with Allow Software Override = "
            "Disabled by default. If `pwmconfig` reports 'no PWM-"
            "responsive fans found' even with hardware present, "
            "operator must check BIOS first. Reset CMOS if knob is "
            "absent on older BIOS — flash to latest per R312 BIOS-"
            "flashback recipe."
        ),
    },
}


def _have(bin_name: str) -> bool:
    return shutil.which(bin_name) is not None


def probe_fans() -> dict[str, Any]:
    """Spawn `sensors -j` (lm-sensors JSON output) + extract fan
    RPM + PWM per device."""
    if not _have("sensors"):
        return {"probable": False,
                "error": "lm-sensors `sensors` binary not on PATH",
                "fans": []}
    try:
        r = subprocess.run(
            ["sensors", "-j"], capture_output=True, text=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"probable": False,
                "error": f"sensors subprocess failed: {e}",
                "fans": []}
    if r.returncode != 0:
        return {"probable": False,
                "error": f"sensors exited rc={r.returncode}: "
                          f"{(r.stderr or '')[:200]}",
                "fans": []}
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"probable": False,
                "error": f"sensors JSON parse failed: {e}",
                "fans": []}
    fans: list[dict[str, Any]] = []
    for chip, chip_data in (data.items() if isinstance(data, dict) else []):
        if not isinstance(chip_data, dict):
            continue
        for label, vals in chip_data.items():
            if not isinstance(vals, dict):
                continue
            # Fan inputs end with _input and live on keys like fan1, fan2.
            for k, v in vals.items():
                if k.endswith("_input") and ("fan" in label.lower()
                                                 or label.lower().startswith("fan")):
                    try:
                        fans.append({
                            "chip": chip,
                            "label": label,
                            "rpm": float(v),
                        })
                    except (TypeError, ValueError):
                        continue
    return {"probable": True, "error": None,
             "fan_count": len(fans), "fans": fans}


def resolve_mode(name: str) -> dict | None:
    for m in MODE_CATALOG:
        if m["mode"] == name:
            return m
    return None


def derive_status(cfg: dict, fan_probe: dict,
                    mode: dict) -> dict[str, Any]:
    """Compare current fan RPMs against the mode's expected curve."""
    if not fan_probe.get("probable"):
        return {
            "verdict": "fan-probe-unavailable",
            "rc": 2,
            "message": fan_probe.get("error") or "lm-sensors not probable",
            "off_curve_fans": [],
        }
    fans = fan_probe.get("fans", [])
    if not fans:
        return {
            "verdict": "no-fans-detected",
            "rc": 2,
            "message": "lm-sensors returned 0 fan readings — verify "
                        "`sensors-detect --auto` was run + chips loaded",
            "off_curve_fans": [],
        }
    min_safe = float(cfg["min_safe_rpm"])
    max_safe = float(cfg["max_safe_rpm"])
    off_curve = []
    for f in fans:
        rpm = f.get("rpm", 0)
        if rpm < min_safe:
            off_curve.append({**f, "issue": f"RPM {rpm} < min_safe {min_safe}",
                                "severity": "attention"})
        elif rpm > max_safe:
            off_curve.append({**f, "issue": f"RPM {rpm} > max_safe {max_safe}",
                                "severity": "attention"})
    if off_curve:
        return {
            "verdict": "fans-off-curve",
            "rc": 1,
            "message": f"{len(off_curve)} of {len(fans)} fans outside "
                        f"safe RPM band [{min_safe}, {max_safe}] for "
                        f"mode '{mode['mode']}'",
            "off_curve_fans": off_curve,
        }
    return {
        "verdict": "fans-in-curve",
        "rc": 0,
        "message": f"All {len(fans)} fans within safe RPM band for "
                    f"mode '{mode['mode']}'",
        "off_curve_fans": [],
    }


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("fan-advisor", DEFAULTS,
                                    explicit_path=overlay_path)
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def render_status_human(cfg: dict, mode: dict, fan_probe: dict,
                         status: dict) -> str:
    lines = [f"── R337 sovereign-os fan advisor (E1.M39) ──"]
    lines.append(f"  active mode:         {cfg['active_mode']}")
    lines.append(f"  fan probable:        {fan_probe.get('probable')}")
    lines.append(f"  fan count:           {fan_probe.get('fan_count', 0)}")
    lines.append(f"  verdict:             {status['verdict']} (rc={status['rc']})")
    lines.append(f"  message:             {status['message']}")
    if fan_probe.get("probable") and fan_probe.get("fans"):
        lines.append("")
        lines.append("  per-fan RPM:")
        for f in fan_probe["fans"][:10]:
            lines.append(f"    {f.get('chip', '?'):28s} {f.get('label', '?'):>12s}  "
                          f"{f.get('rpm', 0):>6.0f} RPM")
    if status.get("off_curve_fans"):
        lines.append("")
        lines.append("  off-curve fans:")
        for f in status["off_curve_fans"]:
            lines.append(f"    [{f['severity']}] {f.get('label')}  {f['issue']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fan-advisor.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("status",):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    pr = sub.add_parser("recommend")
    pr.add_argument("--mode")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    pm = sub.add_parser("modes")
    pm.add_argument("--config", type=Path)
    fm = pm.add_mutually_exclusive_group()
    fm.add_argument("--json", dest="fmt", action="store_const", const="json")
    fm.add_argument("--human", dest="fmt", action="store_const", const="human")
    pm.set_defaults(fmt="json")

    pb = sub.add_parser("bios-gate")
    pb.add_argument("--config", type=Path)
    fb = pb.add_mutually_exclusive_group()
    fb.add_argument("--json", dest="fmt", action="store_const", const="json")
    fb.add_argument("--human", dest="fmt", action="store_const", const="human")
    pb.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)

    if args.cmd == "modes":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "active_mode": cfg["active_mode"],
                "mode_count": len(MODE_CATALOG),
                "modes": MODE_CATALOG,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R337 fan modes (E1.M39) ──")
            print(f"  active mode: {cfg['active_mode']}")
            for m in MODE_CATALOG:
                marker = "→" if m['mode'] == cfg['active_mode'] else " "
                print(f"  {marker} {m['mode']:20s}  "
                      f"cpu_max={m['cpu_target_c_max']}°C  "
                      f"gpu_max={m['gpu_target_c_max']}°C")
                print(f"        {m['description'][:80]}")
        return 0

    if args.cmd == "bios-gate":
        board = cfg["declared_board"]
        entry = BIOS_GATE_CATALOG.get(board)
        if entry is None:
            print(json.dumps({
                "error": f"no BIOS-gate catalog for board: {board}",
                "known_boards": list(BIOS_GATE_CATALOG.keys()),
                "round": ROUND,
                "rc": 1,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "board": board,
                **entry,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R337 BIOS gate for fan SW override "
                  f"({entry['board_name']}) (E1.M39) ──")
            print()
            print(f"  required BIOS knobs:")
            for k in entry["bios_knobs_for_software_fan_override"]:
                print(f"    [{k['required']:>15s}] {k['knob']}")
                print(f"          menu: {k['menu']}")
            print()
            print(f"  post-BIOS setup steps:")
            for s in entry.get("post_bios_setup_steps", []):
                print(f"    {s}")
            print()
            print(f"  caveat: {entry['operator_caveat']}")
        return 0

    if args.cmd == "recommend":
        mode_name = args.mode if args.mode else cfg["active_mode"]
        mode = resolve_mode(mode_name)
        if mode is None:
            print(json.dumps({
                "error": f"unknown mode: {mode_name}",
                "known_modes": [m["mode"] for m in MODE_CATALOG],
                "round": ROUND,
                "rc": 1,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mode": mode,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R337 fan recommendation: {mode['mode']} (E1.M39) ──")
            print(f"  description:           {mode['description']}")
            print(f"  cpu target max:        {mode['cpu_target_c_max']}°C")
            print(f"  gpu target max:        {mode['gpu_target_c_max']}°C")
            print(f"  chassis fan duty:      {mode['fan_duty_pct_chassis']}%")
            print(f"  cpu fan duty:          {mode['fan_duty_pct_cpu']}%")
            print(f"  gpu fan duty:          {mode['fan_duty_pct_gpu']}%")
            print(f"  caveat: {mode['operator_caveat']}")
        return 0

    # status
    mode = resolve_mode(cfg["active_mode"]) or MODE_CATALOG[0]
    fan_probe = probe_fans()
    status = derive_status(cfg, fan_probe, mode)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "active_mode": cfg["active_mode"],
        "declared_board": cfg["declared_board"],
        "config": cfg,
        "mode": mode,
        "fan_probe": fan_probe,
        "verdict": status["verdict"],
        "rc": status["rc"],
        "message": status["message"],
        "off_curve_fans": status.get("off_curve_fans", []),
        "overlay": meta,
    }
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_status_human(cfg, mode, fan_probe, status), end="")
    return status["rc"]


if __name__ == "__main__":
    sys.exit(main())
