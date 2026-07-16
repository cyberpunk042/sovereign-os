#!/usr/bin/env python3
"""scripts/warp/gen_catalog.py — regenerate config/warp-catalog.yaml from a
warp-solar-system-shaders checkout (SDD-300 Warp management panel).

The Warp management panel surfaces the `warp-solar-system-shaders` project (an
NVIDIA-Warp procedural rendering engine: a scene registry + lib packages + example
runners). That project is NOT resident on the sovereign-os host, so its catalog is
generated here and COMMITTED as the panel's source of truth — the exact pattern
config/science-tools.yaml uses for the science-tools surface.

This generator parses the project's `warp_shaders/` package with the stdlib `ast`
module ONLY — it NEVER imports warp / CUDA / numpy — so it runs on the dev/CI box
with no GPU and no heavy deps. It extracts:

  * scenes  — every scenes/*.py exposing SCENE (name + one-line summary + the
              warp_shaders libs it imports)
  * libs    — the warp_shaders sub-packages/modules (engine, sdf, procedural, …),
              each with a one-line summary, scene-usage count, and the OTHER libs
              it imports (lib -> lib edges)
  * edges   — scene -> lib relations (the dependency graph the panel draws)

Reproducible: sorted keys + sorted collections → byte-identical output for the
same checkout (mirrors the repo's reproducibility discipline).

Usage:
  WARP_SHADERS_ROOT=/path/to/warp-solar-system-shaders \
    python3 scripts/warp/gen_catalog.py            # writes config/warp-catalog.yaml
  ... --stdout                                     # print instead of writing
  ... --check                                      # exit 3 if the committed file is stale
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = REPO_ROOT / "config" / "warp-catalog.yaml"

# Core modules that are the registry/plumbing, not a "lib" a scene depends on.
_NOT_A_LIB = {"scene", "scenes", "__init__", "__pycache__"}


def _discover_libs(pkg: Path) -> set[str]:
    libs: set[str] = set()
    for entry in os.listdir(pkg):
        stem = entry[:-3] if entry.endswith(".py") else entry
        if stem in _NOT_A_LIB:
            continue
        full = pkg / entry
        if full.is_dir() or entry.endswith(".py"):
            libs.add(stem)
    return libs


def _first_doc_line(tree: ast.Module) -> str:
    doc = (ast.get_docstring(tree) or "").strip()
    return doc.split("\n", 1)[0].strip() if doc else ""


def _imported_libs(tree: ast.Module, libs: set[str]) -> set[str]:
    """The warp_shaders sub-libs a module imports (relative or absolute)."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level > 0:  # `from ..engine import post` → module == 'engine[...]'
            top = node.module.split(".")[0]
        elif node.module.split(".")[0] == "warp_shaders":
            parts = node.module.split(".")
            top = parts[1] if len(parts) > 1 else ""
        else:
            continue
        if top in libs:
            used.add(top)
    return used


def _scene_name(tree: ast.Module, fallback: str) -> tuple[str, bool]:
    """Return (name, multi). `multi` is True when the module exposes a SCENES list
    (e.g. one Scene per chemical element) rather than a single SCENE — those carry
    several registry names, so the file stem is used as the catalog key and the
    runtime `render.py --list` is the authority for the individual names."""
    multi = False
    name = fallback
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = {getattr(t, "id", None) for t in node.targets}
            if "SCENES" in targets:
                multi = True
            if "SCENE" in targets and isinstance(node.value, ast.Call):
                for kw in node.value.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = str(kw.value.value)
    return name, multi


def _lib_summary(pkg: Path, lib: str) -> str:
    """One-line docstring of a lib package (__init__.py) or module (<lib>.py)."""
    for candidate in (pkg / lib / "__init__.py", pkg / f"{lib}.py"):
        if candidate.is_file():
            try:
                return _first_doc_line(ast.parse(candidate.read_text(encoding="utf-8")))
            except (SyntaxError, OSError):
                return ""
    return ""


