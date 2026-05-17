#!/usr/bin/env python3
"""scripts/services/dependency-graph.py — R277 (E2.M9).

Operator-named (verbatim, 2026-05-17 mandate context): "the management
of the softwares ... observations and operations and configurations".

R240 ships services inventory (list/failures/timers/shipped). R262
ships schedule-manifest with linear drain order. R277 closes E2.M9:
service-dependency graph that introspects systemd's After=, Wants=,
Requires=, BindsTo= directives + computes the topological drain
order operators can paste into a schedule-manifest.

Probes (read-only):
  systemctl show <unit> -p After,Wants,Requires,BindsTo,WantedBy
  /etc/systemd/system/* + systemd/system/* in-repo unit files

Builds a DAG:
  nodes = systemd units we care about (operator-supplied list OR
          all sovereign-* units OR specific filter)
  edges = After (B starts after A → A must drain BEFORE B during
          shutdown) + Requires/BindsTo (hard dep — A must stop B)

Output:
  graph_json        full {nodes, edges} for graphviz consumption
  drain_order       topo-sorted leaves-first list (what to stop first)
  cycles            any dependency cycle the kernel allows but
                    schedule-manifest cannot honor

CLI:
  dependency-graph.py graph [--unit U1,U2,...] [--prefix sovereign-] [--json]
      build + emit the DAG
  dependency-graph.py drain [--unit ...] [--prefix ...] [--json]
      topo-sorted drain list (leaves first)
  dependency-graph.py dot [--unit ...] [--prefix ...]
      graphviz .dot syntax for visual rendering

Exit codes:
  0  graph built / drain order computed
  1  ≥1 cycle detected
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def list_repo_units(prefix: str = "sovereign-") -> list[str]:
    """Enumerate systemd unit files this repo ships, filtered by prefix."""
    unit_dir = REPO_ROOT / "systemd" / "system"
    out: list[str] = []
    if not unit_dir.is_dir():
        return out
    for p in sorted(unit_dir.iterdir()):
        if p.suffix in {".service", ".timer", ".socket", ".target"}:
            if not prefix or p.name.startswith(prefix):
                out.append(p.name)
    return out


def systemctl_show_dependencies(unit: str) -> dict[str, list[str]]:
    """systemctl show <unit> -p After,Before,Wants,Requires,BindsTo,WantedBy
    -p formats each property as KEY=v1 v2 ... (space-separated)."""
    deps = {"After": [], "Before": [], "Wants": [], "Requires": [],
            "BindsTo": [], "WantedBy": []}
    if not shutil.which("systemctl"):
        return deps
    props = ",".join(deps.keys())
    try:
        r = subprocess.run(
            ["systemctl", "show", unit, "-p", props, "--no-pager"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return deps
    if r.returncode != 0:
        return deps
    for line in r.stdout.splitlines():
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k in deps:
            deps[k] = v.split() if v.strip() else []
    return deps


def parse_unit_file_dependencies(unit_path: Path) -> dict[str, list[str]]:
    """Parse a systemd unit file directly (for hosts without
    systemctl access)."""
    deps = {"After": [], "Before": [], "Wants": [], "Requires": [],
            "BindsTo": [], "WantedBy": []}
    if not unit_path.exists():
        return deps
    try:
        for line in unit_path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for k in deps:
                if line.startswith(f"{k}="):
                    deps[k].extend(line.split("=", 1)[1].split())
    except OSError:
        pass
    return deps


def build_graph(units: list[str]) -> dict[str, Any]:
    """Build a DAG. Returns {nodes, edges, edge_count, node_count}.

    Edges semantics:
      edge (a → b) means "during DRAIN, b should be stopped BEFORE a"
      (i.e. b depends on a being available; stop b first, then a).

    Systemd's `After=A` on unit B → B starts AFTER A → during stop
    we reverse: B stops BEFORE A → edge A → B (a points at dependent).
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    # Prefer systemctl show when available, fall back to file parse.
    systemctl_ok = shutil.which("systemctl") is not None
    for u in units:
        if systemctl_ok:
            d = systemctl_show_dependencies(u)
        else:
            d = parse_unit_file_dependencies(
                REPO_ROOT / "systemd" / "system" / u
            )
        nodes.append({"unit": u, "deps": d})
        for after_unit in d["After"]:
            # B (= u) after A (= after_unit) → edge a → b
            edges.append({"from": after_unit, "to": u, "kind": "after"})
        for req in d["Requires"]:
            edges.append({"from": req, "to": u, "kind": "requires"})
        for bind in d["BindsTo"]:
            edges.append({"from": bind, "to": u, "kind": "binds-to"})
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def topo_sort_drain(graph: dict[str, Any]) -> dict[str, Any]:
    """Kahn's algorithm — returns drain order (leaves-first).

    "Leaves" = nodes with no incoming edges in the dep-target sense
    (nothing depends on them, so they stop first). Cycles are reported
    explicitly.
    """
    nodes = [n["unit"] for n in graph["nodes"]]
    # Adjacency: edge from → to. For drain, we want to stop "to" before
    # "from" (because "to" depends on "from"). So in topo sense, nodes
    # with no outgoing-edges-INTO-them stop first.
    incoming: dict[str, set[str]] = {u: set() for u in nodes}
    outgoing: dict[str, set[str]] = {u: set() for u in nodes}
    for e in graph["edges"]:
        f, t = e["from"], e["to"]
        if f not in incoming:
            incoming[f] = set()
            outgoing[f] = set()
        if t not in incoming:
            incoming[t] = set()
            outgoing[t] = set()
        incoming[t].add(f)
        outgoing[f].add(t)
    # Drain order: nodes with no OUTGOING-to-tracked-deps (nothing depending on them) first.
    drain_order: list[str] = []
    no_dependents = sorted(u for u in nodes if not outgoing.get(u))
    while no_dependents:
        n = no_dependents.pop(0)
        drain_order.append(n)
        # Strip edges into n (we already "drained" n; release its preds).
        for pred in list(incoming.get(n, [])):
            outgoing[pred].discard(n)
            if not outgoing[pred]:
                if pred in nodes and pred not in drain_order and pred not in no_dependents:
                    no_dependents.append(pred)
        no_dependents.sort()
    # Any node not in drain_order = part of a cycle.
    cycle_nodes = sorted(u for u in nodes if u not in drain_order)
    return {
        "drain_order": drain_order,
        "cycle_nodes": cycle_nodes,
        "cycle_present": bool(cycle_nodes),
    }


