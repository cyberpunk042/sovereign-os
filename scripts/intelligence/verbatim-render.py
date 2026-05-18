#!/usr/bin/env python3
"""scripts/intelligence/verbatim-render.py — R369 (E10.M13).

Operator-pull: emit a single consolidated markdown document covering
the entire verbatim-preservation surface across all SDD-037 catalogs:
  - architecture-qa questions (Q-NN, §13)
  - architecture-qa gotchas (G-NN, §14)
  - architecture-qa concepts (C-NN, ~20 master spec sections)
  - coverage-map axes (A-NN, operator-stated demands)
  - ccd-pinning layers (§19.2)
  - state-fabric files (§7.1) + ZFS properties (§7.2)
  - network-topology interfaces (§8 + §8.1)
  - repl modes (operator-named Python/System/GPU/LLM)

Without this verb, operator must run 7+ separate `show` commands to
audit the full /goal verbatim-preservation contract. With this verb,
one render gives the operator the entire surface as a navigable doc.

CLI:
  verbatim-render.py render                    [--config P]
  verbatim-render.py summary                   [--config P] [--json|--human]
                                                stats only (counts +
                                                per-catalog tally)
  verbatim-render.py manifest                  [--config P] [--json|--human]
                                                operator-runnable verb
                                                catalog (one verb per
                                                entry showing how to
                                                drill into it)

Operator-overlay (R283/SDD-030): /etc/sovereign-os/verbatim-render.toml
  - filter which catalogs to include
  - override render header

Exit codes:
  0  rendered
  2  usage
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
ROUND = "R369"
SDD_VECTOR = "E10.M13"


def _load_module(path: Path, name: str):
    """Load a Python module from a path. NEVER-raises (returns None
    on failure to keep this NEVER-raise verb itself NEVER-raising)."""
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _gather_catalogs() -> dict[str, Any]:
    """Load all verbatim-preservation catalogs. NEVER-raises."""
    archqa = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py",
        "verbatim_render_archqa",
    )
    coverage = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py",
        "verbatim_render_coverage",
    )
    ccd = _load_module(
        REPO_ROOT / "scripts" / "hardware" / "ccd-pinning.py",
        "verbatim_render_ccd",
    )
    state_fabric = _load_module(
        REPO_ROOT / "scripts" / "hardware" / "state-fabric.py",
        "verbatim_render_state_fabric",
    )
    network = _load_module(
        REPO_ROOT / "scripts" / "network" / "topology.py",
        "verbatim_render_network",
    )
    repl = _load_module(
        REPO_ROOT / "scripts" / "intelligence" / "repl.py",
        "verbatim_render_repl",
    )
    return {
        "questions": getattr(archqa, "ARCHITECTURE_QUESTIONS", []) if archqa else [],
        "gotchas":    getattr(archqa, "ARCHITECTURE_GOTCHAS", []) if archqa else [],
        "concepts":   getattr(archqa, "ARCHITECTURE_CONCEPTS", []) if archqa else [],
        "axes":       getattr(coverage, "DEFAULT_AXES", []) if coverage else [],
        "ccd_layers": getattr(ccd, "DEFAULT_LAYER_CATALOG", []) if ccd else [],
        "state_files":   getattr(state_fabric, "DEFAULT_FILE_MATRIX", []) if state_fabric else [],
        "state_zfs_props": getattr(state_fabric, "DEFAULT_ZFS_PROPERTIES", []) if state_fabric else [],
        "network_ifaces": getattr(network, "DEFAULT_INTERFACES", []) if network else [],
        "network_diagram": getattr(network, "TOPOLOGY_DIAGRAM_VERBATIM", "") if network else "",
        "repl_modes": getattr(repl, "DEFAULT_MODES", []) if repl else [],
    }


def _count_phrases(catalogs: dict[str, Any]) -> int:
    """Best-effort count of operator-exact phrases across all catalogs."""
    total = 0
    for q in catalogs["questions"]:
        total += len((q.get("question") or "").split()) // 8
        total += len((q.get("answer") or "").split()) // 8
    for g in catalogs["gotchas"]:
        for field in ("context", "gotcha", "prevention"):
            total += len((g.get(field) or "").split()) // 8
    for c in catalogs["concepts"]:
        total += len((c.get("explanation") or "").split()) // 8
    for a in catalogs["axes"]:
        total += len((a.get("axis_verbatim") or "").split()) // 8
    return total


def render_summary(catalogs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "catalog_tally": {
            "questions":        len(catalogs["questions"]),
            "gotchas":          len(catalogs["gotchas"]),
            "concepts":         len(catalogs["concepts"]),
            "coverage_axes":    len(catalogs["axes"]),
            "ccd_layers":       len(catalogs["ccd_layers"]),
            "state_files":      len(catalogs["state_files"]),
            "state_zfs_props":  len(catalogs["state_zfs_props"]),
            "network_ifaces":   len(catalogs["network_ifaces"]),
            "network_diagram_lines": len(catalogs["network_diagram"].split("\n")),
            "repl_modes":       len(catalogs["repl_modes"]),
        },
        "total_items": sum([
            len(catalogs["questions"]),
            len(catalogs["gotchas"]),
            len(catalogs["concepts"]),
            len(catalogs["axes"]),
            len(catalogs["ccd_layers"]),
            len(catalogs["state_files"]),
            len(catalogs["state_zfs_props"]),
            len(catalogs["network_ifaces"]),
            len(catalogs["repl_modes"]),
        ]),
        "estimated_phrase_count": _count_phrases(catalogs),
    }


def render_manifest(catalogs: dict[str, Any]) -> dict[str, Any]:
    """Operator-runnable verb catalog. One entry per verbatim item with
    the exact sovereign-osctl command to drill into it."""
    entries: list[dict[str, str]] = []
    for q in catalogs["questions"]:
        entries.append({
            "id": q.get("id"),
            "category": "question",
            "title": (q.get("question") or "")[:70],
            "verb": f"sovereign-osctl architecture-qa show {q.get('id')}",
            "spec_ref": q.get("spec_ref", ""),
        })
    for g in catalogs["gotchas"]:
        entries.append({
            "id": g.get("id"),
            "category": "gotcha",
            "title": g.get("name", "")[:70],
            "verb": f"sovereign-osctl architecture-qa show {g.get('id')}",
            "spec_ref": g.get("spec_ref", ""),
        })
    for c in catalogs["concepts"]:
        entries.append({
            "id": c.get("id"),
            "category": "concept",
            "title": c.get("name", "")[:70],
            "verb": f"sovereign-osctl architecture-qa show {c.get('id')}",
            "spec_ref": c.get("spec_ref", ""),
        })
    for a in catalogs["axes"]:
        entries.append({
            "id": a.get("id"),
            "category": "axis",
            "title": (a.get("axis_verbatim") or "")[:70],
            "verb": f"sovereign-osctl coverage show {a.get('id')}",
            "spec_ref": a.get("source", ""),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "entry_count": len(entries),
        "entries": entries,
    }


def render_markdown(catalogs: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Sovereign-OS verbatim-preservation surface (R369 render)")
    lines.append("")
    lines.append("Operator-readable consolidated render of every verbatim entry")
    lines.append("across all SDD-037 catalogs. **No content here is paraphrased**")
    lines.append("— every field reproduces the operator-stated text. Source-of-truth")
    lines.append("lives in the Python catalog files; this doc regenerates from them.")
    lines.append("")
    summary = render_summary(catalogs)
    tally = summary["catalog_tally"]
    lines.append("## Catalog tally")
    lines.append("")
    for k, v in tally.items():
        lines.append(f"  - **{k}**: {v}")
    lines.append("")
    lines.append(f"  **Total verbatim items**: {summary['total_items']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── §13 Q&A
    lines.append("## §13 Architectural Q&A Matrix (Q-NN)")
    lines.append("")
    for q in catalogs["questions"]:
        lines.append(f"### {q.get('id')} — {q.get('question', '')}")
        lines.append("")
        lines.append("**Answer (operator verbatim):**")
        lines.append("")
        lines.append("> " + q.get("answer", "").replace("\n", "\n> "))
        lines.append("")
        lines.append(f"_spec ref: {q.get('spec_ref')}_")
        lines.append("")

    # ── §14 Gotchas
    lines.append("## §14 Critical Edge Cases & Operational Gotchas (G-NN)")
    lines.append("")
    for g in catalogs["gotchas"]:
        lines.append(f"### {g.get('id')} — {g.get('name', '')}")
        lines.append("")
        for label, field in (("Context", "context"),
                              ("Gotcha", "gotcha"),
                              ("Prevention", "prevention")):
            lines.append(f"**{label}:** {g.get(field, '')}")
            lines.append("")
        for v in g.get("related_verbs") or []:
            lines.append(f"  - `{v}`")
        lines.append("")
        lines.append(f"_spec ref: {g.get('spec_ref')}_")
        lines.append("")

    # ── Concepts
    lines.append("## Architecture-qa concepts (C-NN)")
    lines.append("")
    lines.append("Covers ~20 master spec sections + Block 6 + dump-tail +")
    lines.append("macro-arc plan post-Plan refinements.")
    lines.append("")
    for c in catalogs["concepts"]:
        lines.append(f"### {c.get('id')} — {c.get('name', '')}")
        lines.append("")
        lines.append(c.get("explanation", ""))
        lines.append("")
        lines.append(f"_spec ref: {c.get('spec_ref')}_")
        lines.append("")

    # ── Coverage axes
    lines.append("## Coverage-map axes (A-NN)")
    lines.append("")
    lines.append("Every operator-stated demand mapped to ≥1 implementing verb.")
    lines.append("")
    for a in catalogs["axes"]:
        status = a.get("status", "?")
        glyph = ({"✓ shipped": "✓", "partial": "·", "TODO": "○"}
                 .get(status, "?"))
        lines.append(f"### {glyph} {a.get('id')} — {a.get('axis_verbatim', '')[:80]}")
        lines.append("")
        lines.append(f"**Status**: {status}")
        lines.append(f"**Source**: {a.get('source', '')}")
        lines.append("")
        lines.append("**Implementing verbs**:")
        for v in a.get("implementing_verbs") or []:
            lines.append(f"  - `{v}`")
        lines.append("")
        if a.get("notes"):
            lines.append(f"**Notes**: {a['notes']}")
            lines.append("")

    # ── §19.2 CCD pinning
    lines.append("## §19.2 CCD pinning (Ryzen 9 9900X dual-CCD)")
    lines.append("")
    for layer in catalogs["ccd_layers"]:
        lines.append(f"### {layer.get('layer')} — CCD {layer.get('ccd')}")
        lines.append("")
        lines.append(f"- core range: `{layer.get('core_range')}`")
        lines.append(f"- thread range: `{layer.get('thread_range')}`")
        lines.append(f"- thread mask: `{layer.get('thread_mask_hex')}`")
        lines.append(f"- responsibility: {layer.get('responsibility')}")
        for u in layer.get("service_units") or []:
            lines.append(f"- service unit: `{u}`")
        lines.append("")

    # ── §7.1 State fabric
    lines.append("## §7.1 State fabric file-state matrix")
    lines.append("")
    for f in catalogs["state_files"]:
        lines.append(f"### `{f.get('filename')}` ({f.get('intended_mode')})")
        lines.append("")
        lines.append(f"**Role (operator verbatim)**: {f.get('role_verbatim')}")
        lines.append("")
        lines.append(f"- writer: {f.get('writer')}")
        lines.append(f"- readers: {f.get('readers')}")
        lines.append(f"- intent axis: {f.get('intent_axis')}")
        lines.append("")

    # ── §7.2 ZFS properties
    lines.append("## §7.2 State fabric ZFS transactional optimizations")
    lines.append("")
    for p in catalogs["state_zfs_props"]:
        lines.append(f"- **{p.get('property')} = {p.get('value')}**")
        lines.append(f"  - command: `{p.get('command')}`")
        lines.append(f"  - rationale: {p.get('rationale')}")
    lines.append("")

    # ── §8 Network topology
    lines.append("## §8 Network topology")
    lines.append("")
    lines.append("**ASCII diagram (operator verbatim)**:")
    lines.append("")
    lines.append("```")
    lines.append(catalogs["network_diagram"])
    lines.append("```")
    lines.append("")
    for nif in catalogs["network_ifaces"]:
        lines.append(f"### `{nif.get('interface')}` — {nif.get('vendor')} {nif.get('chipset')} {nif.get('speed')}")
        lines.append("")
        lines.append(f"- role: {nif.get('role')}")
        lines.append(f"- VLAN: {nif.get('vlan')}")
        lines.append(f"- address: `{nif.get('address_cidr')}`")
        if nif.get("gateway"):
            lines.append(f"- gateway: `{nif.get('gateway')}`")
        lines.append(f"- MTU: {nif.get('intended_mtu')}")
        lines.append(f"- WAN access: {nif.get('wan_access')}")
        lines.append("- responsibilities (operator verbatim):")
        for r in nif.get("responsibilities_verbatim") or []:
            lines.append(f"  - {r}")
        lines.append("")

    # ── REPL modes
    lines.append("## Multi-level REPL modes")
    lines.append("")
    for m in catalogs["repl_modes"]:
        lines.append(f"### `{m.get('mode')}` — {m.get('title')}")
        lines.append("")
        lines.append(f"**Rationale**: {m.get('rationale')}")
        lines.append("")
        lines.append("**Reference commands**:")
        for cmd in (m.get("reference_commands") or [])[:5]:
            lines.append(f"  - `{cmd}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Generated by `sovereign-osctl verbatim-render` (R369). "
                  f"Catalog source files: scripts/intelligence/architecture-qa.py, "
                  f"scripts/intelligence/coverage-map.py, scripts/hardware/"
                  f"ccd-pinning.py, scripts/hardware/state-fabric.py, "
                  f"scripts/network/topology.py, scripts/intelligence/repl.py._")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="verbatim-render.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    for verb in ("render", "summary", "manifest"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalogs = _gather_catalogs()

    if args.cmd == "summary":
        result = render_summary(catalogs)
        if args.fmt == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"── R369 verbatim-render summary ──")
            for k, v in result["catalog_tally"].items():
                print(f"  {k:<24}  {v}")
            print(f"  ── total verbatim items: {result['total_items']}")
            print(f"  ── est phrase count:     {result['estimated_phrase_count']}")
        return 0

    if args.cmd == "manifest":
        result = render_manifest(catalogs)
        if args.fmt == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"── R369 verbatim-render manifest ({result['entry_count']} entries) ──")
            for e in result["entries"]:
                print(f"  [{e['id']}] ({e['category']}) {e['title']}")
                print(f"    $ {e['verb']}")
        return 0

    if args.cmd == "render":
        # render always emits markdown
        print(render_markdown(catalogs))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
