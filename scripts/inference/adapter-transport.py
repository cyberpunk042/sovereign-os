#!/usr/bin/env python3
"""scripts/inference/adapter-transport.py — ship a promoted M046 LoRA adapter
from the training box (SAIN-01) to the serving box, on a ZFS-versioned layout
(SDD-716, Slice 2b of the personal-workstation LoRA plan; M046 E0444/E0446).

The M046 loop is: train on SAIN-01 (E0446 4090/Blackwell) → promote through the
foundry (adapter-decide.py, MS041 triple-gate, registry.json) → **transport the
weights here** → serve via `llama-server --lora` (SDD-715). This is the missing
"transport + versioning" link. Per E0446, ZFS owns "adapter versions + rollback".

Layout on the serving box:
  /var/lib/sovereign-os/adapters/<id>/<version>/   ← the GGUF adapter weights
  <dataset>@adapter-<id>-<version>                 ← a ZFS snapshot per version

This is a **planner**: it prints the exact `rsync` + `zfs` commands (DRY-RUN by
default; --apply runs them). Cross-box transport can't be CI-verified, so the
plan construction is what's tested; the operator (or a runtime job) applies it.

Sovereignty: stdlib-only; reuses adapter-foundry's registry helpers (never
invents an adapter); DRY-RUN default (no host mutation without --apply); absent
registry → still plans by id with an honest warning.

  adapter-transport.py plan <id> [--from SRC] [--version V] [--json]
  adapter-transport.py list [--json]
  adapter-transport.py rollback <id> <version> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Reuse the foundry's registry reader (single source of truth; keeps it pure).
_FOUNDRY = _REPO_ROOT / "scripts" / "inference" / "adapter-foundry.py"
_spec = importlib.util.spec_from_file_location("_foundry_for_transport", _FOUNDRY)
_foundry = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_foundry)  # type: ignore[union-attr]

ADAPTERS_DIR = Path(
    os.environ.get("SOVEREIGN_OS_ADAPTERS_DIR", "/var/lib/sovereign-os/adapters")
)
# The ZFS dataset backing ADAPTERS_DIR (operator-set; datasets are profile-declared
# in hardware.storage.datasets, so the exact name is host-specific).
ADAPTER_DATASET = os.environ.get(
    "SOVEREIGN_OS_ADAPTER_DATASET", "rpool/var/lib/sovereign-os/adapters"
)
# Where trained adapters come from — the SAIN-01 foundry (rsync/ssh source).
ADAPTER_SOURCE = os.environ.get(
    "SOVEREIGN_OS_ADAPTER_SOURCE", "sain-01:/var/lib/sovereign-os/adapters"
)


def _snapshot_name(adapter_id: str, version: str) -> str:
    return f"{ADAPTER_DATASET}@adapter-{adapter_id}-{version}"


def _resolve_version(adapter_id: str, explicit: str | None) -> str:
    """Version = explicit, else derived from the registry's promotion history
    length (v1, v2, …), else v1 when there's no registry."""
    if explicit:
        return explicit
    reg = _foundry._read_json(_foundry.ADAPTER_REGISTRY)
    entry = (reg.get("adapters") or {}).get(adapter_id) or {}
    history = entry.get("history") or []
    promotions = [h for h in history if h.get("action") == "promote"]
    return f"v{max(1, len(promotions))}"


def plan(adapter_id: str, source: str | None, version: str | None) -> dict[str, Any]:
    ver = _resolve_version(adapter_id, version)
    dest = ADAPTERS_DIR / adapter_id / ver
    src = f"{source or ADAPTER_SOURCE}/{adapter_id}/"
    snapshot = _snapshot_name(adapter_id, ver)
    reg = _foundry._read_json(_foundry.ADAPTER_REGISTRY)
    known = adapter_id in (reg.get("adapters") or {})
    return {
        "adapter_id": adapter_id,
        "version": ver,
        "registry_known": known,
        "warning": None if known else "adapter not in registry (planning by id anyway)",
        "steps": [
            {"kind": "rsync", "cmd": ["rsync", "-a", "--delete", src, f"{dest}/"]},
            {"kind": "zfs-snapshot", "cmd": ["zfs", "snapshot", snapshot]},
        ],
        "dest": str(dest),
        "snapshot": snapshot,
    }


def list_versions() -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    if ADAPTERS_DIR.is_dir():
        for adir in sorted(p for p in ADAPTERS_DIR.iterdir() if p.is_dir()):
            versions = sorted(v.name for v in adir.iterdir() if v.is_dir())
            if versions:
                out.append({"adapter_id": adir.name, "versions": versions})
    return {"adapters_dir": str(ADAPTERS_DIR), "adapters": out}


def rollback(adapter_id: str, version: str) -> dict[str, Any]:
    snapshot = _snapshot_name(adapter_id, version)
    return {
        "adapter_id": adapter_id,
        "version": version,
        "steps": [{"kind": "zfs-rollback", "cmd": ["zfs", "rollback", snapshot]}],
        "snapshot": snapshot,
    }


def _emit(obj: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
        return
    if "steps" in obj:
        if obj.get("warning"):
            print(f"WARNING: {obj['warning']}")
        print(f"# adapter {obj['adapter_id']} version {obj.get('version', '')}")
        for step in obj["steps"]:
            print(f"  {step['kind']}: {' '.join(step['cmd'])}")
    else:
        for a in obj.get("adapters", []):
            print(f"  {a['adapter_id']}: {', '.join(a['versions'])}")
        if not obj.get("adapters"):
            print(f"  (no adapters under {obj['adapters_dir']})")


def _run(steps: list[dict[str, Any]]) -> int:
    import subprocess

    for step in steps:
        print(f"+ {' '.join(step['cmd'])}")
        rc = subprocess.run(step["cmd"], check=False).returncode
        if rc != 0:
            print(f"step {step['kind']} failed (rc={rc}); stopping", file=sys.stderr)
            return rc
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="plan a transport (DRY-RUN unless --apply)")
    p_plan.add_argument("adapter_id")
    p_plan.add_argument("--from", dest="source", default=None)
    p_plan.add_argument("--version", default=None)
    p_plan.add_argument("--json", action="store_true")
    p_plan.add_argument("--apply", action="store_true", help="execute the plan")

    p_list = sub.add_parser("list", help="local adapter versions on the box")
    p_list.add_argument("--json", action="store_true")

    p_rb = sub.add_parser("rollback", help="plan a ZFS rollback of an adapter version")
    p_rb.add_argument("adapter_id")
    p_rb.add_argument("version")
    p_rb.add_argument("--json", action="store_true")
    p_rb.add_argument("--apply", action="store_true", help="execute the rollback")

    args = ap.parse_args(argv)

    if args.cmd == "plan":
        obj = plan(args.adapter_id, args.source, args.version)
        _emit(obj, args.json)
        return _run(obj["steps"]) if args.apply else 0
    if args.cmd == "list":
        _emit(list_versions(), args.json)
        return 0
    if args.cmd == "rollback":
        obj = rollback(args.adapter_id, args.version)
        _emit(obj, args.json)
        return _run(obj["steps"]) if args.apply else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
