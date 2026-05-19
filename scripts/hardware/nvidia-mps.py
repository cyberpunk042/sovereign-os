#!/usr/bin/env python3
"""scripts/hardware/nvidia-mps.py — R551 (E11.M14) NVIDIA MPS controller.

Operator §1g (verbatim, sacrosanct):
  "Multi mode AI, multiple mode for the AI loadout and load-out switch"
  "be able to load multiple model or unload model and load a new one"

The RTX PRO 6000 (Blackwell workstation SKU) does NOT ship MIG
(per scripts/hardware/gpu-possibility-catalog.py). The NVIDIA-blessed
path to concurrently share a non-MIG GPU across multiple inference
processes (pulse / logic-engine / oracle-core + assistant + ad-hoc)
without serializing them via the time-slicer is **MPS** —
NVIDIA Multi-Process Service.

MPS spawns a control daemon (`nvidia-cuda-mps-control -d`) plus a
worker server per GPU. Client CUDA processes that set
`CUDA_MPS_PIPE_DIRECTORY` to the same pipe-dir transparently route
their kernel launches through the worker, which interleaves them
on the SMs without context-switching overhead.

Operations (read-mostly philosophy, mirrors cpu-mode.py / gpu-mode.py):

  status              report daemon running? pipe-dir? log-dir?
                      active-thread-percentage per visible GPU.
  show                alias for status (--json supported).
  start [--gpus N,M]  spawn `nvidia-cuda-mps-control -d` scoped to
                      CUDA_VISIBLE_DEVICES=N,M. Requires root or
                      pre-existing pipe-dir owned by caller.
  stop                cleanly quit the daemon via `echo quit |
                      nvidia-cuda-mps-control`.
  set-thread-pct <N>  set default active-thread-percentage to N
                      (1..100). Affects all subsequent client connects.
  policy              print effective policy (CUDA_MPS_PIPE_DIRECTORY,
                      CUDA_MPS_LOG_DIRECTORY, default-active-thread-pct,
                      gpus, oversub).
  apply <path.yaml>   apply a policy YAML (or .toml — auto-detect by
                      extension; .yaml requires pyyaml else hand-rolled
                      key=value parser).

Defaults:
  CUDA_MPS_PIPE_DIRECTORY = /var/run/nvidia-mps        (vs /tmp/nvidia-mps;
                                                        /var/run survives
                                                        per-user /tmp scrubs)
  CUDA_MPS_LOG_DIRECTORY  = /var/log/nvidia-mps

Exit codes:
  0  ok
  1  daemon action partially succeeded (e.g. set-thread-pct failed
     but daemon up)
  2  usage error / nvidia-smi unavailable / not-root for a mutating verb
  3  daemon not running (status-only verbs return 0; mutating ones
     that require running daemon return 3)

Read-mostly philosophy carries: status/show/policy NEVER write; only
start/stop/set-thread-pct/apply touch system state.

Cross-reference:
  - gpu-mode.py — sets GPU power/clock limits (orthogonal to MPS;
    MPS is about sharing, gpu-mode is about envelope).
  - gpu-policy.toml (/etc/sovereign-os/) — power-limit / clock-limit
    source-of-truth; this script DOES NOT touch it.
  - systemd/system/sovereign-nvidia-mps.service — boot-time wrapper
    that calls `nvidia-mps.py start` when policy.enabled = true.
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

DEFAULT_PIPE_DIR = "/var/run/nvidia-mps"
DEFAULT_LOG_DIR = "/var/log/nvidia-mps"
DEFAULT_POLICY = "/etc/sovereign-os/nvidia-mps.yaml"


# ── Probes ──────────────────────────────────────────────────────────


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def nvidia_smi_present() -> bool:
    return have("nvidia-smi")


def mps_control_present() -> bool:
    return have("nvidia-cuda-mps-control")


def visible_gpu_indices() -> list[int]:
    """Return the indices nvidia-smi reports. Empty list on failure."""
    if not nvidia_smi_present():
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    res: list[int] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            res.append(int(line))
    return res


def daemon_running(pipe_dir: str) -> bool:
    """The MPS daemon is alive iff its control pipe exists AND it
    answers a get_default_active_thread_percentage probe."""
    pipe = Path(pipe_dir) / "control"
    if not pipe.exists():
        return False
    # The control daemon answers commands fed on stdin. Use a short
    # timeout — a hung daemon must NOT block status.
    try:
        env = os.environ.copy()
        env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
        r = subprocess.run(
            ["nvidia-cuda-mps-control"],
            input="get_default_active_thread_percentage\n",
            capture_output=True, text=True, env=env,
            timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def current_thread_pct(pipe_dir: str) -> int | None:
    pipe = Path(pipe_dir) / "control"
    if not pipe.exists():
        return None
    try:
        env = os.environ.copy()
        env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
        r = subprocess.run(
            ["nvidia-cuda-mps-control"],
            input="get_default_active_thread_percentage\n",
            capture_output=True, text=True, env=env,
            timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


# ── State assembly ──────────────────────────────────────────────────


def gather_state(pipe_dir: str, log_dir: str) -> dict[str, Any]:
    state: dict[str, Any] = {
        "nvidia_smi_present": nvidia_smi_present(),
        "mps_control_present": mps_control_present(),
        "pipe_dir": pipe_dir,
        "log_dir": log_dir,
        "daemon_running": False,
        "visible_gpus": visible_gpu_indices() if nvidia_smi_present() else [],
        "default_active_thread_percentage": None,
    }
    if state["mps_control_present"]:
        state["daemon_running"] = daemon_running(pipe_dir)
        if state["daemon_running"]:
            state["default_active_thread_percentage"] = (
                current_thread_pct(pipe_dir)
            )
    return state


# ── Renderers ───────────────────────────────────────────────────────


def render_status_human(state: dict[str, Any]) -> str:
    lines = ["── sovereign-os NVIDIA MPS status (R551 / E11.M14) ──"]
    lines.append(
        f"nvidia-smi present              : "
        f"{'yes' if state['nvidia_smi_present'] else 'NO'}"
    )
    lines.append(
        f"nvidia-cuda-mps-control present : "
        f"{'yes' if state['mps_control_present'] else 'NO'}"
    )
    lines.append(f"pipe-dir : {state['pipe_dir']}")
    lines.append(f"log-dir  : {state['log_dir']}")
    lines.append(
        f"daemon   : {'running' if state['daemon_running'] else 'STOPPED'}"
    )
    if state["visible_gpus"]:
        lines.append(f"gpus     : {state['visible_gpus']}")
    else:
        lines.append("gpus     : (none reported by nvidia-smi)")
    if state["daemon_running"]:
        pct = state["default_active_thread_percentage"]
        lines.append(
            f"default-active-thread-pct : "
            f"{pct if pct is not None else '(unknown)'}"
        )
    return "\n".join(lines)


# ── Mutators ────────────────────────────────────────────────────────


def require_root_for_mutation() -> None:
    if os.geteuid() != 0:
        print(
            "[nvidia-mps] need root for this verb. Re-run with sudo:\n"
            "  sudo nvidia-mps.py <verb> [...]",
            file=sys.stderr,
        )
        sys.exit(2)


def ensure_dirs(pipe_dir: str, log_dir: str) -> None:
    Path(pipe_dir).mkdir(parents=True, exist_ok=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)


def start_daemon(pipe_dir: str, log_dir: str,
                 gpus: list[int] | None) -> int:
    if not mps_control_present():
        print(
            "[nvidia-mps] nvidia-cuda-mps-control not on PATH — "
            "install nvidia-utils / cuda-runtime first.",
            file=sys.stderr,
        )
        return 2
    if daemon_running(pipe_dir):
        print(f"[nvidia-mps] daemon already running at {pipe_dir} — no-op")
        return 0
    require_root_for_mutation()
    ensure_dirs(pipe_dir, log_dir)
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
    env["CUDA_MPS_LOG_DIRECTORY"] = log_dir
    if gpus:
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(g) for g in gpus)
    try:
        r = subprocess.run(
            ["nvidia-cuda-mps-control", "-d"],
            env=env, capture_output=True, text=True, check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[nvidia-mps] start failed: {e}", file=sys.stderr)
        return 1
    if r.returncode != 0:
        print(
            f"[nvidia-mps] daemon refused to start (rc={r.returncode}): "
            f"{r.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    print(f"[nvidia-mps] daemon started; pipe-dir={pipe_dir}")
    return 0


def stop_daemon(pipe_dir: str) -> int:
    if not daemon_running(pipe_dir):
        print(f"[nvidia-mps] daemon not running at {pipe_dir} — no-op")
        return 0
    require_root_for_mutation()
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
    try:
        r = subprocess.run(
            ["nvidia-cuda-mps-control"],
            input="quit\n",
            env=env, capture_output=True, text=True, check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[nvidia-mps] stop failed: {e}", file=sys.stderr)
        return 1
    if r.returncode != 0:
        print(
            f"[nvidia-mps] quit refused (rc={r.returncode}): "
            f"{r.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    print("[nvidia-mps] daemon stopped")
    return 0


def set_thread_pct(pipe_dir: str, pct: int) -> int:
    if not (1 <= pct <= 100):
        print(
            f"[nvidia-mps] thread-pct out of range: {pct} (must be 1..100)",
            file=sys.stderr,
        )
        return 2
    if not daemon_running(pipe_dir):
        print(
            f"[nvidia-mps] daemon not running at {pipe_dir} — "
            f"start it first.",
            file=sys.stderr,
        )
        return 3
    require_root_for_mutation()
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = pipe_dir
    try:
        r = subprocess.run(
            ["nvidia-cuda-mps-control"],
            input=f"set_default_active_thread_percentage {pct}\n",
            env=env, capture_output=True, text=True, check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[nvidia-mps] set-thread-pct failed: {e}", file=sys.stderr)
        return 1
    if r.returncode != 0:
        print(
            f"[nvidia-mps] set-thread-pct rc={r.returncode}: "
            f"{r.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    print(f"[nvidia-mps] default-active-thread-percentage set to {pct}")
    return 0


# ── Policy load ─────────────────────────────────────────────────────


def parse_policy(path: Path) -> dict[str, Any]:
    """Parse YAML if pyyaml present, else a tiny key:value subset.
    Keys: enabled, pipe_dir, log_dir, gpus, default_active_thread_pct.
    """
    txt = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
        data = yaml.safe_load(txt) or {}
        if isinstance(data, dict):
            return data
    except ImportError:
        pass
    out: dict[str, Any] = {}
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v.lower() in ("true", "false"):
            out[k] = (v.lower() == "true")
            continue
        if v.isdigit():
            out[k] = int(v)
            continue
        if k == "gpus":
            inner = v.strip().lstrip("[").rstrip("]")
            parts = [p.strip() for p in inner.split(",") if p.strip()]
            try:
                out[k] = [int(p) for p in parts]
            except ValueError:
                out[k] = parts
            continue
        out[k] = v
    return out


def apply_policy(path: Path) -> int:
    if not path.is_file():
        print(f"[nvidia-mps] policy file not found: {path}", file=sys.stderr)
        return 2
    pol = parse_policy(path)
    pipe_dir = str(pol.get("pipe_dir", DEFAULT_PIPE_DIR))
    log_dir = str(pol.get("log_dir", DEFAULT_LOG_DIR))
    gpus = pol.get("gpus") if isinstance(pol.get("gpus"), list) else None
    enabled = bool(pol.get("enabled", False))
    pct = pol.get("default_active_thread_pct")
    if not enabled:
        print("[nvidia-mps] policy.enabled=false — ensuring daemon is stopped")
        return stop_daemon(pipe_dir)
    rc = start_daemon(pipe_dir, log_dir, gpus)
    if rc != 0:
        return rc
    if isinstance(pct, int):
        return set_thread_pct(pipe_dir, pct)
    return 0


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="nvidia-mps",
        description="NVIDIA MPS controller (sovereign-os R551 / E11.M14).",
    )
    p.add_argument("--pipe-dir", default=DEFAULT_PIPE_DIR)
    p.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    p.add_argument("--json", action="store_true", help="JSON output")
    sub = p.add_subparsers(dest="verb")
    # Subcommands take a local --json so both `--json status` and
    # `status --json` work. Verbs declared as literal add_parser()
    # calls (grepability — tests/lint/test_nvidia_mps_contract.py
    # asserts the surface explicitly).
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_policy = sub.add_parser("policy")
    sp_policy.add_argument("--json", action="store_true", dest="json_sub")
    s_start = sub.add_parser("start")
    s_start.add_argument("--gpus", default=None,
                         help="comma-separated GPU indices (default: all)")
    sub.add_parser("stop")
    s_pct = sub.add_parser("set-thread-pct")
    s_pct.add_argument("pct", type=int)
    s_apply = sub.add_parser("apply")
    s_apply.add_argument("path", nargs="?", default=DEFAULT_POLICY)
    args = p.parse_args(argv)
    verb = args.verb or "status"
    # Merge global --json with subcommand-local --json so both
    # `--json status` and `status --json` work.
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("status", "show"):
        state = gather_state(args.pipe_dir, args.log_dir)
        if json_out:
            print(json.dumps(state, indent=2))
        else:
            print(render_status_human(state))
        return 0
    if verb == "policy":
        eff = {
            "pipe_dir": args.pipe_dir,
            "log_dir": args.log_dir,
            "default_policy_file": DEFAULT_POLICY,
            "exists": Path(DEFAULT_POLICY).is_file(),
        }
        if eff["exists"]:
            try:
                eff["parsed"] = parse_policy(Path(DEFAULT_POLICY))
            except OSError as e:
                eff["parse_error"] = str(e)
        if json_out:
            print(json.dumps(eff, indent=2))
        else:
            for k, v in eff.items():
                print(f"{k:30s} : {v}")
        return 0
    if verb == "start":
        gpus = None
        if args.gpus:
            try:
                gpus = [int(x) for x in args.gpus.split(",") if x.strip()]
            except ValueError:
                print(
                    f"[nvidia-mps] bad --gpus: {args.gpus!r}", file=sys.stderr,
                )
                return 2
        return start_daemon(args.pipe_dir, args.log_dir, gpus)
    if verb == "stop":
        return stop_daemon(args.pipe_dir)
    if verb == "set-thread-pct":
        return set_thread_pct(args.pipe_dir, args.pct)
    if verb == "apply":
        return apply_policy(Path(args.path))
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
