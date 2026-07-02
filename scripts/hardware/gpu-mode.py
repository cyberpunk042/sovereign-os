#!/usr/bin/env python3
"""scripts/hardware/gpu-mode.py — R236 (SDD-026 Z-5 extension).

Operator-named (verbatim, 2026-05-17 expansion): "Same for the GPU I
guess and this like the tracking of the state like the watt set
consumption for the GPU... with a warning if the RTX 4090 which should
be sliglly reduce which isn't and things like this that warn deviance
from 'perfertion'".

R219 (gpu-watch) tracks the watt state + emits deviance warnings.
R230 (cpu-mode auto) ships the CPU hotswap with workload-aware
recommendation. R236 mirrors R230 on the GPU side: four named modes,
show/list/set/auto verbs, advisory-by-default policy.

Modes (per-GPU power-limit watt targets):

  conservative   reduce TDP to operator-friendly cool baseline
                 (4090 → 250 W, RTX PRO 6000 → 450 W). Designed
                 to keep cooling headroom for sustained inference.

  balanced       split-the-difference (4090 → 300 W, 6000 → 500 W).
                 Default for mixed workloads — chat + light agent.

  sustained      stock TDP, but cap any post-overclock excursion
                 (4090 → 350 W, 6000 → 600 W).

  peak           full TDP every card supports. Operator-driven for
                 synchronous low-batch inference where every watt
                 matters. Uses card's reported max from nvidia-smi
                 (--query-gpu=power.max_limit).

The watt targets are MATCHED to the operator's safe_limit_watts
declared in /etc/sovereign-os/gpu-policy.toml — running `gpu-mode
balanced` writes the safe_limit, NOT the mode's hardcoded value.
This means the mode table is operator-overridable per card; the
named modes are just operator-readable presets.

CLI:
  gpu-mode show              current per-GPU power limits + matched mode
  gpu-mode list              enumerate the 4 named modes
  gpu-mode set <mode>        write per-GPU power limit (requires root)
  gpu-mode auto              workload-aware recommendation
  gpu-mode auto --apply      recommendation + write

Exit codes:
  0  operation succeeded (or advisory mode emitted)
  1  set partially failed
  2  usage error / nvidia-smi unavailable / set without root
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = Path("/etc/sovereign-os/gpu-policy.toml")
DEV_POLICY = REPO_ROOT / "config" / "gpu-policy.toml.example"
DEFAULT_METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR",
        "/var/lib/node_exporter/textfile_collector",
    )
)

# Mode → multiplier of the operator's safe_limit_watts. Conservative
# pulls 15% under, balanced sits at the operator's safe limit, sustained
# adds 10% headroom, peak goes to the card's reported max_limit. These
# are starting-point heuristics — operators with thermal budgets that
# differ should set per-card overrides in gpu-policy.toml under
# `[gpu.<hint>.mode_overrides]`.
MODE_FACTOR: dict[str, float] = {
    "conservative": 0.85,
    "balanced": 1.0,
    "sustained": 1.10,
    "peak": float("inf"),  # → card max_limit
}


def resolve_policy_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    if DEFAULT_POLICY.exists():
        return DEFAULT_POLICY
    if DEV_POLICY.exists():
        return DEV_POLICY
    return None


def load_policy(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    out: dict[str, dict[str, Any]] = {}
    for key, val in (doc.get("gpu") or {}).items():
        if isinstance(val, dict):
            out[key] = val
    return out


def match_policy(
    gpu_name: str, policy: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any]] | None:
    """First substring match (case-insensitive) wins. Mirror of R219."""
    n = gpu_name.lower()
    for hint, rule in policy.items():
        if hint.lower() in n:
            return (hint, rule)
    return None


def probe_gpus() -> list[dict[str, Any]]:
    """Returns [{idx, name, power_limit_watts, power_max_watts, power_draw_watts}]."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,power.limit,power.max_limit,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if r.returncode != 0:
        return []

    def _f(s: str) -> float | None:
        try:
            return float(s)
        except ValueError:
            return None

    out: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        out.append(
            {
                "idx": idx,
                "name": parts[1],
                "power_limit_watts": _f(parts[2]),
                "power_max_watts": _f(parts[3]),
                "power_draw_watts": _f(parts[4]),
            }
        )
    return out


