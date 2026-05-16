#!/usr/bin/env python3
"""scripts/hardware/cycle2-status.py — comprehensive cycle-2
readiness report (R187).

ONE command, ALL cycle-2 surfaces. Aggregates:
  - selfdef SD-R10 capabilities export presence + freshness
  - selfdef SD-R14+R26+R32 module-gate verdict counts (via R170 mirror)
  - selfdef SD-R34 model-registry gate verdict counts (via R182 mirror)
  - selfdef SD-R30 wasm-AOT surface (target_cpu + features)
  - sovereign-os bitnet schedule.json presence (SD-R28 artifact)

Output: human-readable summary OR JSON (--json) for fleet dashboards.

Read-only. Never writes. Cycles through every existing mirror so the
single source of truth for each predicate stays the selfdef side.

Exit codes:
  0  ran successfully (verdicts may include skipped modules)
  2  couldn't read capabilities + no fallback probe
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
DEFAULT_MODULES_DIR = Path("/usr/share/selfdef/modules")
DEFAULT_HOST_CONFIG = Path("/etc/selfdef/modules.toml")
DEFAULT_MODELS_DIR = Path("/etc/selfdef/models")
DEFAULT_BITNET_SCHEDULE = Path("/etc/selfdef/bitnet/schedule.json")
DEFAULT_AUDIT_PATH = Path("/var/log/selfdef/modules-audit.jsonl")
DEFAULT_WASM_AOT_CACHE = Path("/var/lib/selfdef/wasm-aot")


def read_capabilities(caps_path: Path) -> dict[str, Any] | None:
    if not caps_path.exists():
        return None
    try:
        return json.loads(caps_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def run_modules_gate(
    caps_path: Path, modules_dir: Path, host_config: Path
) -> dict[str, Any] | None:
    script = REPO_ROOT / "scripts/hardware/selfdef-modules-gate.py"
    if not script.exists():
        return None
    args = [
        "python3",
        str(script),
        "--caps-path",
        str(caps_path),
        "--modules-dir",
        str(modules_dir),
        "--host-config",
        str(host_config),
        "--json",
    ]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def run_models_gate(
    caps_path: Path, models_dir: Path
) -> dict[str, Any] | None:
    script = REPO_ROOT / "scripts/models/selfdef-models.py"
    if not script.exists():
        return None
    args = [
        "python3",
        str(script),
        "check-hardware",
        "--caps-path",
        str(caps_path),
        "--dir",
        str(models_dir),
        "--json",
    ]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def read_audit_log_count(audit_path: Path) -> tuple[int, str | None]:
    """R191: read the SD-R47 OCSF audit trail (one JSONL line per
    --ignore-hardware invocation). Returns (line_count, last_timestamp)
    or (0, None) when the file doesn't exist (most operators won't
    have used --ignore-hardware)."""
    if not audit_path.exists():
        return 0, None
    try:
        lines = [
            l for l in audit_path.read_text().splitlines() if l.strip()
        ]
    except OSError:
        return 0, None
    last_ts: str | None = None
    for ln in reversed(lines):
        try:
            d = json.loads(ln)
            last_ts = d.get("timestamp")
            break
        except json.JSONDecodeError:
            continue
    return len(lines), last_ts


def summarize(
    caps: dict[str, Any] | None,
    mods: dict[str, Any] | None,
    models: dict[str, Any] | None,
    schedule_path: Path,
    audit_path: Path,
    wasm_aot_cache: Path,
) -> dict[str, Any]:
    cpu = (caps or {}).get("cpu", {}) or {}
    wa = (caps or {}).get("wasm_aot", {}) or {}
    gpu = (caps or {}).get("gpu", {}) or {}
    sain01 = (caps or {}).get("sain01_match", {}) or {}
    return {
        "schema_version": "1.0.0",
        "caps_present": caps is not None,
        "caps_path_probed_at": (caps or {}).get("probed_at"),
        "sain01_verdict": sain01.get("overall", "Unknown"),
        "cpu_model": cpu.get("model_name"),
        "cpu_avx512": {
            "vnni": cpu.get("avx512vnni", False),
            "bf16": cpu.get("avx512bf16", False),
            "fp16": cpu.get("avx512fp16", False),
        },
        "gpu_count": gpu.get("device_count", 0),
        "wasm_aot": {
            "target_cpu": wa.get("target_cpu", ""),
            "target_features": wa.get("target_features", ""),
        },
        "modules_gate": {
            "available": mods is not None,
            "total": (mods or {}).get("total", 0),
            "kept": len((mods or {}).get("kept", []) or []),
            "skipped": len((mods or {}).get("skipped", []) or []),
        },
        "models_gate": {
            "available": models is not None,
            "total": (models or {}).get("total", 0),
            "kept": len((models or {}).get("kept", []) or []),
            "skipped": len((models or {}).get("skipped", []) or []),
        },
        "bitnet_schedule_present": schedule_path.exists(),
        "override_audit": {
            "count": read_audit_log_count(audit_path)[0],
            "last_timestamp": read_audit_log_count(audit_path)[1],
            "path": str(audit_path),
        },
        # R192 (mirror of selfdef SD-R48): wasm-aot-cache provisioning state.
        "wasm_aot_cache": {
            "present": (wasm_aot_cache / "cwasm").is_dir(),
            "cwasm_count": _wasm_aot_cwasm_count(wasm_aot_cache),
            "path": str(wasm_aot_cache),
        },
    }


def _wasm_aot_cwasm_count(cache_dir: Path) -> int:
    """Count .cwasm files in the SD-R48 cache. Returns 0 when the
    cache hasn't been provisioned or is empty."""
    cwasm = cache_dir / "cwasm"
    if not cwasm.is_dir():
        return 0
    try:
        return sum(1 for p in cwasm.iterdir() if p.suffix == ".cwasm")
    except OSError:
        return 0


