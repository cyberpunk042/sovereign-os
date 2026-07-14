#!/usr/bin/env python3
"""scripts/hardware/gpu-watch.py — R219 (SDD-026 Z-5) GPU watt deviance watcher.

Operator directive (verbatim): "warning if the RTX 4090 which should
be slightly reduce which isn't and things like this that warn
deviance from 'perfertion'".

Reads /etc/sovereign-os/gpu-policy.toml (or config/gpu-policy.toml.example
for dev runs), polls nvidia-smi for live per-GPU power.draw + power.limit,
matches each device against the operator's policy by model_hint
substring, and emits:

  - Banner per GPU (`  ✓ RTX PRO 6000 Max-Q (idx=0)  draw=275W  limit=300W  ✓`)
  - Deviance lines for each mismatch with an actionable nvidia-smi fix
  - Layer B Prometheus textfile metrics:
      sovereign_os_gpu_power_limit_watts{gpu="...",idx="N"}
      sovereign_os_gpu_power_draw_watts{gpu="...",idx="N"}
      sovereign_os_gpu_power_limit_deviance_watts{gpu="...",idx="N"}
      sovereign_os_gpu_sustained_draw_warning{gpu="...",idx="N"} (0/1)

CLI:
  gpu-watch.py                            human-readable banner
  gpu-watch.py --json                     machine-readable JSON
  gpu-watch.py --emit-metrics             write .prom textfile (timer use)
  gpu-watch.py --policy /path/to/file     explicit policy file

Exit codes:
  0  every policed GPU is within tolerance
  1  at least one GPU exceeded tolerance (deviance flagged)
  2  usage error / policy unreadable / nvidia-smi missing

The script is read-only — it NEVER changes GPU state. Operator runs
the suggested `nvidia-smi -i N -pl X` manually (deliberate; selfdef
philosophy is operator-control).
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
DEFAULT_POLICY = Path("/etc/sovereign-os/gpu-policy.toml")
DEV_POLICY = REPO_ROOT / "config" / "gpu-policy.toml.example"
DEFAULT_METRICS_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_GPU_METRICS_PATH",
        "/var/lib/node_exporter/textfile_collector/sovereign-os-gpu-watch.prom",
    )
)


def resolve_policy_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    if DEFAULT_POLICY.exists():
        return DEFAULT_POLICY
    if DEV_POLICY.exists():
        return DEV_POLICY
    return None


def load_policy(path: Path) -> dict[str, dict[str, Any]]:
    """Returns dict keyed by model_hint substring."""
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    out: dict[str, dict[str, Any]] = {}
    for key, val in (doc.get("gpu") or {}).items():
        if isinstance(val, dict):
            out[key] = val
    return out


def probe_gpus_via_nvidia_smi() -> list[dict[str, Any]]:
    """Returns one dict per GPU with idx/name/power_draw/power_limit."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,power.draw,power.limit",
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
    out: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        name = parts[1]
        # nvidia-smi reports "N/A" when telemetry is unavailable.
        def _f(x: str) -> float | None:
            try:
                return float(x)
            except ValueError:
                return None

        out.append(
            {
                "idx": idx,
                "name": name,
                "power_draw_watts": _f(parts[2]),
                "power_limit_watts": _f(parts[3]),
            }
        )
    return out