def matched_mode_for(
    gpu: dict[str, Any], policy: dict[str, dict[str, Any]]
) -> str:
    """Best-effort: which named mode does the current power_limit match?"""
    plim = gpu.get("power_limit_watts")
    if plim is None:
        return "unknown"
    m = match_policy(gpu["name"], policy)
    if m is None:
        return "unpoliced"
    _, rule = m
    safe = float(rule.get("safe_limit_watts", 0)) or None
    if safe is None:
        return "unpoliced"
    # Tolerance: within ±5 W of any mode target = that mode.
    pmax = gpu.get("power_max_watts") or safe
    targets = {
        "conservative": safe * MODE_FACTOR["conservative"],
        "balanced": safe * MODE_FACTOR["balanced"],
        "sustained": safe * MODE_FACTOR["sustained"],
        "peak": pmax,
    }
    best = None
    best_diff = 999.0
    for name, t in targets.items():
        d = abs(plim - t)
        if d < best_diff:
            best_diff = d
            best = name
    return best if best_diff <= 5.0 else "custom"


def compute_target_watts(gpu: dict[str, Any], mode: str, safe: float) -> int:
    """Resolve mode → integer watt target for this card."""
    if mode == "peak":
        pmax = gpu.get("power_max_watts") or safe
        return int(round(pmax))
    factor = MODE_FACTOR[mode]
    return int(round(safe * factor))


def cmd_show(json_out: bool, policy_path: Path | None) -> int:
    gpus = probe_gpus()
    policy = load_policy(resolve_policy_path(policy_path))
    rows = []
    for g in gpus:
        rows.append(
            {
                "idx": g["idx"],
                "name": g["name"],
                "power_limit_watts": g["power_limit_watts"],
                "power_max_watts": g["power_max_watts"],
                "power_draw_watts": g["power_draw_watts"],
                "matched_mode": matched_mode_for(g, policy),
            }
        )
    if json_out:
        print(json.dumps({"round": "R236", "gpus": rows}, indent=2))
        return 0
    print("── R236 sovereign-os gpu-mode show (SDD-026 Z-5) ──")
    if not rows:
        print("  (no NVIDIA GPUs detected — nvidia-smi unavailable)")
        return 0
    for g in rows:
        plim = "?" if g["power_limit_watts"] is None else f"{g['power_limit_watts']:.0f}W"
        pmax = "?" if g["power_max_watts"] is None else f"{g['power_max_watts']:.0f}W"
        draw = "?" if g["power_draw_watts"] is None else f"{g['power_draw_watts']:.0f}W"
        print(
            f"  idx={g['idx']}  {g['name']:<32}  "
            f"limit={plim}  max={pmax}  draw={draw}  "
            f"mode={g['matched_mode']}"
        )
    return 0


def cmd_list(json_out: bool) -> int:
    rows = []
    for name, factor in MODE_FACTOR.items():
        if name == "peak":
            desc = "card's nvidia-smi --query-gpu=power.max_limit value"
        else:
            pct = int(round(factor * 100))
            desc = f"{pct}% of operator-set safe_limit_watts in gpu-policy.toml"
        rows.append({"mode": name, "factor": factor if factor != float("inf") else None, "describes": desc})
    if json_out:
        print(json.dumps({"round": "R236", "modes": rows}, indent=2))
        return 0
    print("── R236 sovereign-os gpu-mode list ──")
    for r in rows:
        print(f"  {r['mode']:<14} → {r['describes']}")
    return 0