def render_human(summary: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# R187: sovereign-os cycle-2 readiness report")
    out.append("# (selfdef SD-R10..R42 + R170..R186 mirrors)")
    out.append("")
    if summary["caps_present"]:
        out.append(
            f"## Capabilities: ✓ probed_at={summary['caps_path_probed_at']}"
        )
    else:
        out.append(
            "## Capabilities: ✗ not found (run `selfdefctl hardware export"
            " --output /var/lib/selfdef/hardware-capabilities.json`)"
        )
    out.append(f"  CPU:          {summary['cpu_model'] or '(unknown)'}")
    avx = summary["cpu_avx512"]
    out.append(
        f"  AVX-512:      vnni={avx['vnni']} bf16={avx['bf16']} fp16={avx['fp16']}"
    )
    out.append(f"  GPUs:         {summary['gpu_count']}")
    out.append(f"  Sain01:       {summary['sain01_verdict']}")
    out.append("")
    wa = summary["wasm_aot"]
    if wa["target_features"]:
        out.append("## Wasm-AOT (SD-R30):")
        out.append(f"  target_cpu:      {wa['target_cpu']}")
        out.append(f"  target_features: {wa['target_features']}")
    else:
        out.append("## Wasm-AOT (SD-R30): ✗ no AVX-512 → no AOT hint")
    out.append("")
    mg = summary["modules_gate"]
    if mg["available"]:
        out.append(
            f"## Modules gate (SD-R14+R26+R32):"
            f" {mg['kept']}/{mg['total']} apply,"
            f" {mg['skipped']} skip"
        )
    else:
        out.append("## Modules gate: (selfdef-modules-gate.py unavailable)")
    mdg = summary["models_gate"]
    if mdg["available"]:
        out.append(
            f"## Models gate (SD-R34):"
            f" {mdg['kept']}/{mdg['total']} apply,"
            f" {mdg['skipped']} skip"
        )
    else:
        out.append("## Models gate: (selfdef-models.py unavailable)")
    out.append("")
    if summary["bitnet_schedule_present"]:
        out.append("## BitNet schedule (SD-R28): ✓ present")
    else:
        out.append("## BitNet schedule (SD-R28): ✗ absent (module not applied)")
    # R192: wasm-aot-cache (SD-R48) presence.
    wac = summary["wasm_aot_cache"]
    if wac["present"]:
        out.append(
            f"## Wasm-AOT cache (SD-R48): ✓ {wac['path']}"
            f" ({wac['cwasm_count']} cached artifact(s))"
        )
    else:
        out.append("## Wasm-AOT cache (SD-R48): ✗ absent (module not applied)")
    # R191: SD-R47 override audit trail surface.
    audit = summary["override_audit"]
    if audit["count"] > 0:
        out.append("")
        out.append(
            f"## Override audit (SD-R47): ⚠ {audit['count']} `--ignore-hardware`"
            " event(s) recorded"
        )
        if audit["last_timestamp"]:
            out.append(f"  last: {audit['last_timestamp']}")
        out.append(f"  path: {audit['path']}")
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="cycle-2 readiness report (R187)")
    p.add_argument(
        "--caps-path",
        type=Path,
        default=Path(os.environ.get("SELFDEF_CAPS_PATH", str(DEFAULT_CAPS_PATH))),
    )
    p.add_argument(
        "--modules-dir",
        type=Path,
        default=Path(os.environ.get("SELFDEF_MODULES_DIR", str(DEFAULT_MODULES_DIR))),
    )
    p.add_argument(
        "--host-config",
        type=Path,
        default=Path(os.environ.get("SELFDEF_HOST_CONFIG", str(DEFAULT_HOST_CONFIG))),
    )
    p.add_argument(
        "--models-dir",
        type=Path,
        default=Path(os.environ.get("SELFDEF_MODELS_DIR", str(DEFAULT_MODELS_DIR))),
    )
    p.add_argument(
        "--schedule-path",
        type=Path,
        default=Path(os.environ.get(
            "SELFDEF_BITNET_SCHEDULE_FILE", str(DEFAULT_BITNET_SCHEDULE)
        )),
    )
    p.add_argument(
        "--audit-path",
        type=Path,
        default=Path(os.environ.get(
            "SELFDEF_MODULES_AUDIT_PATH", str(DEFAULT_AUDIT_PATH)
        )),
    )
    p.add_argument(
        "--wasm-aot-cache",
        type=Path,
        default=Path(os.environ.get(
            "SELFDEF_WASM_AOT_CACHE_DIR", str(DEFAULT_WASM_AOT_CACHE)
        )),
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    caps = read_capabilities(args.caps_path)
    mods = run_modules_gate(args.caps_path, args.modules_dir, args.host_config)
    models = run_models_gate(args.caps_path, args.models_dir)
    summary = summarize(
        caps,
        mods,
        models,
        args.schedule_path,
        args.audit_path,
        args.wasm_aot_cache,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        sys.stdout.write(render_human(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
