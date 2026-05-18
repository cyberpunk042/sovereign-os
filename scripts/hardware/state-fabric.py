#!/usr/bin/env python3
"""scripts/hardware/state-fabric.py — R358 (E1.M42).

Operator-pull entry-point for the master spec §7 Vibe Managing State
Fabric — the deterministic file-state matrix on the high-safety ZFS
dataset (tank/context) that holds CLAUDE.md / SOUL.md / AGENTS.md /
IDENTITY.md with strict atomicity contracts.

§7.1 File-State Matrix (operator verbatim):

  /mnt/vault/context/
  ├── IDENTITY.md      # Immutable System Persona & Owner Constraints (Read-Only to Agents)
  ├── SOUL.md          # Core Behavioral Logic & Dynamic Long-Term Memory (Read-Write via Manager)
  ├── AGENTS.md        # Routing Table & Hardware Pinning Map for Sub-Agents (Read-Only to Sub-Agents)
  └── CLAUDE.md        # Active Session Context & Project State Constraints (Atomic Append-Only)

§7.2 ZFS Transactional Optimizations (operator verbatim):
  zfs set sync=always tank/context
  zfs set primarycache=all tank/context
  zfs set logbias=latency tank/context

Until R358, these properties were checked inline by `trinity weaver`
brief but no dedicated verb surfaced them as a discoverable contract
or rendered the bootstrap commands a fresh operator runs to materialize
the fabric.

CLI:
  state-fabric.py layout                [--config P] [--json|--human]
                                          render the §7.1 4-file matrix
                                          with operator-verbatim access
                                          control intent
  state-fabric.py verify                [--root R] [--config P] [--json|--human]
                                          probe live tank/context dataset:
                                          - dataset exists?
                                          - sync=always / primarycache=all /
                                            logbias=latency?
                                          - the 4 files exist?
                                          - per-file mode matches intent?
                                          NEVER raises; rc=1 on drift
  state-fabric.py scaffold              [--root R] [--config P] [--json|--human]
                                          emit operator-runnable shell
                                          commands to MATERIALIZE the
                                          fabric (chmod + zfs set + tee
                                          stubs). Never executes — prints.

Operator-overlay (R283/SDD-030): /etc/sovereign-os/state-fabric.toml
  - override file-state matrix (custom file additions)
  - override ZFS dataset name (multi-host topology)
  - override expected modes per file

Exit codes:
  0  layout rendered / verify clean
  1  verify drift (dataset absent OR property mismatch OR file missing OR mode wrong)
  2  usage error
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

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R358"
SDD_VECTOR = "E1.M42"


DEFAULT_DATASET = "tank/context"
DEFAULT_MOUNTPOINT = "/mnt/vault/context"


# ── §7.1 File-State Matrix (operator-verbatim intent per file) ────
#
# Each entry preserves the operator's exact descriptive intent from
# the master spec. Mode encodes the access-control semantic:
#   "0o400"  Read-Only (operator + RO-to-agents convention)
#   "0o644"  Read-Write (standard; Manager mutates SOUL.md)
#   "0o400"  AGENTS.md Read-Only to Sub-Agents
#   "0o644"  CLAUDE.md is Atomic Append-Only (mode is rw; atomicity is
#            in the writer not the bit)
#
# The operator-verbatim TEXT for each file's role is the load-bearing
# content — L3 asserts it appears unchanged.
DEFAULT_FILE_MATRIX: list[dict[str, Any]] = [
    {
        "filename": "IDENTITY.md",
        "role_verbatim": ("Immutable System Persona & Owner Constraints "
                           "(Read-Only to Agents)"),
        "intended_mode": "0o400",
        "intended_owner": "root",
        "intent_axis": "immutable-identity",
        "writer": "(none — immutable post-bootstrap)",
        "readers": "all agents (read-only)",
        "spec_ref": "master spec §7.1 verbatim",
    },
    {
        "filename": "SOUL.md",
        "role_verbatim": ("Core Behavioral Logic & Dynamic Long-Term "
                           "Memory (Read-Write via Manager)"),
        "intended_mode": "0o644",
        "intended_owner": "root",
        "intent_axis": "manager-mutable",
        "writer": "Manager process (atomic-state.py per §21)",
        "readers": "all agents (read-write via Manager)",
        "spec_ref": "master spec §7.1 verbatim",
    },
    {
        "filename": "AGENTS.md",
        "role_verbatim": ("Routing Table & Hardware Pinning Map for "
                           "Sub-Agents (Read-Only to Sub-Agents)"),
        "intended_mode": "0o400",
        "intended_owner": "root",
        "intent_axis": "routing-table-immutable",
        "writer": "(bootstrap only)",
        "readers": "sub-agents (read-only)",
        "spec_ref": "master spec §7.1 verbatim",
    },
    {
        "filename": "CLAUDE.md",
        "role_verbatim": ("Active Session Context & Project State "
                           "Constraints (Atomic Append-Only)"),
        "intended_mode": "0o644",
        "intended_owner": "root",
        "intent_axis": "atomic-append-only",
        "writer": "Weaver atomic writer (scripts/weaver/atomic-state.py)",
        "readers": "all agents (append-only via Weaver)",
        "spec_ref": "master spec §7.1 verbatim",
    },
]


# §7.2 ZFS Transactional Optimizations (operator-verbatim properties)
DEFAULT_ZFS_PROPERTIES: list[dict[str, str]] = [
    {
        "property": "sync",
        "value": "always",
        "rationale": ("Force synchronous writes to guarantee that an "
                       "agent's state change is physically committed to "
                       "the NVMe before the next agent reads the file."),
        "command": "zfs set sync=always tank/context",
        "spec_ref": "master spec §7.2 verbatim",
    },
    {
        "property": "primarycache",
        "value": "all",
        "rationale": ("Minimize caching overhead for these specific "
                       "text layouts."),
        "command": "zfs set primarycache=all tank/context",
        "spec_ref": "master spec §7.2 verbatim",
    },
    {
        "property": "logbias",
        "value": "latency",
        "rationale": ("Minimize caching overhead for these specific "
                       "text layouts (continued)."),
        "command": "zfs set logbias=latency tank/context",
        "spec_ref": "master spec §7.2 verbatim",
    },
]


# ── Probing ────────────────────────────────────────────────────────
def _zfs_get(dataset: str, prop: str) -> str | None:
    """zfs get -H -o value <prop> <dataset>. NEVER raises."""
    if not shutil.which("zfs"):
        return None
    try:
        cp = subprocess.run(
            ["zfs", "get", "-H", "-o", "value", prop, dataset],
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    val = cp.stdout.strip()
    return val if val else None


def _file_mode_octal(path: Path) -> str | None:
    """Return mode as 0o### string. NEVER raises."""
    try:
        st = path.stat()
    except OSError:
        return None
    return f"0o{(st.st_mode & 0o777):o}"