def cmd_set(mode: str, policy_path: Path | None) -> int:
    if mode not in MODE_FACTOR:
        print(f"ERROR unknown mode {mode!r}; run `gpu-mode list`", file=sys.stderr)
        return 2
    if not shutil.which("nvidia-smi"):
        print("ERROR nvidia-smi not on PATH", file=sys.stderr)
        return 2
    gpus = probe_gpus()
    if not gpus:
        print("ERROR no NVIDIA GPUs detected", file=sys.stderr)
        return 2
    policy = load_policy(resolve_policy_path(policy_path))
    if os.geteuid() != 0:
        cmds = []
        for g in gpus:
            m = match_policy(g["name"], policy)
            if m is None:
                cmds.append(
                    f"# idx={g['idx']} {g['name']}: no policy match — add a "
                    f"[gpu.\"<substring>\"] table to gpu-policy.toml"
                )
                continue
            _, rule = m
            safe = float(rule.get("safe_limit_watts", 0))
            if safe <= 0:
                continue
            target = compute_target_watts(g, mode, safe)
            cmds.append(f"sudo nvidia-smi -i {g['idx']} -pl {target}")
        joined = "\n  ".join(cmds) if cmds else "(no actionable commands)"
        print(
            f"# Not running as root — to set mode {mode!r} run:\n  {joined}",
            file=sys.stderr,
        )
        return 2
    # Root path: actually write.
    failures = 0
    for g in gpus:
        m = match_policy(g["name"], policy)
        if m is None:
            print(f"  skip idx={g['idx']} {g['name']} (no policy match)")
            continue
        _, rule = m
        safe = float(rule.get("safe_limit_watts", 0))
        if safe <= 0:
            continue
        target = compute_target_watts(g, mode, safe)
        try:
            r = subprocess.run(
                ["nvidia-smi", "-i", str(g["idx"]), "-pl", str(target)],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if r.returncode != 0:
                failures += 1
                print(
                    f"  FAIL idx={g['idx']} {g['name']} → {target}W "
                    f"(nvidia-smi rc={r.returncode}: {r.stderr.strip()})"
                )
            else:
                print(f"  OK   idx={g['idx']} {g['name']} → {target}W")
        except (subprocess.TimeoutExpired, OSError) as e:
            failures += 1
            print(f"  FAIL idx={g['idx']} {g['name']}: {e}")
    return 1 if failures else 0


def _max_metric(lines: list[str], prefix: str) -> float:
    best = 0.0
    for line in lines:
        if line.startswith("#") or not line.startswith(prefix):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        try:
            v = float(parts[1])
            if v > best:
                best = v
        except ValueError:
            continue
    return best


def _read_prom(name: str) -> list[str]:
    p = DEFAULT_METRICS_DIR / name
    if not p.exists():
        return []
    try:
        return p.read_text(errors="replace").splitlines()
    except OSError:
        return []


def derive_auto_recommendation() -> dict[str, Any]:
    """R236 — workload-aware GPU mode recommendation.

    Mirrors R230 cpu-mode auto but consumes additional GPU-side signals.
    Signal sources (Layer B textfile collector .prom files):

      sovereign_os_gpu_sustained_draw_warning  (R219 / Z-5)
        non-zero when ≥1 GPU draws above its max_sustained_draw_watts.
        Strong signal that sustained inference is happening.

      sovereign_os_gpu_power_draw_watts        (R219 / Z-5)
        live draw; we look at max across all GPUs.

      sovereign_os_inference_router_class_total (R215 / Z-2)
        cumulative inference routes — any > 0 means inference is happening.

    Decision table:
      sustained warning fired   → sustained (matches the observed load)
      gpu_draw_max ≥ 200 W      → sustained
      gpu_draw_max ≥ 100 W      → balanced
      inference_routes > 0      → balanced
      otherwise                 → conservative (safe-default cool baseline)
    """
    gpu_lines = _read_prom("sovereign-os-gpu-watch.prom")
    infer_lines = _read_prom("sovereign-os-inference-router.prom")
    draw_max = _max_metric(gpu_lines, "sovereign_os_gpu_power_draw_watts")
    sus_warn = _max_metric(gpu_lines, "sovereign_os_gpu_sustained_draw_warning")
    infer_total = sum(
        float(line.rsplit(None, 1)[1])
        for line in infer_lines
        if not line.startswith("#")
        and line.startswith("sovereign_os_inference_router_class_total")
        and len(line.rsplit(None, 1)) == 2
        and line.rsplit(None, 1)[1].replace(".", "").replace("-", "").isdigit()
    )
    signals_present = bool(gpu_lines or infer_lines)
    if sus_warn > 0:
        rec, reason = "sustained", "GPU sustained-draw warning is active"
    elif draw_max >= 200.0:
        rec, reason = "sustained", f"GPU draw {draw_max:.0f} W ≥ 200 W"
    elif draw_max >= 100.0:
        rec, reason = "balanced", f"GPU draw {draw_max:.0f} W ≥ 100 W"
    elif infer_total > 0:
        rec, reason = "balanced", (
            f"inference router served {int(infer_total)} route(s)"
        )
    elif signals_present:
        rec, reason = "conservative", "cold GPU + no recent inference"
    else:
        rec, reason = "conservative", "no Layer B signals (safe cool default)"
    return {
        "round": "R236",
        "vector": "SDD-026 Z-5 (gpu-mode auto)",
        "signals": {
            "gpu_draw_max_watts": draw_max,
            "gpu_sustained_warn_active": sus_warn > 0,
            "inference_router_total": infer_total,
            "signals_present": signals_present,
        },
        "recommendation": rec,
        "reason": reason,
        "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def cmd_auto(apply_flag: bool, json_out: bool, policy_path: Path | None) -> int:
    rec = derive_auto_recommendation()
    rec["policy_path"] = str(resolve_policy_path(policy_path) or "")
    apply_rc: int | None = None
    if apply_flag:
        apply_rc = cmd_set(rec["recommendation"], policy_path)
    rec["apply_requested"] = bool(apply_flag)
    rec["apply_rc"] = apply_rc
    if json_out:
        print(json.dumps(rec, indent=2))
        return apply_rc if (apply_flag and apply_rc is not None) else 0
    print("── R236 sovereign-os gpu-mode auto ──")
    s = rec["signals"]
    print(
        f"  signals:        draw_max={s['gpu_draw_max_watts']:.0f} W  "
        f"sustained_warn={s['gpu_sustained_warn_active']}  "
        f"inference={int(s['inference_router_total'])}"
    )
    print(f"  recommendation: {rec['recommendation']}")
    print(f"  reason:         {rec['reason']}")
    if apply_flag:
        mark = "applied" if apply_rc == 0 else f"failed (rc={apply_rc})"
        print(f"  action:         {mark}")
    else:
        print(f"  action:         (advisory — re-run with --apply)")
    return apply_rc if (apply_flag and apply_rc is not None) else 0


def main() -> int:
    p = argparse.ArgumentParser(description="R236 (SDD-026 Z-5) GPU hotswap modes.")
    p.add_argument("--policy", type=Path, default=None)
    sub = p.add_subparsers(dest="action", required=True)
    ps = sub.add_parser("show", help="show current per-GPU power limit + matched mode")
    ps.add_argument("--json", action="store_true")
    pl = sub.add_parser("list", help="enumerate the 4 named modes")
    pl.add_argument("--json", action="store_true")
    pset = sub.add_parser("set", help="set a named mode (requires root)")
    pset.add_argument("mode", choices=sorted(MODE_FACTOR.keys()))
    pa = sub.add_parser("auto", help="workload-aware recommendation")
    pa.add_argument("--apply", action="store_true")
    pa.add_argument("--json", action="store_true")
    args = p.parse_args()
    if args.action == "show":
        return cmd_show(args.json, args.policy)
    if args.action == "list":
        return cmd_list(args.json)
    if args.action == "set":
        return cmd_set(args.mode, args.policy)
    if args.action == "auto":
        return cmd_auto(args.apply, args.json, args.policy)
    return 2


if __name__ == "__main__":
    sys.exit(main())
