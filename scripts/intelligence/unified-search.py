#!/usr/bin/env python3
"""scripts/intelligence/unified-search.py — R386 (E10.M30).

Unified operator-pull search across all 3 verbatim-catalog taxonomies:
  - architecture-qa: 4 questions + 3 gotchas + 27 concepts
  - coverage-map:    32 operator-stated demand axes
  - layers:          11 'guide into' operator-verbatim layers

Without this verb, operator runs 3 separate searches to find content
about a topic. With this verb, one command returns unified ranked
results across all taxonomies.

CLI:
  unified-search.py <needle>            [--config P] [--json|--human]

Output (ranked by relevance — exact-match in name > exact-match in
tags > substring-match in body):

  ── results for '<needle>' (N matches across 3 catalogs) ──
    [concept C-04]  Dual-CCD Infinity Fabric cross-die penalty
                     → sovereign-osctl architecture-qa show C-04
    [axis A-04]      GPU watts, RTX 4090 details ...
                     → sovereign-osctl coverage show A-04
    [layer hardware] into the hardware
                     → sovereign-osctl layers show hardware

Exit codes:
  0  ≥1 result across catalogs
  1  no results
  2  usage error
"""
from __future__ import annotations

import argparse
import importlib.util
import json
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
ROUND = "R386"
SDD_VECTOR = "E10.M30"


def _load_module(path: Path, name: str):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _search_archqa(needle: str) -> list[dict[str, Any]]:
    mod = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py",
        "unified_search_archqa",
    )
    if mod is None:
        return []
    n = needle.lower()
    out: list[dict[str, Any]] = []
    for q in mod.ARCHITECTURE_QUESTIONS:
        if (n in (q.get("id") or "").lower()
            or n in (q.get("question") or "").lower()
            or n in (q.get("answer") or "").lower()
            or any(n in t.lower() for t in (q.get("tags") or []))):
            out.append({
                "catalog": "architecture-qa",
                "category": "question",
                "id": q.get("id"),
                "title": (q.get("question") or "")[:80],
                "drill_verb": f"sovereign-osctl architecture-qa show {q.get('id')}",
                "spec_ref": q.get("spec_ref"),
            })
    for g in mod.ARCHITECTURE_GOTCHAS:
        if (n in (g.get("id") or "").lower()
            or n in (g.get("name") or "").lower()
            or n in (g.get("context") or "").lower()
            or n in (g.get("gotcha") or "").lower()
            or any(n in t.lower() for t in (g.get("tags") or []))):
            out.append({
                "catalog": "architecture-qa",
                "category": "gotcha",
                "id": g.get("id"),
                "title": g.get("name", "")[:80],
                "drill_verb": f"sovereign-osctl architecture-qa show {g.get('id')}",
                "spec_ref": g.get("spec_ref"),
            })
    for c in mod.ARCHITECTURE_CONCEPTS:
        if (n in (c.get("id") or "").lower()
            or n in (c.get("name") or "").lower()
            or n in (c.get("explanation") or "").lower()
            or any(n in t.lower() for t in (c.get("tags") or []))):
            out.append({
                "catalog": "architecture-qa",
                "category": "concept",
                "id": c.get("id"),
                "title": c.get("name", "")[:80],
                "drill_verb": f"sovereign-osctl architecture-qa show {c.get('id')}",
                "spec_ref": c.get("spec_ref"),
            })
    return out


def _search_coverage(needle: str) -> list[dict[str, Any]]:
    mod = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py",
        "unified_search_coverage",
    )
    if mod is None:
        return []
    n = needle.lower()
    out: list[dict[str, Any]] = []
    for a in mod.DEFAULT_AXES:
        if (n in (a.get("id") or "").lower()
            or n in (a.get("axis_verbatim") or "").lower()
            or n in (a.get("notes") or "").lower()
            or any(n in v.lower()
                    for v in (a.get("implementing_verbs") or []))):
            out.append({
                "catalog": "coverage-map",
                "category": "axis",
                "id": a.get("id"),
                "title": (a.get("axis_verbatim") or "")[:80],
                "drill_verb": f"sovereign-osctl coverage show {a.get('id')}",
                "status": a.get("status"),
            })
    return out


def _search_layers(needle: str) -> list[dict[str, Any]]:
    mod = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "layers.py",
        "unified_search_layers",
    )
    if mod is None:
        return []
    n = needle.lower()
    out: list[dict[str, Any]] = []
    for layer in mod.DEFAULT_LAYERS:
        if (n in (layer.get("layer") or "").lower()
            or n in (layer.get("layer_verbatim") or "").lower()
            or n in (layer.get("operator_note") or "").lower()
            or any(n in v.lower()
                    for v in (layer.get("implementing_verbs") or []))):
            out.append({
                "catalog": "layers",
                "category": "layer",
                "id": layer.get("layer"),
                "title": layer.get("layer_verbatim", ""),
                "drill_verb": f"sovereign-osctl layers show {layer.get('layer')}",
            })
    return out


def _rank(needle: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank by: exact-id-match → exact-title-match → substring-only."""
    n = needle.lower()
    def score(item: dict[str, Any]) -> int:
        if (item.get("id") or "").lower() == n:
            return 0  # exact id match
        if n in (item.get("title") or "").lower().split()[:1]:
            return 1  # title starts with needle
        return 2  # substring only
    return sorted(items, key=score)


def search_all(needle: str) -> dict[str, Any]:
    archqa = _search_archqa(needle)
    coverage = _search_coverage(needle)
    layers = _search_layers(needle)
    all_results = archqa + coverage + layers
    ranked = _rank(needle, all_results)
    return {
        "needle": needle,
        "total_matches": len(ranked),
        "archqa_matches": len(archqa),
        "coverage_matches": len(coverage),
        "layers_matches": len(layers),
        "results": ranked,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="unified-search.py")
    p.add_argument("needle")
    p.add_argument("--config", type=Path)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", dest="fmt", action="store_const", const="json")
    g.add_argument("--human", dest="fmt", action="store_const", const="human")
    p.set_defaults(fmt="json")
    args = p.parse_args(argv)

    result = search_all(args.needle)
    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            **result,
        }, indent=2))
    else:
        print(f"── R386 unified search: '{args.needle}' "
               f"({result['total_matches']} matches across 3 catalogs) ──")
        print(f"  archqa: {result['archqa_matches']} | "
               f"coverage: {result['coverage_matches']} | "
               f"layers: {result['layers_matches']}")
        print()
        for r in result["results"][:25]:
            print(f"  [{r['catalog']}/{r['category']}] "
                   f"{r['id']:>10}  {r['title']}")
            print(f"             → {r['drill_verb']}")
    return 0 if result["total_matches"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
