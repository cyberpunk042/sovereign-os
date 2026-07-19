#!/usr/bin/env python3
"""scripts/inference/model-health.py — unified model-health core
(M060 D-03 / R10069-R10074).

The data model behind the D-03 model-health cockpit dashboard. Joins the
canonical model catalog (models/catalog.yaml) to the SRP hardware topology
(M075 Conductor/Logic/Oracle) and overlays whatever LIVE telemetry the
workstation exposes:

  - SRP topology (M075)      tier pulse→Conductor (CPU/CCD0 cores 0-5,
                             bitnet.cpp ternary), tier logic→Logic Engine
                             (RTX 5090 32GB internal secondary, Blackwell GB202
                             NVFP4-capable, PCIEX16_2 x8 — operator directive
                             2026-07-14 / D-022), tier oracle→Oracle Core (RTX
                             PRO 6000 Blackwell Max-Q 96GB, NVFP4-capable,
                             primary). The RTX 4090 24GB OcuLink eGPU is the
                             DSpark speculative-decode draft — host-resident by
                             default, opt-in VFIO — and is NOT one of the three
                             named SRP tiers (left unassigned by model-health).
  - GPU live (nvidia-smi)    per-GPU util / VRAM-used / temp / power /
                             compute-capability. Both internal cards are
                             Blackwell (GB202); the highest-VRAM Blackwell
                             (RTX PRO 6000) is the Oracle GPU, the next
                             (RTX 5090) is the Logic GPU (D-022).
  - Catalog (M073/M077/M080) per-role configured models + precision class
                             (ternary / nvfp4 / fp8 / fp16 / bf16 / hrm) +
                             declared VRAM footprint.
  - Runtime model-state      OPTIONAL /run/sovereign-os/model-state.json
                             published by the inference fabric (M058):
                             loaded models, tokens/sec, KV-cache occupancy.
  - Latency metrics          OPTIONAL /run/sovereign-os/model-latency.json:
                             per-model p50/p95/p99 + req/min + 24h heatmap.

Sovereignty: stdlib-only, zero added deps (the catalog YAML subset is parsed
by a purpose-built reader so the operator daemons stay dependency-free, like
every other scripts/operator/*-api.py). Every probe degrades gracefully — a
missing GPU / absent runtime-state file yields `null`/empty (rendered as `—`
or "no … activity" in the dashboard), NEVER a crash. This is the `core`
surface of the §1g 8-surface ladder for the model-health module;
`scripts/operator/model-health-api.py` serves it, `sovereign-osctl
model-health` drives it ad-hoc, the D-03 webapp renders it.

  model-health.py status   [--json]   full health snapshot (the dashboard model)
  model-health.py catalog  [--json]   parsed catalog rows joined to roles
  model-health.py gpus     [--json]   live nvidia-smi GPU table only
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

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = Path(
    os.environ.get("SOVEREIGN_OS_MODEL_CATALOG", str(_REPO_ROOT / "models" / "catalog.yaml"))
)
MODEL_STATE_PATH = Path(
    os.environ.get("SOVEREIGN_OS_MODEL_STATE", "/run/sovereign-os/model-state.json")
)
MODEL_LATENCY_PATH = Path(
    os.environ.get("SOVEREIGN_OS_MODEL_LATENCY", "/run/sovereign-os/model-latency.json")
)

# tier (catalog) → SRP role (M075). router-tier models (embed/reranker/draft)
# are co-resident helpers, surfaced under the role that hosts them; the
# dashboard's three role cards are conductor/logic/oracle.
TIER_TO_ROLE = {
    "pulse": "conductor",
    "logic": "logic",
    "oracle": "oracle",
    "router": "logic",  # RAG/draft helpers ride the Logic GPU by default
}

# Oracle = RTX PRO 6000 Blackwell Max-Q (96GB, primary); Logic = RTX 5090
# (32GB, internal secondary Blackwell GB202) per D-022 (operator 2026-07-14).
# Declared VRAM ceilings the dashboard gauges divide against (frontend
# hard-codes 32 / 96).
ROLE_VRAM_CEILING_GB = {"logic": 32.0, "oracle": 96.0}


def _run(cmd: list[str], timeout: float = 4.0) -> str | None:
    """Best-effort subprocess capture — None on any failure/absence."""
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


# ----------------------------------------------------------- catalog ------

def _scalar(v: str) -> Any:
    """Coerce a YAML scalar token to str/int/float, stripping quotes."""
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",")]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        if "." in v or "e" in low:
            return float(v)
        return int(v)
    except ValueError:
        return v


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    """Parse models/catalog.yaml's `catalog.models` list into dicts.

    Purpose-built reader for the catalog's regular structure (4-space list
    entries, 6-space scalar fields, `|` block scalars skipped). Keeps the
    operator daemons stdlib-only — no PyYAML dependency in the serving path.
    Absent/unreadable catalog → empty list (never raises)."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    models: list[dict[str, Any]] = []
    in_models = False
    cur: dict[str, Any] | None = None
    skip_block_indent: int | None = None
    for raw in lines:
        # End of an active `|` block scalar when we dedent back to/under the
        # key's indent (or hit a real key at the field indent).
        if skip_block_indent is not None:
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" "))
            if stripped and indent <= skip_block_indent:
                skip_block_indent = None
            else:
                continue
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body = raw.strip()
        if not in_models:
            if body == "models:" and indent == 2:
                in_models = True
            continue
        # A models-list entry begins at 4-space `- ` ; fields at 6 spaces.
        if indent < 4:
            # dedented out of the models list entirely
            break
        if body.startswith("- "):
            if cur:
                models.append(cur)
            cur = {}
            body = body[2:].strip()  # inline first field after the dash
        if cur is None:
            continue
        if ":" not in body:
            continue
        key, _, val = body.partition(":")
        key = key.strip()
        val = val.strip()
        # Strip inline `#` comments (YAML requires a leading space) unless the
        # value is a quoted string or inline list.
        if val[:1] not in ('"', "'", "[") and " #" in val:
            val = val.split(" #", 1)[0].strip()
        if val == "|" or val == ">":
            skip_block_indent = indent  # block scalar — skip its body lines
            continue
        if val == "":
            continue
        cur[key] = _scalar(val)
    if cur:
        models.append(cur)
    return models


