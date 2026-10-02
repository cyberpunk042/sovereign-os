#!/usr/bin/env python3
"""scripts/science/science.py — R558 (SDD-070) science-tools operator CLI.

The stdlib-only (+ optional PyYAML) operator surface for the science-tools
catalog. Reads config/science-tools.yaml and delegates all NVIDIA Warp
status/execution to scripts/science/warp-runner.py — the ONLY warp-importing
script — so this CLI (and the science-api daemon that shells it) never carry the
heavy warp/CUDA import.

Surfaces the operator's Image-2 science catalog (DNA / protein / particles) and
the integrated NVIDIA Warp particle-sim. Anchored to the `simulation` REPL kind
in config/execution/m023-execution-substrate.yaml.

CLI:
  science.py list [--json]          catalog, grouped by scientific domain
  science.py status [--json]        integrated tools + warp installed?/device/version
                                    + per-tool live state (SDD-301 readiness)
  science.py run [--json] [ARGS]    run the Warp particle sim (delegates to warp-runner)
  science.py history [--limit N] [--json]
                                    the Warp run history (newest first) + per-device
                                    median wall_ms (SDD-301); store =
                                    SOVEREIGN_OS_SCIENCE_RUNS env or
                                    ~/.local/state/sovereign-os/science-runs.jsonl
  science.py install [--json]       print how to install the integrated tools (advisory)
  science.py info <id> [--json]     one tool's full detail

Exit codes: 0 clean, 2 usage / unknown tool.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / "config" / "science-tools.yaml"
WARP_RUNNER = REPO_ROOT / "scripts" / "science" / "warp-runner.py"

# Model-vault location for artifact detection — the same convention as
# scripts/models/pull.sh (SOVEREIGN_OS_MODELS_DIR, default /mnt/vault/models).
MODELS_DIR_ENV = "SOVEREIGN_OS_MODELS_DIR"
DEFAULT_MODELS_DIR = Path("/mnt/vault/models")

# HuggingFace cache root — HF_HOME convention (huggingface_hub), fallback to
# the standard user cache. Resolved at call time so tests can point it away.
HF_CACHE_ENV = "HF_HOME"
DEFAULT_HF_CACHE = Path("~/.cache/huggingface")


def load_catalog() -> dict[str, Any]:
    try:
        import yaml  # PyYAML — a soft dep the repo's other config readers use
    except ImportError:
        return {"error": "python3-yaml not installed", "tools": []}
    try:
        with CATALOG_FILE.open() as f:
            return (yaml.safe_load(f) or {}).get("catalog", {}) or {"tools": []}
    except OSError as exc:
        return {"error": str(exc), "tools": []}


def tools() -> list[dict[str, Any]]:
    return load_catalog().get("tools", []) or []


def warp_capture(*args: str) -> dict[str, Any]:
    """Shell warp-runner.py with --json and parse the result. Never raises."""
    try:
        r = subprocess.run(
            [sys.executable, str(WARP_RUNNER), *args, "--json"],
            capture_output=True, text=True, timeout=180, cwd=str(REPO_ROOT), check=False,
        )
        if r.stdout.strip():
            return json.loads(r.stdout)
        return {"error": r.stderr.strip() or "no output", "returncode": r.returncode}
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def warp_stream(extra: list[str], json_out: bool) -> int:
    """Delegate a Warp run straight to warp-runner.py, streaming its output."""
    cmd = [sys.executable, str(WARP_RUNNER), "run", *extra]
    if json_out:
        cmd.append("--json")
    try:
        return subprocess.run(cmd, cwd=str(REPO_ROOT), check=False).returncode
    except OSError as exc:
        print(f"error: cannot launch warp-runner: {exc}", file=sys.stderr)
        return 1


# ── per-tool readiness (SDD-301) ─────────────────────────────────────────────

def _hf_hub_root() -> Path:
    env = os.environ.get(HF_CACHE_ENV, "").strip()
    return (Path(env).expanduser() if env else DEFAULT_HF_CACHE.expanduser()) / "hub"


def _models_dir() -> Path:
    env = os.environ.get(MODELS_DIR_ENV, "").strip()
    return Path(env).expanduser() if env else DEFAULT_MODELS_DIR


def _hf_artifacts_present(ref: str) -> bool:
    """Is an HF model's artifact resident? Checked in the HF hub cache
    (models--org--name with a non-empty snapshots dir) or the sovereign model
    vault (by the repo basename)."""
    hub = _hf_hub_root() / f"models--{ref.replace('/', '--')}"
    snaps = hub / "snapshots"
    try:
        if snaps.is_dir() and any(snaps.iterdir()):
            return True
    except OSError:
        pass
    name = ref.rsplit("/", 1)[-1]
    return (_models_dir() / name).is_dir()


def _import_ok(module: str) -> bool | None:
    """Is a python module importable? None = could not determine (unknown)."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", module or ""):
        return None  # catalog typo — never shell-interpolate
    try:
        r = subprocess.run([sys.executable, "-c", f"import {module}"],
                           capture_output=True, timeout=60, check=False)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None


