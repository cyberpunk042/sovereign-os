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
  science.py run [--json] [ARGS]    run the Warp particle sim (delegates to warp-runner)
  science.py install [--json]       print how to install the integrated tools (advisory)
  science.py info <id> [--json]     one tool's full detail

Exit codes: 0 clean, 2 usage / unknown tool.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / "config" / "science-tools.yaml"
WARP_RUNNER = REPO_ROOT / "scripts" / "science" / "warp-runner.py"


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
    payload = {"integrated_tools": integrated, "warp": warp}
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── R558 sovereign-os science · status (SDD-070) ──")
    print(f"  integrated: {', '.join(integrated) or '(none)'}")
    if warp.get("installed"):
        print(f"  warp-lang:  installed (v{warp.get('version') or '?'})")
        print(f"  cuda:       {'available' if warp.get('cuda_available') else 'not available (CPU fallback)'}")
        print(f"  devices:    {warp.get('devices') or []}")
    else:
        print("  warp-lang:  NOT installed — run `sovereign-osctl science install`")
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="R558 (SDD-070) science-tools operator CLI.")
    sub = p.add_subparsers(dest="cmd")
    for name in ("list", "status", "install"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    sp_info = sub.add_parser("info")
    sp_info.add_argument("id")
    sp_info.add_argument("--json", action="store_true")
    sp_run = sub.add_parser("run")
    sp_run.add_argument("--json", action="store_true")
    sp_run.add_argument("rest", nargs=argparse.REMAINDER,
                        help="passed through to warp-runner.py run (e.g. --device cpu --particles N)")
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
        return warp_stream(args.rest or [], args.json)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