def _precision(model: dict[str, Any]) -> str:
    """Map catalog quantization (+ class) to the dashboard precision token
    (ternary/nvfp4/fp8/fp16/bf16/hrm + honest pass-through for the rest)."""
    cls = str(model.get("class", "")).lower()
    if cls == "hrm" or "hrm" in str(model.get("id", "")).lower():
        return "hrm"
    q = str(model.get("quantization", "")).lower()
    if "ternary" in q or "1.58" in q:
        return "ternary"
    if "nvfp4" in q:
        return "nvfp4"
    if "fp8" in q:
        return "fp8"
    if "fp16" in q:
        return "fp16"
    if "bf16" in q:
        return "bf16"
    if q.startswith("gguf-"):
        return q[len("gguf-"):]  # e.g. q4_k_m
    return q or "—"


def _quant_suffix(quantization: Any) -> str:
    """The id suffix that encodes a quantization value in the catalog's
    quant-in-id convention (e.g. gguf-q4_k_m → Q4_K_M, fp16 → FP16, nvfp4 →
    NVFP4). Used to recover a model's base id by stripping its quant suffix."""
    q = str(quantization or "").lower()
    if not q:
        return ""
    if q.startswith("gguf-"):
        return q[len("gguf-"):].upper()      # gguf-q4_k_m → Q4_K_M
    return q.upper()                          # fp16 → FP16, nvfp4 → NVFP4, bf16 → BF16


def _base_id(model: dict[str, Any]) -> str:
    """A model's base id — its id with a trailing `-<QUANT>` suffix removed when
    that suffix matches the entry's own quantization. Quant variants of one model
    are separate catalog ids (…-FP16 / …-Q4_K_M, or per-quant HF repos like the
    Nemotron BF16/FP8/NVFP4 trio), so grouping by hf_repo_id is insufficient;
    stripping the entry's own quant suffix recovers the shared base. Models whose
    id carries no quant suffix (e.g. Ling-2.6-flash) are their own base."""
    mid = str(model.get("id", "") or "")
    suf = _quant_suffix(model.get("quantization"))
    if suf and mid.lower().endswith("-" + suf.lower()):
        return mid[: len(mid) - len(suf) - 1]
    return mid


