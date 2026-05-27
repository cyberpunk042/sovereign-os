#!/usr/bin/env python3
"""sovereign-os mirror of selfdef SD-R34 model registry (R182).

selfdef SD-R34 adds `selfdefctl models {list,check-hardware}` —
operators declare every model they care about in a canonical
manifest, the SD-R14 + SD-R26 + SD-R32 predicate engine gates which
land. This sovereign-os mirror lets operators answer the same
question — "which models WILL apply on THIS host?" — from EITHER
CLI without needing selfdefctl installed.

Reads:
  1. /var/lib/selfdef/hardware-capabilities.json (selfdef SD-R10 export)
     OR runs sain01-match.py + synthesizes caps as fallback
  2. The model registry directory (default /etc/selfdef/models, or
     --dir / SELFDEF_MODELS_DIR override)

CLI:
  selfdef-models.py list                  # human catalog listing
  selfdef-models.py check-hardware        # human dry-run
  selfdef-models.py check-hardware --json # machine output

Exit codes:
  0  successful (regardless of how many models would skip)
  2  couldn't load capabilities

Cross-repo provenance: matches the selfdef SD-R34 manifest format
1:1 — same `[model]` + `[hardware]` blocks, same predicate names,
same evaluation logic. The two CLIs MUST agree on identical inputs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

DEFAULT_CAPS_PATH = Path("/var/lib/selfdef/hardware-capabilities.json")
DEFAULT_MODELS_DIR = Path("/etc/selfdef/models")
VERDICT_RANK = {"FullMatch": 3, "PartialMatch": 2, "NoMatch": 1}


def load_capabilities(caps_path: Path) -> dict[str, Any] | None:
    if not caps_path.exists():
        return None
    try:
        return json.loads(caps_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"WARN  R182: capabilities file unreadable: {e}\n")
        return None


def probe_caps_fallback() -> dict[str, Any] | None:
    """Fall back to sain01-match.py when caps file absent — same
    pattern as R170 (selfdef-modules-gate.py)."""
    sain01 = REPO_ROOT / "scripts/hardware/sain01-match.py"
    if not sain01.exists():
        return None
    try:
        r = subprocess.run(
            ["python3", str(sain01), "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if not r.stdout:
        return None
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    snap = doc.get("snapshot", {}) or {}
    cpu = snap.get("cpu", {}) or {}
    mem = snap.get("memory", {}) or {}
    gpus = snap.get("gpus", {}) or {}
    return {
        "cpu": {
            "avx512vnni": bool(cpu.get("avx512_vnni", False)),
            "avx512bf16": bool(cpu.get("avx512_bf16", False)),
        },
        "memory": {"total_bytes": int(mem.get("total_bytes", 0))},
        "gpu": {"device_count": int(gpus.get("count", 0)), "devices": []},
        "sain01_match": doc.get("sain01_match", {}) or {"overall": "NoMatch"},
        "wasm_aot": {"target_features": ""},
    }


def parse_model_toml(path: Path) -> dict[str, Any]:
    """Minimal TOML parser for the SD-R34 model.toml shape. Same
    pattern as scripts/hardware/selfdef-modules-gate.py — we only
    care about [model] + [hardware] scalar fields; the authoritative
    parser is the Rust one."""
    text = path.read_text()
    out: dict[str, Any] = {"model": {}, "hardware": {}}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip(",")
        if "#" in v and not v.startswith('"'):
            v = v.split("#", 1)[0].strip()
        if v.startswith('"') and v.endswith('"'):
            val: Any = v[1:-1]
        elif v in ("true", "false"):
            val = v == "true"
        else:
            try:
                val = int(v)
            except ValueError:
                continue
        if section in ("model", "hardware"):
            out[section][k] = val
    return out


def evaluate(req: dict[str, Any], caps: dict[str, Any]) -> list[str]:
    """Mirror of selfdef::models::ModelHardwareRequirements::evaluate.
    Same predicate set as the cycle-1 + cycle-2 module gate."""
    unmet: list[str] = []
    cpu = caps.get("cpu", {}) or {}
    mem = caps.get("memory", {}) or {}
    gpu = caps.get("gpu", {}) or {}
    sain01 = caps.get("sain01_match", {}) or {}

    if req.get("avx512_vnni") and not cpu.get("avx512vnni", False):
        unmet.append("avx512_vnni required (host lacks AVX-512 VNNI)")
    if req.get("avx512_bf16") and not cpu.get("avx512bf16", False):
        unmet.append("avx512_bf16 required (host lacks AVX-512 BF16)")

    mem_min = int(req.get("memory_gib_min", 0) or 0)
    if mem_min > 0:
        host_gib = int(mem.get("total_bytes", 0)) // (1024**3)
        if host_gib < mem_min:
            unmet.append(f"memory_gib_min = {mem_min} (host has {host_gib} GiB)")

    gpu_min = int(req.get("gpu_count_min", 0) or 0)
    if gpu_min > 0:
        host_gpu = int(gpu.get("device_count", 0))
        if host_gpu < gpu_min:
            unmet.append(f"gpu_count_min = {gpu_min} (host has {host_gpu} GPU(s))")

    vram_min = int(req.get("gpu_vram_gib_min", 0) or 0)
    if vram_min > 0:
        want_bytes = vram_min * (1024**3)
        devices = gpu.get("devices", []) or []
        any_big_enough = any(
            (d.get("vram_bytes") or 0) >= want_bytes for d in devices
        )
        if not any_big_enough:
            best_gib = max(
                ((d.get("vram_bytes") or 0) // (1024**3) for d in devices),
                default=0,
            )
            unmet.append(
                f"gpu_vram_gib_min = {vram_min} (host best is {best_gib} GiB)"
            )

    wa_required = (req.get("wasm_aot_features_required", "") or "").strip()
    if wa_required:
        wa = caps.get("wasm_aot", {}) or {}
        actual_set = {
            f.strip()
            for f in (wa.get("target_features", "") or "").split(",")
            if f.strip()
        }
        missing = [
            f.strip()
            for f in wa_required.split(",")
            if f.strip() and f.strip() not in actual_set
        ]
        if missing:
            unmet.append(
                f"wasm_aot_features_required = {wa_required!r}"
                f" (host missing: {','.join(missing)})"
            )

    verdict_min = req.get("sain01_verdict_min", "") or ""
    if verdict_min:
        actual = sain01.get("overall", "NoMatch")
        if VERDICT_RANK.get(actual, 0) < VERDICT_RANK.get(verdict_min, 0):
            unmet.append(
                f"sain01_verdict_min = {verdict_min} (host verdict = {actual})"
            )
    return unmet


def humanize_bytes(b: int) -> str:
    if b <= 0:
        return "?"
    gib, mib, kib = 1024**3, 1024**2, 1024
    if b >= gib:
        return f"{b / gib:.1f} GiB"
    if b >= mib:
        return f"{b / mib:.1f} MiB"
    if b >= kib:
        return f"{b / kib:.1f} KiB"
    return f"{b} B"


def load_catalog(dir_: Path) -> list[tuple[str, dict[str, Any]]]:
    if not dir_.exists() or not dir_.is_dir():
        return []
    out = []
    for entry in sorted(dir_.iterdir()):
        mt = entry / "model.toml"
        if mt.exists():
            try:
                out.append((entry.name, parse_model_toml(mt)))
            except OSError as e:
                sys.stderr.write(f"WARN  R182: {mt}: {e}\n")
    return out


def cmd_list(catalog: list[tuple[str, dict[str, Any]]], dir_: Path) -> int:
    if not catalog:
        print(f"(no models registered in {dir_})")
        return 0
    print(f"{'name':<32}  {'format':<10}  {'size':<10}  summary")
    for slug, m in catalog:
        model = m.get("model", {}) or {}
        size = humanize_bytes(int(model.get("size_bytes", 0) or 0))
        fmt = model.get("weight_format", "") or "?"
        summary = model.get("summary", "")
        print(f"{slug:<32}  {fmt:<10}  {size:<10}  {summary}")
    return 0


def cmd_check_hardware(
    catalog: list[tuple[str, dict[str, Any]]],
    caps: dict[str, Any] | None,
    json_mode: bool,
) -> int:
    kept: list[tuple[str, int, str, str]] = []  # name, size_bytes, fmt, reason
    skipped: list[tuple[str, list[str], int, str]] = []
    probe_ok = caps is not None
    for slug, m in catalog:
        model = m.get("model", {}) or {}
        hw = m.get("hardware", {}) or {}
        size = int(model.get("size_bytes", 0) or 0)
        fmt = model.get("weight_format", "") or "?"
        if caps is None:
            skipped.append((slug, ["hardware probe unavailable"], size, fmt))
            continue
        unmet = evaluate(hw, caps)
        if not unmet:
            kept.append((slug, size, fmt, "all hardware requirements met"))
        else:
            skipped.append((slug, unmet, size, fmt))
    if json_mode:
        print(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "probe_ok": probe_ok,
                    "total": len(kept) + len(skipped),
                    "kept": [
                        {
                            "model": n,
                            "size_bytes": sz,
                            "weight_format": f,
                            "reason": r,
                        }
                        for (n, sz, f, r) in kept
                    ],
                    "skipped": [
                        {
                            "model": n,
                            "unmet": u,
                            "size_bytes": sz,
                            "weight_format": f,
                        }
                        for (n, u, sz, f) in skipped
                    ],
                },
                indent=2,
            )
        )
        return 0
    print("# R182: sovereign-os mirror of selfdef SD-R34 model-registry dry-run")
    if not probe_ok:
        print("# (hardware probe unavailable — gated models will be skipped)")
    print(f"# {len(kept) + len(skipped)} registered model(s)")
    if kept:
        print()
        print(f"WOULD APPLY ({len(kept)}):")
        for n, sz, f, r in kept:
            print(f"  ✓ {n} ({humanize_bytes(sz)}, {f}; {r})")
    if skipped:
        print()
        print(f"WOULD SKIP ({len(skipped)}):")
        for n, unmet, sz, f in skipped:
            print(f"  ✗ {n} ({humanize_bytes(sz)}, {f})")
            for u in unmet:
                print(f"      - {u}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="sovereign-os mirror of selfdef SD-R34 models registry (R182)"
    )
    p.add_argument(
        "command",
        choices=["list", "check-hardware"],
        help="Subcommand",
    )
    p.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("SELFDEF_MODELS_DIR", str(DEFAULT_MODELS_DIR))),
    )
    p.add_argument(
        "--caps-path",
        type=Path,
        default=Path(os.environ.get("SELFDEF_CAPS_PATH", str(DEFAULT_CAPS_PATH))),
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    catalog = load_catalog(args.dir)
    if args.command == "list":
        return cmd_list(catalog, args.dir)
    if args.command == "check-hardware":
        caps = load_capabilities(args.caps_path) or probe_caps_fallback()
        return cmd_check_hardware(catalog, caps, args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
