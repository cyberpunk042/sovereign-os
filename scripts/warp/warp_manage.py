#!/usr/bin/env python3
"""scripts/warp/warp_manage.py — SDD-300 Warp management operator CLI.

The stdlib-only (+ optional PyYAML) operator surface for the Warp management
panel: the warp-solar-system-shaders project (an NVIDIA-Warp procedural
rendering engine — a scene registry + lib packages + example runners).

Reads config/warp-catalog.yaml (the committed, generated catalog; the shaders
project is not resident on the host, so the catalog is the source of truth for
listing + relations). Execution (`render` / `bench`) shells to the project's own
runners WHEN a checkout is present (WARP_SHADERS_ROOT or a default path) and
degrades to an honest exit-0 banner when it isn't — the same "never fail on a
box without the tool" doctrine SDD-070 uses for Warp.

This CLI is the gated verb the cockpit exec-rail (config/control-systems.yaml →
_action_exec.py → sudoers `sovereign-osctl warp render|bench *`) invokes. It
therefore validates every scene name against the catalog AND a strict token
regex, and NEVER builds a shell string (argv lists only).

CLI:
  warp list [--json] [--lib L] [--search Q]   scenes (optionally filtered)
  warp libs [--json]                          the lib packages (+ scene counts, deps)
  warp relations [--json] [--scene S] [--lib L]   the scene->lib / lib->lib graph
  warp info <scene> [--json]                  one scene's detail
  warp status [--json]                        catalog counts + is a checkout resident + warp-lang?
  warp render <scene> [--json] [-- ARGS...]   render a scene (shells render.py)
  warp bench <scene> [--json] [-- ARGS...]    benchmark a scene (shells bench.py)

Exit codes: 0 clean, 2 usage / unknown scene, 3 checkout absent (render/bench).
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
CATALOG_FILE = REPO_ROOT / "config" / "warp-catalog.yaml"

# Strict scene-name token — mirrors _action_exec._SAFE_VALUE's spirit (no
# whitespace, no shell metacharacters, no path traversal). Scene names are
# [A-Za-z0-9][A-Za-z0-9_-]*.
_SAFE_SCENE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

# Candidate checkout locations, in priority order. WARP_SHADERS_ROOT wins.
_DEFAULT_ROOTS = (
    "/opt/warp-solar-system-shaders",
    "/usr/local/share/warp-solar-system-shaders",
    str(Path.home() / "warp-solar-system-shaders"),
)


def load_catalog() -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {"error": "python3-yaml not installed", "scenes": [], "libs": []}
    try:
        with CATALOG_FILE.open(encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("catalog", {}) or {"scenes": [], "libs": []}
    except OSError as exc:
        return {"error": str(exc), "scenes": [], "libs": []}


def scenes() -> list[dict[str, Any]]:
    return load_catalog().get("scenes", []) or []


def libs() -> list[dict[str, Any]]:
    return load_catalog().get("libs", []) or []


def find_scene(name: str) -> dict[str, Any] | None:
    return next((s for s in scenes() if s["name"] == name), None)


def shaders_root() -> Path | None:
    """The resident warp-solar-system-shaders checkout, or None."""
    env = os.environ.get("WARP_SHADERS_ROOT")
    candidates = [env] if env else []
    candidates += list(_DEFAULT_ROOTS)
    for c in candidates:
        if not c:
            continue
        p = Path(c).expanduser()
        if (p / "render.py").is_file() and (p / "warp_shaders").is_dir():
            return p
    return None


def warp_installed() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("warp") is not None
    except (ImportError, ValueError):
        return False


# ── read commands ──────────────────────────────────────────────────────────

def cmd_list(json_out: bool, lib: str | None, search: str | None) -> int:
    ss = scenes()
    if lib:
        ss = [s for s in ss if lib in s.get("libs", [])]
    if search:
        q = search.lower()
        ss = [s for s in ss if q in s["name"].lower() or q in s.get("summary", "").lower()]
    if json_out:
        print(json.dumps({"scenes": ss, "count": len(ss)}, indent=2))
        return 0
    filt = (f" · lib={lib}" if lib else "") + (f" · search={search!r}" if search else "")
    print(f"── SDD-300 warp scenes ({len(ss)}){filt} ──")
    for s in ss:
        print(f"  {s['name']:<22} [{','.join(s.get('libs', [])) or '-'}]  {s.get('summary', '')}")
    return 0


def cmd_libs(json_out: bool) -> int:
    ls = libs()
    if json_out:
        print(json.dumps({"libs": ls, "count": len(ls)}, indent=2))
        return 0
    print(f"── SDD-300 warp libs ({len(ls)}) ──")
    for lib in sorted(ls, key=lambda x: -x["scene_count"]):
        deps = ",".join(lib.get("depends_on", [])) or "-"
        print(f"  {lib['id']:<16} {lib['kind']:<8} scenes={lib['scene_count']:<4} "
              f"deps=[{deps}]  {lib.get('summary', '')}")
    return 0


def cmd_relations(json_out: bool, scene: str | None, lib: str | None) -> int:
    scene_edges = [{"from": s["name"], "to": s.get("libs", [])}
                   for s in scenes()
                   if (not scene or s["name"] == scene) and (not lib or lib in s.get("libs", []))]
    lib_edges = [{"from": lb["id"], "to": lb.get("depends_on", [])}
                 for lb in libs() if (not lib or lb["id"] == lib)]
    payload = {"scene_to_lib": scene_edges, "lib_to_lib": lib_edges}
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── SDD-300 warp relations · scene → lib ──")
    for e in scene_edges:
        print(f"  {e['from']:<22} → {', '.join(e['to']) or '-'}")
    print("\n── lib → lib ──")
    for e in lib_edges:
        print(f"  {e['from']:<16} → {', '.join(e['to']) or '-'}")
    return 0


def cmd_info(name: str, json_out: bool) -> int:
    s = find_scene(name)
    if s is None:
        print(f"error: unknown scene '{name}' (see `warp list`)", file=sys.stderr)
        return 2
    if json_out:
        print(json.dumps(s, indent=2))
        return 0
    print(f"── scene: {s['name']} ──")
    print(f"  file:    {s['file']}")
    print(f"  libs:    {', '.join(s.get('libs', [])) or '-'}")
    if s.get("multi"):
        print("  multi:   this module exposes several scenes (see render.py --list)")
    print(f"  summary: {s.get('summary', '')}")
    return 0


def cmd_status(json_out: bool) -> int:
    cat = load_catalog()
    root = shaders_root()
    payload = {
        "scenes": len(cat.get("scenes", [])),
        "libs": len(cat.get("libs", [])),
        "project": cat.get("project"),
        "checkout_resident": root is not None,
        "checkout_path": str(root) if root else None,
        "warp_installed": warp_installed(),
    }
    if json_out:
        print(json.dumps(payload, indent=2))
        return 0
    print("── SDD-300 warp · status ──")
    print(f"  catalog:   {payload['scenes']} scenes · {payload['libs']} libs "
          f"({payload['project']})")
    if root:
        print(f"  checkout:  resident at {root}")
    else:
        print("  checkout:  NOT resident — render/bench will print how to obtain it")
    print(f"  warp-lang: {'installed' if payload['warp_installed'] else 'NOT installed'}")
    return 0


# ── execute commands (the gated verbs) ──────────────────────────────────────

def _validate_scene(name: str) -> str | None:
    """Return an error string if the scene name is unsafe or unknown, else None."""
    if not _SAFE_SCENE.fullmatch(name):
        return f"scene name {name!r} rejected (unsafe token)"
    if find_scene(name) is None:
        return f"unknown scene {name!r} (see `warp list`)"
    return None


def _absent_banner(verb: str, scene: str, json_out: bool) -> int:
    src = load_catalog().get("source", "the warp-solar-system-shaders repo")
    msg = (f"warp {verb}: the warp-solar-system-shaders checkout is not resident on "
           f"this host — nothing to run. Obtain it (git clone {src}) and set "
           f"WARP_SHADERS_ROOT, or install it to one of {list(_DEFAULT_ROOTS)}.")
    if json_out:
        print(json.dumps({"verb": verb, "scene": scene, "ran": False,
                          "reason": "checkout-absent", "hint": msg}, indent=2))
    else:
        print(f"── warp {verb} · {scene} ──")
        print(f"  {msg}")
    return 3


def _run_runner(runner: str, argv: list[str], json_out: bool, verb: str, scene: str) -> int:
    root = shaders_root()
    if root is None:
        return _absent_banner(verb, scene, json_out)
    cmd = [sys.executable, str(root / runner), *argv]
    try:
        rc = subprocess.run(cmd, cwd=str(root), check=False).returncode
    except OSError as exc:
        print(f"error: cannot launch {runner}: {exc}", file=sys.stderr)
        return 1
    if json_out:
        print(json.dumps({"verb": verb, "scene": scene, "ran": True,
                          "runner": runner, "returncode": rc}, indent=2))
    return rc


def cmd_render(scene: str, json_out: bool, extra: list[str]) -> int:
    err = _validate_scene(scene)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return _run_runner("render.py", ["--scene", scene, *extra], json_out, "render", scene)


def cmd_bench(scene: str, json_out: bool, extra: list[str]) -> int:
    err = _validate_scene(scene)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return _run_runner("bench.py", [scene, *extra], json_out, "bench", scene)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SDD-300 Warp management operator CLI.")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("list")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--lib")
    sp.add_argument("--search")

    for name in ("libs", "status"):
        s = sub.add_parser(name)
        s.add_argument("--json", action="store_true")

    sr = sub.add_parser("relations")
    sr.add_argument("--json", action="store_true")
    sr.add_argument("--scene")
    sr.add_argument("--lib")

    si = sub.add_parser("info")
    si.add_argument("scene")
    si.add_argument("--json", action="store_true")

    for name in ("render", "bench"):
        se = sub.add_parser(name)
        se.add_argument("scene")
        se.add_argument("--json", action="store_true")
        se.add_argument("rest", nargs=argparse.REMAINDER,
                        help="extra args passed through to the runner")

    args = p.parse_args(argv)
    cmd = args.cmd or "list"

    if cmd == "list":
        return cmd_list(args.json, args.lib, args.search)
    if cmd == "libs":
        return cmd_libs(args.json)
    if cmd == "relations":
        return cmd_relations(args.json, args.scene, args.lib)
    if cmd == "info":
        return cmd_info(args.scene, args.json)
    if cmd == "status":
        return cmd_status(args.json)
    if cmd == "render":
        return cmd_render(args.scene, args.json, args.rest or [])
    if cmd == "bench":
        return cmd_bench(args.scene, args.json, args.rest or [])
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