def group_by_base(models: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Catalog models grouped by base model, each group carrying its available
    quantization variants — the shape a load-time quantization picker consumes.
    A group with one variant is a single-quant model; a group with several
    (DeepSeek-R1-Distill-Llama-70B → fp16 + gguf-q4_k_m; Nemotron-…-Reasoning →
    bf16 + fp8 + nvfp4) is where the operator gets a real quant choice. Order is
    catalog order (stable). Reuses load_catalog (no drift)."""
    if models is None:
        models = load_catalog()
    order: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for m in models:
        b = _base_id(m)
        if b not in groups:
            groups[b] = []
            order.append(b)
        groups[b].append(m)
    out: list[dict[str, Any]] = []
    for b in order:
        variants = groups[b]
        head = variants[0]
        out.append({
            "base": b,
            "tier": head.get("tier"),
            "class": head.get("class"),
            "engine": head.get("engine"),
            "hf_repo_id": head.get("hf_repo_id"),
            "variant_count": len(variants),
            "variants": [{
                "id": v.get("id"),
                "quantization": v.get("quantization"),
                "precision": _precision(v),
                "vram_gib_min": v.get("vram_gib_min"),
                "size_class": v.get("size_class"),
                "status": v.get("status"),
                "params_b": (round(v["parameters_millions"] / 1000, 1)
                             if isinstance(v.get("parameters_millions"), (int, float))
                             else None),
                "context_window_tokens": v.get("context_window_tokens"),
            } for v in variants],
        })
    return out


def _size_bytes(model: dict[str, Any]) -> int | None:
    """Declared on-GPU footprint from catalog vram_gib_min (GiB → bytes)."""
    v = model.get("vram_gib_min")
    if isinstance(v, (int, float)):
        return int(v * (1024 ** 3))
    return None


def catalog_by_role() -> dict[str, list[dict[str, Any]]]:
    """Catalog models grouped into the three SRP role buckets, each row
    reduced to the dashboard's per-role shape (id/precision/size_bytes)."""
    buckets: dict[str, list[dict[str, Any]]] = {"conductor": [], "logic": [], "oracle": []}
    for m in load_catalog():
        role = TIER_TO_ROLE.get(str(m.get("tier", "")).lower())
        if role not in buckets:
            continue
        buckets[role].append({
            "id": m.get("id", "?"),
            "precision": _precision(m),
            "size_bytes": _size_bytes(m),
            "class": m.get("class"),
            "status": m.get("status"),
            "context_window_tokens": m.get("context_window_tokens"),
        })
    return buckets


# --------------------------------------------------------------- GPU ------

def collect_gpus() -> list[dict[str, Any]]:
    """Per-GPU live telemetry via nvidia-smi CSV + Blackwell classification.
    Absent nvidia-smi → empty list (graceful)."""
    out = _run([
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,"
        "temperature.gpu,power.draw,compute_cap",
        "--format=csv,noheader,nounits",
    ])
    if out is None:
        return []

    def num(v: str) -> float | None:
        try:
            return float(v)
        except ValueError:
            return None

    gpus: list[dict[str, Any]] = []
    for line in out.strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < 8:
            continue
        mem_used, mem_total = num(cells[3]), num(cells[4])
        cc = num(cells[7])
        gpus.append({
            "index": cells[0],
            "name": cells[1],
            "util_pct": num(cells[2]),
            "vram_used_gb": round(mem_used / 1024, 1) if mem_used is not None else None,
            "vram_total_gb": round(mem_total / 1024, 1) if mem_total is not None else None,
            "temp_c": num(cells[5]),
            "power_w": num(cells[6]),
            "compute_cap": cc,
            "is_blackwell": cc is not None and cc >= 10.0,
        })
    return gpus


def _assign_gpu_roles(gpus: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """oracle ← highest-VRAM Blackwell (the RTX PRO 6000 96 GB primary) else
    highest-VRAM GPU; logic ← the next Blackwell (the RTX 5090 32 GB internal
    secondary) else the next-highest-VRAM non-oracle GPU. Per D-022 (operator
    2026-07-14) the Logic Engine runs on the internal RTX 5090; the RTX 4090
    OcuLink eGPU is the DSpark draft (not a named SRP tier), left unassigned
    when the 5090 is present. Mirrors start-oracle-core.sh's Blackwell-detection
    + start-logic-engine.sh (RTX 5090). Empty when no GPUs present."""
    role_gpu: dict[str, dict[str, Any]] = {}
    if not gpus:
        return role_gpu
    # Rank Blackwell cards by VRAM so the 96 GB PRO 6000 is the Oracle and the
    # 32 GB RTX 5090 is the Logic engine (D-022) — not merely list order.
    blackwell = sorted(
        (g for g in gpus if g.get("is_blackwell")),
        key=lambda g: (g.get("vram_total_gb") or 0),
        reverse=True,
    )
    if blackwell:
        role_gpu["oracle"] = blackwell[0]
        rest_bw = blackwell[1:]
        if rest_bw:
            role_gpu["logic"] = rest_bw[0]
        else:
            others = sorted(
                (g for g in gpus if g is not blackwell[0]),
                key=lambda g: (g.get("vram_total_gb") or 0),
                reverse=True,
            )
            if others:
                role_gpu["logic"] = others[0]
    else:
        # No Blackwell present: highest total-VRAM GPU is the Oracle stand-in.
        ranked = sorted(gpus, key=lambda g: (g.get("vram_total_gb") or 0), reverse=True)
        role_gpu["oracle"] = ranked[0]
        if ranked[1:]:
            role_gpu["logic"] = ranked[1]
    return role_gpu


# ----------------------------------------------- runtime overlay ----------

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def snapshot() -> dict[str, Any]:
    """The full D-03 dashboard data model. Catalog + live GPU are always
    real; loaded-models/latency/kvcache/heatmap come from the inference
    fabric's runtime files when present, else empty (honest idle state)."""
    cat = catalog_by_role()
    gpus = collect_gpus()
    role_gpu = _assign_gpu_roles(gpus)
    state = _read_json(MODEL_STATE_PATH) or {}
    lat = _read_json(MODEL_LATENCY_PATH) or {}

    loaded = state.get("loaded") or {}  # {role: [{id,precision,size_bytes}, ...]}
    tps = state.get("tokens_per_sec") or {}  # {role: float}

    roles: dict[str, Any] = {}
    for role in ("conductor", "logic", "oracle"):
        g = role_gpu.get(role, {})
        # Models shown per role: runtime-loaded set when published, else the
        # catalog-configured candidates for that role (transparent via source).
        runtime_models = loaded.get(role)
        if runtime_models is not None:
            models, source = runtime_models, "runtime"
        else:
            models, source = cat.get(role, []), "catalog"
        entry: dict[str, Any] = {
            "util_pct": g.get("util_pct"),
            "models": models,
            "model_source": source,
            "loaded_count": len(runtime_models) if runtime_models is not None else 0,
        }
        if role == "conductor":
            entry["tokens_per_sec"] = tps.get("conductor")
            entry["hardware"] = "Pulse Core CCD 0 (cores 0-5, bitnet.cpp ternary)"
        else:
            entry["vram_used_gb"] = g.get("vram_used_gb")
            entry["vram_total_gb"] = g.get("vram_total_gb") or ROLE_VRAM_CEILING_GB.get(role)
            entry["gpu_name"] = g.get("name")
            entry["temp_c"] = g.get("temp_c")
            entry["power_w"] = g.get("power_w")
        roles[role] = entry

    # Summary counts: runtime loaded totals when published, else catalog size.
    if loaded:
        total = sum(len(v) for v in loaded.values())
        bw = len(loaded.get("oracle", []))
        rtx = len(loaded.get("logic", []))
        cpu = len(loaded.get("conductor", []))
    else:
        total = sum(len(v) for v in cat.values())
        bw, rtx, cpu = len(cat["oracle"]), len(cat["logic"]), len(cat["conductor"])

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total": total, "blackwell": bw, "rtx4090": rtx, "cpu": cpu,
            "source": "runtime" if loaded else "catalog",
        },
        "roles": roles,
        "gpus": gpus,
        "models": lat.get("models", []),      # per-model p50/p95/p99 + req/min
        "kvcache": lat.get("kvcache", []),    # per-model KV cache occupancy
        "heatmap": lat.get("heatmap", []),    # 24h availability heatmap
    }


def _print(obj: Any, as_json: bool) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="unified model-health core (M060 D-03)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("status", "catalog", "gpus"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "status"
    as_json = getattr(args, "json", False)
    if cmd == "catalog":
        _print(catalog_by_role(), as_json)
    elif cmd == "gpus":
        _print(collect_gpus(), as_json)
    else:
        _print(snapshot(), as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