def detect_tool(t: dict[str, Any]) -> dict[str, Any]:
    """Live per-tool state (SDD-301): installed / artifacts-present /
    downloadable / unknown. The `detect` spec in the catalog names the primary
    artifact check; an optional `detect.import_module` must ALSO import for the
    state to upgrade to `installed`. Detection failures report `unknown`, never
    a fake `installed` (SB-077)."""
    det = t.get("detect") or {}
    method = det.get("method") or t["install"]["method"]
    ref = det.get("ref") or t["install"]["ref"]
    state = "unknown"
    if method == "import":
        ok = _import_ok(ref)
        state = "installed" if ok else ("unknown" if ok is None else "downloadable")
    elif method == "pip":
        ok = _import_ok(ref) if ref else None
        state = "installed" if ok else ("unknown" if ok is None else "downloadable")
    elif method == "hf":
        present = _hf_artifacts_present(ref)
        state = "artifacts-present" if present else "downloadable"
        mod = det.get("import_module")
        if present and mod:
            ok = _import_ok(mod)
            if ok:
                state = "installed"
            elif ok is None:
                state = "artifacts-present"  # keep: weights are the primary artifact
    elif method == "checkout":
        p = Path(ref).expanduser() if not str(ref).startswith(("http", "git@", "git:")) else None
        state = "installed" if (p is not None and p.is_dir()) else "downloadable"
    return {
        "id": t["id"],
        "state": state,
        "install_cmd": install_cmd(t),
        "size_gb": t.get("size_gb"),
        "vram_gb": t.get("vram_gb"),
    }


def install_cmd(t: dict[str, Any]) -> str:
    """The operator-facing command that gets this tool resident (copy-able;
    execution is the operator's — this surface never downloads)."""
    m, ref = t["install"]["method"], t["install"]["ref"]
    if m == "pip":
        return f"pip install {ref}"
    if m == "hf":
        return f"hf download {ref}"
    if str(ref).startswith(("http", "git@", "git:")):
        return f"git clone {ref}"
    return f"git clone {ref} <path>"  # github method with a non-URL ref (defensive)


def tools_status() -> list[dict[str, Any]]:
    return [detect_tool(t) for t in tools()]


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_list(json_out: bool) -> int:
    ts = tools()
    if json_out:
        print(json.dumps({"tools": ts}, indent=2))
        return 0
    print("── R558 sovereign-os science-tools (SDD-070) ──")
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for t in ts:
        by_domain.setdefault(t["domain"], []).append(t)
    for domain in ("particles", "dna", "protein"):
        ds = by_domain.get(domain, [])
        if not ds:
            continue
        print(f"\n  {domain}:")
        for t in ds:
            mark = "●" if t["status"] == "integrated" else "○"
            print(f"    {mark} {t['id']:<22} {t['name']:<28} "
                  f"[{t['status']}] tiers={','.join(t['tiers'])}")
    print("\n  ● integrated (install + runner + panel)   ○ cataloged (data only)")
    return 0


def cmd_status(json_out: bool) -> int:
    warp = warp_capture("status")
    integrated = [t["id"] for t in tools() if t.get("status") == "integrated"]
    payload = {"integrated_tools": integrated, "warp": warp, "tools_status": tools_status()}
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── R558 sovereign-os science · status (SDD-070 / SDD-301) ──")
    print(f"  integrated: {', '.join(integrated) or '(none)'}")
    if warp.get("installed"):
        print(f"  warp-lang:  installed (v{warp.get('version') or '?'})")
        print(f"  cuda:       {'available' if warp.get('cuda_available') else 'not available (CPU fallback)'}")
        print(f"  devices:    {warp.get('devices') or []}")
    else:
        print("  warp-lang:  NOT installed — run `sovereign-osctl science install`")
    print("\n  per-tool readiness (live):")
    for s in payload["tools_status"]:
        extra = []
        if s.get("size_gb") is not None:
            extra.append(f"~{s['size_gb']} GB")
        if s.get("vram_gb") is not None:
            extra.append(f"≥{s['vram_gb']} GB VRAM")
        tail = ("  [" + ", ".join(extra) + "]") if extra else ""
        print(f"    {s['state']:<17} {s['id']}{tail}")
    return 0