def derive_zfs_state(dataset: str) -> dict[str, Any]:
    """Probe the dataset + each §7.2 property."""
    dataset_exists = _zfs_get(dataset, "name") == dataset
    rows: list[dict[str, Any]] = []
    drift_count = 0
    for spec in DEFAULT_ZFS_PROPERTIES:
        actual = _zfs_get(dataset, spec["property"]) if dataset_exists else None
        drifted = (
            dataset_exists and actual is not None and actual != spec["value"]
        )
        if drifted:
            drift_count += 1
        rows.append({
            "property": spec["property"],
            "intended_value": spec["value"],
            "actual_value": actual,
            "drifted": drifted,
            "probed": dataset_exists and actual is not None,
            "remediation": spec["command"],
            "rationale": spec["rationale"],
        })
    return {
        "dataset": dataset,
        "dataset_exists": dataset_exists,
        "property_rows": rows,
        "drift_count": drift_count,
    }


def derive_file_state(mountpoint: str, files: list[dict]) -> dict[str, Any]:
    """Probe each §7.1 file's presence + mode."""
    mp = Path(mountpoint)
    rows: list[dict[str, Any]] = []
    drift_count = 0
    for spec in files:
        path = mp / spec["filename"]
        exists = path.is_file()
        actual_mode = _file_mode_octal(path) if exists else None
        intended_mode = spec.get("intended_mode")
        drifted = (
            exists and actual_mode is not None and actual_mode != intended_mode
        )
        if drifted or not exists:
            drift_count += 1
        rows.append({
            "filename": spec["filename"],
            "path": str(path),
            "exists": exists,
            "intended_mode": intended_mode,
            "actual_mode": actual_mode,
            "drifted": drifted,
            "role_verbatim": spec.get("role_verbatim"),
            "intent_axis": spec.get("intent_axis"),
            "remediation": (
                f"chmod {intended_mode[2:] if intended_mode else '?'} "
                f"{path}" if drifted else (
                    f"touch {path} && chmod "
                    f"{intended_mode[2:] if intended_mode else '?'} {path}"
                    if not exists else None
                )
            ),
        })
    return {
        "mountpoint": mountpoint,
        "file_rows": rows,
        "missing_count": sum(1 for r in rows if not r["exists"]),
        "mode_drift_count": sum(1 for r in rows if r["drifted"]),
        "total_drift": drift_count,
    }