def build_catalog(shaders_root: Path) -> dict:
    pkg = shaders_root / "warp_shaders"
    scenes_dir = pkg / "scenes"
    if not scenes_dir.is_dir():
        raise SystemExit(
            f"error: {scenes_dir} not found — set WARP_SHADERS_ROOT to a "
            "warp-solar-system-shaders checkout")

    libs = _discover_libs(pkg)
    scenes: list[dict] = []
    for fname in sorted(os.listdir(scenes_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        tree = ast.parse((scenes_dir / fname).read_text(encoding="utf-8"))
        name, multi = _scene_name(tree, fname[:-3])
        used = sorted(_imported_libs(tree, libs))
        entry = {
            "name": name,
            "file": f"warp_shaders/scenes/{fname}",
            "summary": _first_doc_line(tree),
            "libs": used,
        }
        if multi:
            entry["multi"] = True
        scenes.append(entry)
    scenes.sort(key=lambda s: s["name"])

    # lib -> lib edges + scene-usage counts + summaries.
    usage: dict[str, int] = {lib: 0 for lib in libs}
    for s in scenes:
        for lib in s["libs"]:
            usage[lib] += 1
    lib_entries: list[dict] = []
    for lib in sorted(libs):
        libdir = pkg / lib
        kind = "package" if libdir.is_dir() else "module"
        # what OTHER libs this lib imports (lib -> lib edges)
        dep: set[str] = set()
        sources = (
            [libdir / f for f in os.listdir(libdir) if f.endswith(".py")]
            if libdir.is_dir() else [pkg / f"{lib}.py"]
        )
        for src in sources:
            try:
                dep |= _imported_libs(ast.parse(src.read_text(encoding="utf-8")), libs)
            except (SyntaxError, OSError):
                continue
        dep.discard(lib)
        lib_entries.append({
            "id": lib,
            "kind": kind,
            "summary": _lib_summary(pkg, lib),
            "scene_count": usage[lib],
            "depends_on": sorted(dep),
        })

    return {
        "schema_version": "1.0.0",
        "catalog": {
            "version": "1.0.0",
            "project": "warp-solar-system-shaders",
            "source": "https://github.com/cyberpunk042/warp-solar-system-shaders",
            "engine": "NVIDIA Warp (warp-lang)",
            "description": (
                "Catalog of the warp-solar-system-shaders project — an NVIDIA-Warp "
                "procedural rendering engine. Scenes are auto-discovered @wp.kernel "
                "shaders; libs are the warp_shaders sub-packages; the relations are "
                "the scene→lib and lib→lib import graph. Generated by "
                "scripts/warp/gen_catalog.py; do not hand-edit."),
            "runners": [
                {"id": "render", "cmd": "render.py", "desc": "render a scene to PNG/GIF"},
                {"id": "bench", "cmd": "bench.py", "desc": "time scenes (ms/frame)"},
                {"id": "simulate", "cmd": "simulate.py", "desc": "nuclear/thermonuclear blast sim"},
                {"id": "reel", "cmd": "reel.py", "desc": "multi-scene showcase reel"},
            ],
            "counts": {"scenes": len(scenes), "libs": len(lib_entries)},
            "libs": lib_entries,
            "scenes": scenes,
        },
    }


def _dump(catalog: dict) -> str:
    try:
        import yaml
    except ImportError:
        raise SystemExit("error: PyYAML required (pip install pyyaml)")

    header = (
        "# sovereign-os warp-catalog — the warp-solar-system-shaders project,\n"
        "# surfaced for the Warp management panel (SDD-300).\n"
        "#\n"
        "# GENERATED — do not hand-edit. Regenerate with:\n"
        "#   WARP_SHADERS_ROOT=<checkout> python3 scripts/warp/gen_catalog.py\n"
        "#\n"
        "# scenes[].libs and libs[].depends_on ARE the relation graph the panel\n"
        "# draws (scene→lib, lib→lib). The shaders project is not resident on the\n"
        "# host, so this committed catalog is the panel's source of truth — the\n"
        "# same pattern config/science-tools.yaml uses.\n"
        "#\n"
        "# Schema: schemas/warp-catalog.schema.yaml\n"
        "#         (tests/schema/test_warp_catalog_schema_conformance.py)\n\n"
    )
    body = yaml.safe_dump(catalog, sort_keys=True, allow_unicode=True,
                          default_flow_style=False, width=100)
    return header + body


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate config/warp-catalog.yaml.")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--check", action="store_true",
                    help="exit 3 if the committed catalog is stale vs the checkout")
    args = ap.parse_args()

    root = Path(os.environ.get("WARP_SHADERS_ROOT", "")).expanduser()
    if not root:
        raise SystemExit(
            "error: set WARP_SHADERS_ROOT to a warp-solar-system-shaders checkout")
    text = _dump(build_catalog(root))

    if args.check:
        current = OUT_FILE.read_text(encoding="utf-8") if OUT_FILE.is_file() else ""
        if current != text:
            print(f"STALE: {OUT_FILE} differs from a fresh generation", file=sys.stderr)
            return 3
        print(f"OK: {OUT_FILE} matches the checkout")
        return 0
    if args.stdout:
        sys.stdout.write(text)
        return 0
    OUT_FILE.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_FILE} "
          f"({text.count(chr(10))} lines)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