# --------------------------------------------------------------- verbs


def cmd_graph(args: argparse.Namespace) -> int:
    units = resolve_units(args)
    g = build_graph(units)
    out = {
        "round": "R277",
        "vector": "E2.M9 (service-dep-graph)",
        "systemctl_available": shutil.which("systemctl") is not None,
        "units": units,
        **g,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R277 sovereign-os service-dependency-graph graph (E2.M9) ──")
    print(f"  units: {len(units)}  edges: {g['edge_count']}")
    for n in g["nodes"]:
        d = n["deps"]
        non_empty = [(k, vs) for k, vs in d.items() if vs]
        if non_empty:
            print(f"\n  {n['unit']}")
            for k, vs in non_empty:
                print(f"    {k}: {', '.join(vs[:4])}{' ...' if len(vs) > 4 else ''}")
    return 0


def cmd_drain(args: argparse.Namespace) -> int:
    units = resolve_units(args)
    g = build_graph(units)
    topo = topo_sort_drain(g)
    out = {
        "round": "R277",
        "vector": "E2.M9 (drain-order)",
        "input_unit_count": len(units),
        "drain_order_count": len(topo["drain_order"]),
        "cycle_present": topo["cycle_present"],
        "cycle_nodes": topo["cycle_nodes"],
        "drain_order": topo["drain_order"],
    }
    rc = 1 if topo["cycle_present"] else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R277 service-dependency-graph drain order (E2.M9) ──")
    print(f"  input units:        {len(units)}")
    print(f"  drain order length: {len(topo['drain_order'])}")
    print(f"  cycle present:      {topo['cycle_present']}")
    print()
    print("  STOP-FIRST →")
    for i, u in enumerate(topo["drain_order"]):
        print(f"    {i+1:>3}. {u}")
    if topo["cycle_nodes"]:
        print()
        print(f"  cycle members (not in drain order):")
        for u in topo["cycle_nodes"]:
            print(f"    ⚠ {u}")
    return rc


def cmd_dot(args: argparse.Namespace) -> int:
    units = resolve_units(args)
    g = build_graph(units)
    lines = ["digraph sovereign_services {"]
    lines.append("  rankdir=BT;  // bottom-up: stop-first at bottom")
    lines.append("  node [shape=box, fontname=\"Courier\"];")
    for n in g["nodes"]:
        lines.append(f'  "{n["unit"]}";')
    for e in g["edges"]:
        style = {
            "requires": "style=bold,color=red",
            "binds-to": "style=bold,color=orange",
            "after":    "style=dashed,color=blue",
        }.get(e.get("kind"), "")
        lines.append(f'  "{e["from"]}" -> "{e["to"]}" [{style}];')
    lines.append("}")
    print("\n".join(lines))
    return 0


def resolve_units(args: argparse.Namespace) -> list[str]:
    if args.unit:
        return [u.strip() for u in args.unit.split(",") if u.strip()]
    return list_repo_units(prefix=args.prefix or "sovereign-")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dependency-graph.py",
        description="R277 (E2.M9) — service-dependency graph + drain order.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("graph", cmd_graph, "build + emit the DAG"),
        ("drain", cmd_drain, "topo-sorted drain order (leaves-first)"),
        ("dot", cmd_dot, "graphviz .dot syntax"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--unit", help="comma-separated unit list (overrides --prefix)")
        sp.add_argument("--prefix", default="sovereign-",
                        help="filter repo units by prefix (default 'sovereign-')")
        if name != "dot":
            sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