# ── Loading ────────────────────────────────────────────────────────
def load_state(
    overlay_path: Path | None,
) -> tuple[list[dict], list[dict], str, str, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    files = list(DEFAULT_FILE_MATRIX)
    zfs_props = list(DEFAULT_ZFS_PROPERTIES)
    dataset = DEFAULT_DATASET
    mountpoint = DEFAULT_MOUNTPOINT
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "state-fabric",
            {"files": [], "zfs_properties": [],
             "dataset": dataset, "mountpoint": mountpoint},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("files"):
            files = list(loaded["files"])
        if loaded.get("zfs_properties"):
            zfs_props = list(loaded["zfs_properties"])
        if loaded.get("dataset"):
            dataset = loaded["dataset"]
        if loaded.get("mountpoint"):
            mountpoint = loaded["mountpoint"]
    return files, zfs_props, dataset, mountpoint, meta


# ── Renderers ──────────────────────────────────────────────────────
def render_layout_human(files: list[dict], zfs_props: list[dict],
                         dataset: str, mountpoint: str) -> str:
    lines = [f"── R358 state-fabric layout (master spec §7.1 + §7.2 verbatim) ──"]
    lines.append("")
    lines.append(f"  Dataset:    {dataset}")
    lines.append(f"  Mountpoint: {mountpoint}")
    lines.append("")
    lines.append("  §7.1 FILE-STATE MATRIX (operator-verbatim intent):")
    for f in files:
        lines.append(f"    {f.get('filename')}  ({f.get('intended_mode')})  "
                      f"axis={f.get('intent_axis')}")
        lines.append(f"      role:    {f.get('role_verbatim')}")
        lines.append(f"      writer:  {f.get('writer')}")
        lines.append(f"      readers: {f.get('readers')}")
    lines.append("")
    lines.append("  §7.2 ZFS TRANSACTIONAL OPTIMIZATIONS:")
    for p in zfs_props:
        lines.append(f"    {p.get('property')} = {p.get('value')}")
        lines.append(f"      $ {p.get('command')}")
    return "\n".join(lines) + "\n"


def render_verify_human(zfs_state: dict, file_state: dict) -> str:
    lines = [f"── R358 state-fabric verify (master spec §7.1+§7.2) ──"]
    lines.append(f"  Dataset: {zfs_state['dataset']} "
                  f"(exists: {zfs_state['dataset_exists']})")
    lines.append("")
    lines.append("  ZFS properties:")
    for r in zfs_state["property_rows"]:
        if r["probed"]:
            glyph = "✗" if r["drifted"] else "✓"
            lines.append(f"    {glyph} {r['property']} = {r['actual_value']} "
                          f"(intended {r['intended_value']})")
            if r["drifted"]:
                lines.append(f"        $ {r['remediation']}")
        else:
            lines.append(f"    · {r['property']}: un-probed "
                          f"(intended {r['intended_value']})")
    lines.append("")
    lines.append("  Files:")
    for r in file_state["file_rows"]:
        if not r["exists"]:
            lines.append(f"    ✗ {r['filename']}: missing")
            if r.get("remediation"):
                lines.append(f"        $ {r['remediation']}")
        elif r["drifted"]:
            lines.append(f"    ✗ {r['filename']}: mode {r['actual_mode']} "
                          f"(intended {r['intended_mode']})")
            lines.append(f"        $ {r['remediation']}")
        else:
            lines.append(f"    ✓ {r['filename']} ({r['actual_mode']})")
    return "\n".join(lines) + "\n"


def render_scaffold_human(files: list[dict], zfs_props: list[dict],
                           dataset: str, mountpoint: str) -> str:
    lines = [f"── R358 state-fabric scaffold (operator-runnable bootstrap) ──"]
    lines.append("")
    lines.append("  # 1) Create the dataset")
    lines.append(f"  zfs create {dataset}")
    lines.append(f"  zfs set mountpoint={mountpoint} {dataset}")
    lines.append("")
    lines.append("  # 2) Apply §7.2 transactional optimizations")
    for p in zfs_props:
        lines.append(f"  {p.get('command')}")
    lines.append("")
    lines.append("  # 3) Materialize the §7.1 4-file state fabric")
    for f in files:
        path = f"{mountpoint}/{f.get('filename')}"
        mode = (f.get("intended_mode") or "0o644")[2:]
        lines.append(f"  touch {path}")
        lines.append(f"  chmod {mode} {path}  # {f.get('intent_axis')}")
    lines.append("")
    lines.append("  # 4) Verify")
    lines.append(f"  sovereign-osctl state-fabric verify --json")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="state-fabric.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("layout", "verify", "scaffold"):
        sp = sub.add_parser(verb)
        if verb in ("verify", "scaffold"):
            sp.add_argument("--root", help="override mountpoint for tests")
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    files, zfs_props, dataset, mountpoint, meta = load_state(
        getattr(args, "config", None))
    if getattr(args, "root", None):
        mountpoint = args.root

    if args.cmd == "layout":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "dataset": dataset,
                "mountpoint": mountpoint,
                "files": files,
                "zfs_properties": zfs_props,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_layout_human(files, zfs_props, dataset, mountpoint),
                  end="")
        return 0

    if args.cmd == "verify":
        zfs_state = derive_zfs_state(dataset)
        file_state = derive_file_state(mountpoint, files)
        drift = zfs_state["drift_count"] + file_state["total_drift"]
        out = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "zfs": zfs_state,
            "files": file_state,
            "total_drift": drift,
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(render_verify_human(zfs_state, file_state), end="")
        return 1 if drift else 0

    if args.cmd == "scaffold":
        if args.fmt == "json":
            commands: list[str] = [
                f"zfs create {dataset}",
                f"zfs set mountpoint={mountpoint} {dataset}",
            ]
            commands.extend(p.get("command") for p in zfs_props)
            for f in files:
                path = f"{mountpoint}/{f.get('filename')}"
                mode = (f.get("intended_mode") or "0o644")[2:]
                commands.append(f"touch {path}")
                commands.append(f"chmod {mode} {path}")
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "dataset": dataset,
                "mountpoint": mountpoint,
                "command_count": len(commands),
                "commands": commands,
                "note": ("operator-runnable bootstrap — this verb does NOT "
                          "execute; copy/paste under SOVEREIGN_OS_CONFIRM_DESTROY=YES "
                          "guard"),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_scaffold_human(files, zfs_props, dataset, mountpoint),
                  end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