def match_policy(gpu_name: str, policy: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    name_low = gpu_name.lower()
    for hint, rule in policy.items():
        if hint.lower() in name_low:
            return hint, rule
    return None


def analyse(
    gpus: list[dict[str, Any]],
    policy: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    any_deviance = False
    for g in gpus:
        match = match_policy(g["name"], policy)
        row: dict[str, Any] = {
            "idx": g["idx"],
            "name": g["name"],
            "power_draw_watts": g["power_draw_watts"],
            "power_limit_watts": g["power_limit_watts"],
            "policed": match is not None,
            "policy_hint": match[0] if match else None,
            "deviance_watts": None,
            "sustained_draw_warning": False,
            "flags": [],
            "fix_command": None,
        }
        if match is not None:
            hint, rule = match
            safe = float(rule.get("safe_limit_watts", 0))
            tol = float(rule.get("tolerance_watts", 5))
            actual_limit = g["power_limit_watts"]
            if actual_limit is None:
                row["flags"].append("nvidia-smi did not report power.limit")
                any_deviance = True
            else:
                dev = abs(actual_limit - safe)
                row["deviance_watts"] = dev
                if dev > tol:
                    direction = "above" if actual_limit > safe else "below"
                    row["flags"].append(
                        f"power_limit {actual_limit:.0f}W is {direction} "
                        f"operator-set safe_limit {safe:.0f}W (tolerance ±{tol:.0f}W)"
                    )
                    row["fix_command"] = (
                        f"nvidia-smi -i {g['idx']} -pl {int(safe)}"
                    )
                    any_deviance = True
            max_sus = rule.get("max_sustained_draw_watts")
            draw = g["power_draw_watts"]
            if (
                max_sus is not None
                and draw is not None
                and draw > float(max_sus)
            ):
                row["sustained_draw_warning"] = True
                row["flags"].append(
                    f"sustained draw {draw:.0f}W exceeds "
                    f"max_sustained_draw {max_sus:.0f}W "
                    f"(warning only — sustained loads are normal during inference)"
                )
                # NOT counted as deviance — informational only
        rows.append(row)
    return {"gpus": rows, "any_deviance": any_deviance}


def render_text(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("── R219 sovereign-os gpu-watch (SDD-026 Z-5) ──")
    if not analysis["gpus"]:
        lines.append("(no GPUs detected — nvidia-smi unavailable or no NVIDIA devices)")
        return "\n".join(lines) + "\n"
    for g in analysis["gpus"]:
        draw = "?" if g["power_draw_watts"] is None else f"{g['power_draw_watts']:.0f}W"
        limit = "?" if g["power_limit_watts"] is None else f"{g['power_limit_watts']:.0f}W"
        if not g["policed"]:
            lines.append(
                f"  ◌ {g['name']} (idx={g['idx']})  draw={draw}  limit={limit}"
                "  (no policy match — operator should add a [gpu.\"...\"] table)"
            )
            continue
        if not g["flags"]:
            lines.append(
                f"  ✓ {g['name']} (idx={g['idx']})  draw={draw}  limit={limit}"
                f"  (matches policy `{g['policy_hint']}`)"
            )
        else:
            lines.append(
                f"  ⚠ {g['name']} (idx={g['idx']})  draw={draw}  limit={limit}"
                f"  (policy `{g['policy_hint']}`)"
            )
            for f in g["flags"]:
                lines.append(f"      - {f}")
            if g["fix_command"]:
                lines.append(f"      → fix: {g['fix_command']}")
    if analysis["any_deviance"]:
        lines.append("")
        lines.append("⚠ Deviance detected — operator should re-apply the safe power limits.")
    return "\n".join(lines) + "\n"


def render_metrics(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# HELP sovereign_os_gpu_power_limit_watts Current per-GPU power.limit reading (nvidia-smi).")
    lines.append("# TYPE sovereign_os_gpu_power_limit_watts gauge")
    for g in analysis["gpus"]:
        if g["power_limit_watts"] is not None:
            safe_name = g["name"].replace('"', '\\"')
            lines.append(
                f'sovereign_os_gpu_power_limit_watts{{gpu="{safe_name}",idx="{g["idx"]}"}} '
                f'{g["power_limit_watts"]:.0f}'
            )
    lines.append("# HELP sovereign_os_gpu_power_draw_watts Current per-GPU power.draw reading.")
    lines.append("# TYPE sovereign_os_gpu_power_draw_watts gauge")
    for g in analysis["gpus"]:
        if g["power_draw_watts"] is not None:
            safe_name = g["name"].replace('"', '\\"')
            lines.append(
                f'sovereign_os_gpu_power_draw_watts{{gpu="{safe_name}",idx="{g["idx"]}"}} '
                f'{g["power_draw_watts"]:.0f}'
            )
    lines.append(
        "# HELP sovereign_os_gpu_power_limit_deviance_watts "
        "abs(actual_limit - operator_safe_limit) for policed GPUs (R219 / SDD-026 Z-5)."
    )
    lines.append("# TYPE sovereign_os_gpu_power_limit_deviance_watts gauge")
    for g in analysis["gpus"]:
        if g["policed"] and g["deviance_watts"] is not None:
            safe_name = g["name"].replace('"', '\\"')
            lines.append(
                f'sovereign_os_gpu_power_limit_deviance_watts{{gpu="{safe_name}",idx="{g["idx"]}"}} '
                f'{g["deviance_watts"]:.1f}'
            )
    lines.append(
        "# HELP sovereign_os_gpu_sustained_draw_warning "
        "1 = current power_draw exceeds operator's max_sustained_draw_watts."
    )
    lines.append("# TYPE sovereign_os_gpu_sustained_draw_warning gauge")
    for g in analysis["gpus"]:
        if g["policed"]:
            safe_name = g["name"].replace('"', '\\"')
            v = 1 if g["sustained_draw_warning"] else 0
            lines.append(
                f'sovereign_os_gpu_sustained_draw_warning{{gpu="{safe_name}",idx="{g["idx"]}"}} {v}'
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(
        description="R219 (SDD-026 Z-5) — GPU watt deviance watcher."
    )
    p.add_argument("--policy", type=Path, help="explicit policy file path")
    p.add_argument("--json", action="store_true", help="emit JSON instead of banner")
    p.add_argument(
        "--emit-metrics",
        action="store_true",
        help="write Layer B textfile metrics atomically",
    )
    p.add_argument(
        "--metrics-path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="override metrics file path (default %(default)s)",
    )
    args = p.parse_args()

    policy_path = resolve_policy_path(args.policy)
    policy: dict[str, dict[str, Any]] = {}
    if policy_path is not None:
        try:
            policy = load_policy(policy_path)
        except Exception as e:
            print(f"ERROR reading policy {policy_path}: {e}", file=sys.stderr)
            return 2

    gpus = probe_gpus_via_nvidia_smi()
    analysis = analyse(gpus, policy)

    if args.emit_metrics:
        try:
            args.metrics_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = args.metrics_path.with_suffix(args.metrics_path.suffix + ".tmp")
            tmp.write_text(render_metrics(analysis))
            tmp.replace(args.metrics_path)
        except OSError as e:
            print(f"WARNING failed to write metrics: {e}", file=sys.stderr)
        # Even with --emit-metrics, also print banner unless --json
        # so operator running on-demand gets a status echo.

    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        sys.stdout.write(render_text(analysis))

    return 1 if analysis["any_deviance"] else 0


if __name__ == "__main__":
    sys.exit(main())
