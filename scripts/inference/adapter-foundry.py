#!/usr/bin/env python3
"""scripts/inference/adapter-foundry.py — LoRA adapter inventory + promotion
status core (M060 D-11 / R10109-R10111).

The data model behind the D-11 adapter-status cockpit dashboard. Joins two
real sources — never invents an adapter:

  - model catalog  models/catalog.yaml `class: lora-adapter` entries (M046
                   LoRA Foundry) — the CONFIGURED adapters + their base_model
                   + precision + declared footprint. Parsed through the SAME
                   model-health core the D-03 dashboard uses (no schema drift).
  - promotion      OPTIONAL /var/lib/sovereign-os/adapters/registry.json
    registry       published by the LoRA Foundry: per-adapter live status
                   (active/pending/quarantined/rolled-back), MS041 triple-gate
                   state (snapshot + test/eval + oracle-or-human, R09697-R09711),
                   eval gain %, NVFP4 recipe (M077), and the promotion/rollback
                   history. Absent → every catalog adapter is `pending` with
                   all gates `pending` + empty history (honest pre-promotion state).

Also reports HRM (M080) model-class install status — HRM does NOT use LoRA
(arXiv 2506.21734 R13374); the dashboard surfaces it read-only for contrast.

Sovereignty: stdlib-only (catalog parsed by the model-health reader, registry
is plain JSON). Absent catalog/registry → empty inventory (the dashboard shows
"no adapters"), NEVER a crash. This is the `core` surface of the §1g 8-surface
ladder for the adapter module; `scripts/operator/adapters-api.py` serves it,
`sovereign-osctl adapters` drives it, the D-11 webapp renders it.

  adapter-foundry.py inventory [--json]   full dashboard model
  adapter-foundry.py list      [--json]   adapter rows only
  adapter-foundry.py history   [--json]   promotion/rollback history only
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_REGISTRY = Path(os.environ.get(
    "SOVEREIGN_OS_ADAPTER_REGISTRY", "/var/lib/sovereign-os/adapters/registry.json",
))

# Import the model-health core (single source of truth for catalog parsing +
# precision mapping). Hyphenated filename → importlib.
_MH_CORE_PATH = _REPO_ROOT / "scripts" / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_modelhealth_for_adapters", _MH_CORE_PATH)
_mh = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mh)  # type: ignore[union-attr]

# The three HRM variants the dashboard's M080 table enumerates (registry keys).
HRM_VARIANTS = ("canonical_27m", "text_1b", "trm_7m")
_VALID_STATUS = frozenset({"active", "pending", "quarantined", "rolled-back"})
_VALID_GATE = frozenset({"passed", "pending", "failed"})


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _catalog_adapters() -> list[dict[str, Any]]:
    """The `class: lora-adapter` rows from the model catalog, projected onto
    the dashboard adapter shape. base_model is REQUIRED by the catalog schema."""
    out = []
    for m in _mh.load_catalog():
        if str(m.get("class", "")).lower() != "lora-adapter":
            continue
        vram = m.get("vram_gib_min")
        out.append({
            "id": m.get("id", "?"),
            "base_model": m.get("base_model", "?"),
            "precision": _mh._precision(m),
            "size_bytes": int(vram * (1024 ** 3)) if isinstance(vram, (int, float)) else None,
            "catalog_status": m.get("status"),
        })
    return out


def _default_gates() -> dict[str, str]:
    # MS041 R09697-R09711 triple-gate — all pending until the Foundry advances them.
    return {"snapshot": "pending", "test_eval": "pending",
            "oracle": "pending", "human": "pending", "oracle_or_human": "pending"}


def _merge_gates(reg_gates: dict[str, Any]) -> dict[str, str]:
    g = _default_gates()
    for k in ("snapshot", "test_eval", "oracle", "human"):
        v = reg_gates.get(k)
        if v in _VALID_GATE:
            g[k] = v
    # composite the dashboard's adapter table reads (snapshot+test passed)
    g["oracle_or_human"] = "passed" if (g["oracle"] == "passed" or g["human"] == "passed") else "pending"
    return g


def _enrich_nvfp4(row: dict[str, Any], r: dict[str, Any]) -> None:
    """Attach the M077 NVFP4 4-bit detail fields the D-11 NVFP4 table reads,
    when the adapter is NVFP4 precision (or the registry declares a recipe)."""
    if row.get("precision") == "nvfp4" or r.get("nvfp4_recipe"):
        row["nvfp4_recipe"] = r.get("nvfp4_recipe", "NvidiaCanonical")
        row["vram_4bit_bytes"] = r.get("vram_4bit_bytes", row.get("size_bytes"))
        row["vram_bf16_bytes"] = r.get("vram_bf16_bytes")
        row["base_portability"] = r.get("base_portability", "NVFP4/FP8/BF16 rescale")


def list_adapters(registry: Path = ADAPTER_REGISTRY) -> list[dict[str, Any]]:
    """Catalog adapters overlaid with the promotion registry's live state."""
    reg = _read_json(registry)
    reg_adapters = reg.get("adapters") or {}
    rows = []
    for a in _catalog_adapters():
        r = reg_adapters.get(a["id"], {}) if isinstance(reg_adapters, dict) else {}
        status = r.get("status") if r.get("status") in _VALID_STATUS else "pending"
        gates = _merge_gates(r.get("gates") or {})
        row = {
            **a,
            "training": r.get("training", "sft"),
            "status": status,
            "eval_gain_pct": r.get("eval_gain_pct"),
            "gates": gates,
        }
        _enrich_nvfp4(row, r)
        rows.append(row)
    # registry may also carry adapters not (yet) in the catalog — include them.
    if isinstance(reg_adapters, dict):
        known = {a["id"] for a in rows}
        for aid, r in reg_adapters.items():
            if aid in known or not isinstance(r, dict):
                continue
            row = {
                "id": aid, "base_model": r.get("base_model", "?"),
                "precision": r.get("precision"), "size_bytes": r.get("size_bytes"),
                "catalog_status": None, "training": r.get("training", "sft"),
                "status": r.get("status") if r.get("status") in _VALID_STATUS else "pending",
                "eval_gain_pct": r.get("eval_gain_pct"), "gates": _merge_gates(r.get("gates") or {}),
            }
            _enrich_nvfp4(row, r)
            rows.append(row)
    return rows