def cmd_install(json_out: bool) -> int:
    """Advisory: print how each integrated tool is obtained (the actual install
    is the first-boot hook / operator-deps, gated per SDD-030 — this never
    mutates)."""
    integrated = [t for t in tools() if t.get("status") == "integrated"]
    if json_out:
        print(json.dumps({"install": [
            {"id": t["id"], "method": t["install"]["method"], "ref": t["install"]["ref"]}
            for t in integrated
        ]}, indent=2))
        return 0
    print("── R558 sovereign-os science · install (advisory) ──")
    for t in integrated:
        m, ref = t["install"]["method"], t["install"]["ref"]
        how = f"pip install {ref}" if m == "pip" else f"{m}: {ref}"
        print(f"  {t['id']}: {how}")
    print("\n  First boot runs scripts/hooks/post-install/warp-setup.sh automatically;")
    print("  or declare in /etc/sovereign-os/operator-deps.toml [pip] (SDD-030).")
    return 0


def cmd_info(tool_id: str, json_out: bool) -> int:
    t = next((x for x in tools() if x["id"] == tool_id), None)
    if t is None:
        print(f"error: unknown science tool '{tool_id}' "
              f"(see `science list`)", file=sys.stderr)
        return 2
    if json_out:
        print(json.dumps(t, indent=2))
        return 0
    print(f"── {t['name']} ({t['id']}) ──")
    print(f"  domain:   {t['domain']}")
    print(f"  kind:     {t['kind']}")
    print(f"  install:  {t['install']['method']} — {t['install']['ref']}")
    print(f"  tiers:    {', '.join(t['tiers'])}   cpu_capable={t['cpu_capable']}")
    print(f"  status:   {t['status']}")
    if t.get("source"):
        print(f"  source:   {t['source']}")
    if t.get("notes"):
        print(f"  notes:    {t['notes'].strip()}")
    return 0


def cmd_history(json_out: bool, limit: int | None) -> int:
    """Delegate the run history to warp-runner.py (single source for the store
    path + bound). Stdlib-only surface; never imports warp."""
    cmd = [sys.executable, str(WARP_RUNNER), "history"]
    if limit:
        cmd += ["--limit", str(limit)]
    if json_out:
        cmd.append("--json")
    try:
        return subprocess.run(cmd, cwd=str(REPO_ROOT), check=False).returncode
    except OSError as exc:
        print(f"error: cannot launch warp-runner: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="R558 (SDD-070) science-tools operator CLI.")
    sub = p.add_subparsers(dest="cmd")
    for name in ("list", "status", "install"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    sp_info = sub.add_parser("info")
    sp_info.add_argument("id")
    sp_info.add_argument("--json", action="store_true")
    # `run` parses its flags natively (SDD-301 fix): the old REMAINDER form
    # rejected the documented `--device/--particles/--steps` syntax (argparse
    # treats options before the first positional as its own). Flags are
    # forwarded to warp-runner only when set, so the runner's config file
    # still supplies defaults.
    sp_run = sub.add_parser("run")
    sp_run.add_argument("--json", action="store_true")
    sp_run.add_argument("--device", choices=["auto", "cuda", "cpu"])
    sp_run.add_argument("--particles", type=int)
    sp_run.add_argument("--steps", type=int)
    sp_run.add_argument("--config")
    sp_run.add_argument("--emit-metrics", action="store_true")
    sp_hist = sub.add_parser("history")
    sp_hist.add_argument("--json", action="store_true")
    sp_hist.add_argument("--limit", type=int)
    args = p.parse_args(argv)
    cmd = args.cmd or "list"

    if cmd == "list":
        return cmd_list(args.json)
    if cmd == "status":
        return cmd_status(args.json)
    if cmd == "install":
        return cmd_install(args.json)
    if cmd == "info":
        return cmd_info(args.id, args.json)
    if cmd == "run":
        extra: list[str] = []
        if args.device:
            extra += ["--device", args.device]
        if args.particles is not None:
            extra += ["--particles", str(args.particles)]
        if args.steps is not None:
            extra += ["--steps", str(args.steps)]
        if args.config:
            extra += ["--config", args.config]
        if args.emit_metrics:
            extra += ["--emit-metrics"]
        return warp_stream(extra, args.json)
    if cmd == "history":
        return cmd_history(args.json, args.limit)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
