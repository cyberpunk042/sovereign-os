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
  warp-runner.py history [--limit N]      the run history (newest first)
  warp-runner.py history --json           machine-readable history + per-device stats

Run history (SDD-301): every run that actually advanced the sim (success or
domain error) appends one JSONL record to the run store —
SOVEREIGN_OS_SCIENCE_RUNS env override, default
~/.local/state/sovereign-os/science-runs.jsonl. Bounded to the last
1000 records. History writing is best-effort and never changes the run's exit
code. The graceful-degrade path (warp not installed) records nothing — there is
no sim to remember.

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
from datetime import datetime, timezone
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

# Run history (SDD-301) — where `run` results accumulate so the panel/CLI can
# show what ran, where, and how fast. Env-overridable (test + operator layout);
# mirrors the SDD-300 warp-renders store convention (user-local state).
RUNS_ENV = "SOVEREIGN_OS_SCIENCE_RUNS"
DEFAULT_RUNS_PATH = Path("~/.local/state/sovereign-os/science-runs.jsonl")
MAX_RUN_RECORDS = 1000


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


# ── run history (SDD-301) ─────────────────────────────────────────────────────

def runs_path() -> Path:
    env = os.environ.get(RUNS_ENV, "").strip()
    return Path(env).expanduser() if env else DEFAULT_RUNS_PATH.expanduser()


def record_run(payload: dict[str, Any]) -> None:
    """Append one JSONL history record for a sim that actually ran (or raised).
    Best-effort: any failure is swallowed — the run's exit code is unchanged."""
    sim = payload.get("sim") or {}
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "warp-lang",
        "sim": "particle-drop",
        "device": payload.get("device"),
        "num_particles": sim.get("num_particles"),
        "steps": sim.get("steps"),
        "dt": sim.get("dt"),
        "wall_ms": sim.get("wall_ms"),
        "mean_final_height": sim.get("mean_final_height"),
        "settled": sim.get("settled"),
        "warp_version": payload.get("version"),
    }
    if payload.get("error"):
        rec["error"] = str(payload["error"])
    try:
        p = runs_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = [l for l in p.read_text().splitlines()] if p.exists() else []
        lines.append(json.dumps(rec))
        if len(lines) > MAX_RUN_RECORDS:
            lines = lines[-MAX_RUN_RECORDS:]
        tmp = p.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(lines) + "\n")
        tmp.replace(p)
    except (OSError, ValueError):
        pass  # history is observability, never a run gate


def read_history(limit: int | None) -> list[dict[str, Any]]:
    """Read the run store, newest first. Malformed lines are skipped (the store
    is an append log, not a contract)."""
    p = runs_path()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    except OSError:
        return []
    out.reverse()  # newest first (file is append-oldest-first)
    return out[:limit] if limit else out


def _median(ws: list[float]) -> float:
    s = sorted(ws)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def history_stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-device aggregates over the (newest-first) runs: count + median
    wall_ms. The GPU-vs-CPU comparison strip on the panel reads this."""
    by_device: dict[str, list[float]] = {}
    for r in runs:
        w = r.get("wall_ms")
        dev = r.get("device")
        if isinstance(w, (int, float)) and dev:
            by_device.setdefault(str(dev), []).append(float(w))
    return {
        "count": len(runs),
        "by_device": {
            dev: {"count": len(ws), "median_wall_ms": round(_median(ws), 3)}
            for dev, ws in sorted(by_device.items())
        },
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
    sp_hist = sub.add_parser("history")
    sp_hist.add_argument("--json", action="store_true")
    sp_hist.add_argument("--limit", type=int)
    args = p.parse_args(argv)
    cmd = args.cmd or "run"

    # --json must be machine-parseable on stdout (SB-077). Warp prints its init
    # banner + JIT "load on device" lines to stdout; when --json, route stdout to
    # stderr for the run so the JSON below is the only thing on fd 1.
    real_stdout = sys.stdout
    if getattr(args, "json", False):
        sys.stdout = sys.stderr
    try:
        # history is pure store-reading: handle it BEFORE the warp probe so the
        # verb stays stdlib-fast and works on a box where warp is broken.
        if cmd == "history":
            runs = read_history(getattr(args, "limit", None))
            if getattr(args, "json", False):
                print(json.dumps({"runs": runs, "stats": history_stats(runs)},
                                 indent=2), file=real_stdout)
            else:
                print("── R558 (SDD-301) science · run history ──")
                if not runs:
                    print("  (no recorded runs yet)")
                for r in runs[:30]:
                    w = r.get("wall_ms")
                    err = r.get("error")
                    print(f"  {r.get('ts', '?'):<26} {str(r.get('device')):<8} "
                          f"{r.get('num_particles')}×{r.get('steps')} → "
                          f"{('ERR ' + err[:40]) if err else (str(w) + ' ms')}")
            return 0

        status = warp_status()
        payload: dict[str, Any] = dict(status)

        if cmd == "status":
            if getattr(args, "json", False):
                print(json.dumps(payload, indent=2), file=real_stdout)
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
                print(json.dumps(payload, indent=2), file=real_stdout)
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
            record_run(payload)
            if args.json:
                print(json.dumps(payload, indent=2), file=real_stdout)
            else:
                print(render_human(payload) + f"\n  ERROR: {payload['error']}", file=sys.stderr)
            return 1

        payload["device"] = device
        payload["sim"] = sim
        record_run(payload)
        if getattr(args, "emit_metrics", False):
            emit_metrics(payload)
        if args.json:
            print(json.dumps(payload, indent=2), file=real_stdout)
        else:
            print(render_human(payload))
        return 0
    finally:
        sys.stdout = real_stdout


if __name__ == "__main__":
    sys.exit(main())