def _hrm_status(registry: Path = ADAPTER_REGISTRY) -> dict[str, Any]:
    reg = _read_json(registry).get("hrm") or {}
    return {v: {"installed": bool((reg.get(v) or {}).get("installed"))} for v in HRM_VARIANTS}


def inventory(registry: Path = ADAPTER_REGISTRY) -> dict[str, Any]:
    """The full D-11 dashboard model."""
    adapters = list_adapters(registry)
    reg = _read_json(registry)
    promoted = sum(1 for a in adapters if a["status"] == "active")
    pending = sum(1 for a in adapters if a["status"] == "pending")
    vram_loaded = sum(
        a["size_bytes"] for a in adapters
        if a["status"] == "active" and isinstance(a.get("size_bytes"), int)
    )
    history = reg.get("history") if isinstance(reg.get("history"), list) else []
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total": len(adapters),
            "promoted": promoted,
            "pending": pending,
            "vram_loaded_bytes": vram_loaded or None,
        },
        "adapters": adapters,
        "history": history,
        "hrm": _hrm_status(registry),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="LoRA adapter inventory core (M060 D-11)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("inventory", "list", "history"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "inventory"
    if cmd == "list":
        _print(list_adapters())
    elif cmd == "history":
        _print(inventory()["history"])
    else:
        _print(inventory())
    return 0


if __name__ == "__main__":
    sys.exit(main())
