#!/usr/bin/env python3
"""scripts/science/warp-runner.py — R558 (SDD-070) NVIDIA Warp particle-sim runner.

The one and only warp-importing script in the tree. Everything operator-facing
(scripts/science/science.py, scripts/operator/science-api.py, the osctl bridge)
is stdlib-only and shells out to THIS runner with --json — so the heavy
warp/CUDA import is confined here, per the repo's stdlib-only runtime doctrine.

Materialises the `particles` entry of config/science-tools.yaml (the operator's
Image-2 science catalog) and the `simulation` REPL kind declared in
config/execution/m023-execution-substrate.yaml (M00374, Tiers 3-5).

What it does: a small, deterministic sample simulation — N particles dropped
under gravity with a floor bounce — advanced with a Warp kernel on the GPU when
a CUDA device is present, else on the CPU. It reports the device that ran it and
a few observables. NVIDIA Warp's pip wheel bundles the CUDA 12 runtime, so GPU
works with just the NVIDIA driver; when no CUDA GPU is present Warp runs on CPU.

Config: /etc/sovereign-os/warp.toml (or config/science/warp.toml.example for dev
runs) — [sim] num_particles / steps / dt / device_preference (auto|cuda|cpu).

CLI:
  warp-runner.py run                      run the sample sim, human banner
  warp-runner.py run --json               machine-readable JSON
  warp-runner.py status --json            device/version report, no sim
  warp-runner.py run --emit-metrics       write Layer B .prom textfile
  warp-runner.py run --device cpu         force a device (cpu|cuda|auto)
  warp-runner.py run --particles N --steps M

Exit codes:
  0  clean — sim ran (GPU or CPU), OR warp not installed (graceful degrade)
  1  domain error — warp present but the sim raised
  2  usage error / config unreadable
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:  # pragma: no cover
        tomllib = None  # type: ignore

VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/warp.toml")
DEV_CONFIG = REPO_ROOT / "config" / "science" / "warp.toml.example"
DEFAULT_METRICS_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_WARP_METRICS_PATH",
        "/var/lib/node_exporter/textfile_collector/sovereign-os-science-warp.prom",
    )
)

# Sim defaults (overridden by config + CLI).
DEFAULTS = {"num_particles": 100_000, "steps": 200, "dt": 0.01, "device_preference": "auto"}


def resolve_config_path(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(explicit: str | None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    path = resolve_config_path(explicit)
    if path is None or tomllib is None:
        return cfg
    try:
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
        sim = doc.get("sim") or {}
        for k in DEFAULTS:
            if k in sim:
                cfg[k] = sim[k]
    except (OSError, ValueError):
        pass  # unreadable config → defaults (never fatal)
    return cfg


# ── warp availability + device probing (import-guarded) ──────────────────────

def warp_status() -> dict[str, Any]:
    """Report whether warp is importable, its version, and available devices.
    Never raises — returns a structured dict for the panel/CLI."""
    out: dict[str, Any] = {
        "installed": False,
        "version": None,
        "cuda_available": False,
        "cuda_device_count": 0,
        "devices": [],
    }
    try:
        import warp as wp  # type: ignore
    except Exception:  # ImportError or a broken partial install
        return out
    out["installed"] = True
    out["version"] = getattr(wp, "__version__", None)
    try:
        wp.init()
    except Exception:
        # warp present but init failed (e.g. no libs) — still "installed".
        return out
    try:
        out["cuda_available"] = bool(wp.is_cuda_available())
    except Exception:
        out["cuda_available"] = False
    try:
        out["cuda_device_count"] = int(wp.get_cuda_device_count())
    except Exception:
        out["cuda_device_count"] = 0
    try:
        out["devices"] = [str(d) for d in wp.get_devices()]
    except Exception:
        out["devices"] = []
    return out


def select_device(preference: str, status: dict[str, Any]) -> str:
    """auto → cuda:0 if available else cpu; cuda → cuda:0 (falls back to cpu with
    a note if unavailable); cpu → cpu."""
    pref = (preference or "auto").lower()
    if pref == "cpu":
        return "cpu"
    if status.get("cuda_available"):
        return "cuda:0"
    return "cpu"


# ── the sample simulation (raw Warp kernel — version-stable) ─────────────────

def run_sim(cfg: dict[str, Any], device: str) -> dict[str, Any]:
    """Drop N particles under gravity with a floor bounce, advance `steps`
    Warp-kernel iterations on `device`, return observables. Raises on warp error."""
    import numpy as np  # numpy is warp's one hard dependency
    import warp as wp  # type: ignore

    wp.init()
    n = int(cfg["num_particles"])
    steps = int(cfg["steps"])
    dt = float(cfg["dt"])

    # 1D vertical model per particle: y-position (staggered heights) + y-velocity.
    rng = np.linspace(1.0, 10.0, n, dtype=np.float32)
    pos = wp.array(rng, dtype=wp.float32, device=device)
    vel = wp.array(np.zeros(n, dtype=np.float32), dtype=wp.float32, device=device)

    @wp.kernel
    def step_kernel(
        pos: wp.array(dtype=wp.float32),
        vel: wp.array(dtype=wp.float32),
        g: wp.float32,
        dt: wp.float32,
    ):
        i = wp.tid()
        v = vel[i] + g * dt
        p = pos[i] + v * dt
        if p < 0.0:
            p = 0.0
            v = -v * 0.5  # restitution
        pos[i] = p
        vel[i] = v

    t0 = time.perf_counter()
    for _ in range(steps):
        wp.launch(step_kernel, dim=n, inputs=[pos, vel, wp.float32(-9.81), wp.float32(dt)], device=device)
    try:
        wp.synchronize()
    except Exception:
        pass
    wall_ms = (time.perf_counter() - t0) * 1000.0

    final = pos.numpy()
    return {
        "num_particles": n,
        "steps": steps,
        "dt": dt,
        "wall_ms": round(wall_ms, 3),
        "mean_final_height": round(float(final.mean()), 5),
        "max_final_height": round(float(final.max()), 5),
        "settled": int((final <= 0.001).sum()),  # particles resting on the floor
    }


# ── metrics ──────────────────────────────────────────────────────────────────

def emit_metrics(payload: dict[str, Any]) -> bool:
    """Write Layer B Prometheus textfile metrics. Silent no-op on failure."""
    lines = [
        "# HELP sovereign_os_science_warp_installed warp-lang importable (0/1).",
        "# TYPE sovereign_os_science_warp_installed gauge",
        f'sovereign_os_science_warp_installed {1 if payload.get("installed") else 0}',
    ]
    sim = payload.get("sim")
    dev = payload.get("device", "none")
    if sim:
        lines += [
            "# HELP sovereign_os_science_warp_sim_wall_ms last sample sim wall time (ms).",
            "# TYPE sovereign_os_science_warp_sim_wall_ms gauge",
            f'sovereign_os_science_warp_sim_wall_ms{{device="{dev}"}} {sim["wall_ms"]}',
            "# HELP sovereign_os_science_warp_sim_particles particles in last sample sim.",
            "# TYPE sovereign_os_science_warp_sim_particles gauge",
            f'sovereign_os_science_warp_sim_particles{{device="{dev}"}} {sim["num_particles"]}',
        ]
    try:
        DEFAULT_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DEFAULT_METRICS_PATH.with_suffix(".prom.tmp")
        tmp.write_text("\n".join(lines) + "\n")
        tmp.replace(DEFAULT_METRICS_PATH)
        return True
    except OSError:
        return False


# ── rendering ────────────────────────────────────────────────────────────────

def render_human(payload: dict[str, Any]) -> str:
    L = ["── R558 sovereign-os science · NVIDIA Warp (SDD-070) ──"]
    if not payload.get("installed"):
        L.append("  warp-lang: NOT installed")
        L.append("  action:    install via `sovereign-osctl science install`")
        L.append("             (first boot runs scripts/hooks/post-install/warp-setup.sh)")
        return "\n".join(L)
    L.append(f"  warp-lang: installed (v{payload.get('version') or '?'})")
    L.append(f"  cuda:      {'available' if payload.get('cuda_available') else 'not available (CPU fallback)'}"
             f"  devices={payload.get('devices') or []}")
    sim = payload.get("sim")
    if sim:
        L.append(f"  device:    {payload.get('device')}")
        L.append(f"  sim:       {sim['num_particles']} particles × {sim['steps']} steps → "
                 f"{sim['wall_ms']} ms")
        L.append(f"  result:    mean_h={sim['mean_final_height']}  settled={sim['settled']}")
    return "\n".join(L)


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="R558 (SDD-070) NVIDIA Warp particle-sim runner.")
    sub = p.add_subparsers(dest="cmd")
    for name in ("run", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--config")
        if name == "run":
            sp.add_argument("--emit-metrics", action="store_true")
            sp.add_argument("--device", choices=["auto", "cuda", "cpu"])
            sp.add_argument("--particles", type=int)
            sp.add_argument("--steps", type=int)
    args = p.parse_args(argv)
    cmd = args.cmd or "run"

    status = warp_status()
    payload: dict[str, Any] = dict(status)

    if cmd == "status":
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2))
        else:
            print(render_human(payload))
        return 0

    # cmd == "run"
    if not status["installed"]:
        # Graceful degrade: not installed is a clean exit (0), not a failure.
        payload["device"] = None
        payload["sim"] = None
        if getattr(args, "emit_metrics", False):
            emit_metrics(payload)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(render_human(payload))
        return 0

    cfg = load_config(getattr(args, "config", None))
    if getattr(args, "particles", None):
        cfg["num_particles"] = args.particles
    if getattr(args, "steps", None):
        cfg["steps"] = args.steps
    pref = getattr(args, "device", None) or cfg["device_preference"]
    device = select_device(pref, status)

    try:
        sim = run_sim(cfg, device)
    except Exception as exc:  # warp present but sim raised → domain error
        payload["device"] = device
        payload["sim"] = None
        payload["error"] = f"{type(exc).__name__}: {exc}"
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(render_human(payload) + f"\n  ERROR: {payload['error']}", file=sys.stderr)
        return 1

    payload["device"] = device
    payload["sim"] = sim
    if getattr(args, "emit_metrics", False):
        emit_metrics(payload)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_human(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
