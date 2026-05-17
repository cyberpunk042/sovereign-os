#!/usr/bin/env python3
"""sovereign-os mirror of selfdef SD-R14/R15/R25/R26 module hardware gate (R170+R177).

selfdef SD-R14 adds `[requires_hardware]` to every selfdef module.toml;
SD-R15 ships `selfdefctl modules check-hardware` so operators can dry-run
the gate. This sovereign-os mirror lets operators answer the SAME
question — "which selfdef modules will actually apply on THIS host?" —
without needing selfdefctl installed. We read:

  1. /var/lib/selfdef/hardware-capabilities.json (selfdef SD-R10 export)
     OR run sain01-match.py + derive caps in-Python as fallback.
  2. The selfdef modules directory (default /usr/share/selfdef/modules,
     overrideable with --modules-dir or $SELFDEF_MODULES_DIR).
  3. The host's /etc/selfdef/modules.toml (or --host-config) to know
     WHICH modules are active.

For each active module, we evaluate the SAME predicates the Rust
implementation does in crates/selfdef-cli/src/modules.rs:

  - avx512_vnni                  bool   host must report cpu.avx512vnni
  - avx512_bf16                  bool   host must report cpu.avx512bf16
  - memory_gib_min               u64    host memory >= this many GiB
  - gpu_count_min                u32    host GPU count >= this
  - gpu_vram_gib_min             u64    SD-R26: at least one GPU vram >= this
  - gpu_vram_gib_each_min        u64    SD-R51: ALL GPUs must report vram >= this
  - gpu_power_headroom_watts_min u32    SD-R26: sum(limit-draw) >= this
  - wasm_aot_features_required   string SD-R32: every +feature in CSV
                                              must land in
                                              caps.wasm_aot.target_features
  - sain01_verdict_min           string host Sain01Match.overall >= rank

CLI:
  selfdef-modules-gate.py                # human-readable dry-run
  selfdef-modules-gate.py --json         # machine-readable
  selfdef-modules-gate.py --verdict-only # 0 (all apply) / 1 (some skip)

Exit codes:
  0   ran successfully (regardless of how many modules would skip)
  2   couldn't probe hardware AND couldn't read the capabilities JSON
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

VERDICT_RANK = {"FullMatch": 3, "PartialMatch": 2, "NoMatch": 1}


def load_capabilities(caps_path: Path) -> dict[str, Any] | None:
    """Read the selfdef SD-R10 capabilities JSON if present.

    Returns None when the file is missing or malformed — the caller
    falls back to sain01-match.py probe."""
    if not caps_path.exists():
        return None
    try:
        return json.loads(caps_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"WARN  R170: capabilities file unreadable: {e}\n")
        return None


def probe_caps_via_sain01_match() -> dict[str, Any] | None:
    """Fallback when /var/lib/selfdef/hardware-capabilities.json is
    absent: call sain01-match.py and synthesize the shape the gate
    expects. Returns None on probe failure."""
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
        "memory": {
            "total_bytes": int(mem.get("total_bytes", 0)),
        },
        "gpu": {
            "device_count": int(gpus.get("count", 0)),
        },
        "sain01_match": doc.get("sain01_match", {}) or {"overall": "NoMatch"},
    }


def parse_module_toml(path: Path) -> dict[str, Any]:
    """Read a single selfdef module.toml. We don't pull a TOML library
    dependency — we only care about `name` + the `[requires_hardware]`
    section. A 30-line ad-hoc parser is more than enough for this
    constrained shape; the authoritative parser is the Rust one."""
    text = path.read_text()
    out: dict[str, Any] = {"name": path.parent.name, "requires_hardware": {}}
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
        # Strip inline comments
        if "#" in v and not v.startswith('"'):
            v = v.split("#", 1)[0].strip()
        # Coerce
        if v.startswith('"') and v.endswith('"'):
            val: Any = v[1:-1]
        elif v in ("true", "false"):
            val = v == "true"
        else:
            try:
                val = int(v)
            except ValueError:
                continue
        if section == "requires_hardware":
            out["requires_hardware"][k] = val
        elif section is None and k == "name":
            out["name"] = val
    return out


def read_host_active_modules(host_config: Path) -> list[str]:
    """Parse /etc/selfdef/modules.toml-style `[modules.<slug>]` headers.
    Returns slugs in stable order (file order). When the file is
    missing, returns []."""
    if not host_config.exists():
        return []
    slugs: list[str] = []
    seen: set[str] = set()
    for raw in host_config.read_text().splitlines():
        line = raw.strip()
        if not line.startswith("[modules.") or not line.endswith("]"):
            continue
        key = line[len("[modules.") : -1]
        # Strip optional "#instance" suffix and quotes
        if key.startswith('"') and key.endswith('"'):
            key = key[1:-1]
        slug = key.split("#", 1)[0]
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)
    return slugs


def evaluate(req: dict[str, Any], caps: dict[str, Any]) -> list[str]:
    """Mirror of selfdef::modules::HardwareRequirements::evaluate.

    Returns a list of unmet predicate strings (operator-readable).
    Empty list = module passes the gate."""
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

    # R177 (mirror of selfdef SD-R26 cycle-2): per-GPU VRAM threshold. Passes
    # when ANY GPU in gpu.devices reports vram_bytes >= the bar.
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

    # R193 (mirror of selfdef SD-R51 cycle-2): ALL-semantics
    # per-GPU VRAM threshold. EVERY GPU must report vram_bytes ≥ bar.
    # Fail-closed on empty per-device list.
    each_min = int(req.get("gpu_vram_gib_each_min", 0) or 0)
    if each_min > 0:
        want_bytes = each_min * (1024**3)
        devices = gpu.get("devices", []) or []
        all_big_enough = bool(devices) and all(
            (d.get("vram_bytes") or 0) >= want_bytes for d in devices
        )
        if not all_big_enough:
            worst_gib = min(
                ((d.get("vram_bytes") or 0) // (1024**3) for d in devices),
                default=0,
            )
            unmet.append(
                f"gpu_vram_gib_each_min = {each_min}"
                f" (host worst is {worst_gib} GiB across {len(devices)} GPU(s))"
            )

    # SD-R26 mirror: aggregate power-headroom across all GPUs.
    headroom_min = int(req.get("gpu_power_headroom_watts_min", 0) or 0)
    if headroom_min > 0:
        devices = gpu.get("devices", []) or []
        total_headroom = 0
        telemetry_complete = bool(devices)
        for d in devices:
            lim = d.get("power_limit_watts")
            drw = d.get("power_draw_watts")
            if lim is None or drw is None:
                telemetry_complete = False
            else:
                total_headroom += max(0, int(lim) - int(drw))
        if not telemetry_complete:
            unmet.append(
                f"gpu_power_headroom_watts_min = {headroom_min}"
                " (host GPU(s) lack power telemetry — install nvidia-smi + NVML)"
            )
        elif total_headroom < headroom_min:
            unmet.append(
                f"gpu_power_headroom_watts_min = {headroom_min}"
                f" (host headroom is {total_headroom} W)"
            )

    # R181 (mirror of selfdef SD-R32 cycle-2): wasm-AOT feature
    # requirement. Both sides use comma-separated `+feature` syntax
    # (LLVM/wasmtime convention). Tolerates whitespace.
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
        rank = VERDICT_RANK
        if rank.get(actual, 0) < rank.get(verdict_min, 0):
            unmet.append(
                f"sain01_verdict_min = {verdict_min} (host verdict = {actual})"
            )

    # R209 (mirror of selfdef SD-R64 cycle-3): ternary AOT readiness +
    # ZMM INT8 lane width predicates. The capabilities JSON carries the
    # derived rollup fields on the cpu block (#[serde(default)] on the
    # selfdef side keeps pre-SD-R64 dumps deserialising to false/0,
    # which is the safe gate default).
    if req.get("ternary_aot_capable_required") and not cpu.get(
        "ternary_aot_capable", False
    ):
        unmet.append(
            "ternary_aot_capable required (host lacks AVX-512 VNNI "
            "+ (BF16 or FP16) — bitnet.cpp ternary hot path unavailable "
            "per master spec § 16)"
        )
    lanes_min = int(req.get("zmm_int8_lanes_min", 0) or 0)
    if lanes_min > 0:
        host_lanes = int(cpu.get("zmm_int8_lane_capacity", 0) or 0)
        if host_lanes < lanes_min:
            unmet.append(
                f"zmm_int8_lanes_min = {lanes_min} (host max = {host_lanes})"
            )

    # R211 (mirror of selfdef SD-R68 cycle-3): generalized cpuinfo-flag
    # gate. Reads the host's SD-R68 cpu.extended_features long-tail
    # surface; comma-separated syntax, no `+` prefix (distinguishes
    # from wasm_aot_features_required which uses LLVM target-feature
    # convention).
    host_feats_req = (req.get("host_features_required", "") or "").strip()
    if host_feats_req:
        actual = set(cpu.get("extended_features", []) or [])
        missing = [
            f.strip()
            for f in host_feats_req.split(",")
            if f.strip() and f.strip() not in actual
        ]
        if missing:
            unmet.append(
                f"host_features_required = {host_feats_req!r}"
                f" (host missing: {','.join(missing)})"
            )

    return unmet


def is_empty_req(req: dict[str, Any]) -> bool:
    """No requirements declared (or every field is zero/false/empty)."""
    if not req:
        return True
    return not (
        req.get("avx512_vnni")
        or req.get("avx512_bf16")
        or int(req.get("memory_gib_min", 0) or 0) > 0
        or int(req.get("gpu_count_min", 0) or 0) > 0
        or int(req.get("gpu_vram_gib_min", 0) or 0) > 0
        or int(req.get("gpu_vram_gib_each_min", 0) or 0) > 0
        or int(req.get("gpu_power_headroom_watts_min", 0) or 0) > 0
        or (req.get("wasm_aot_features_required", "") or "").strip()
        or (req.get("sain01_verdict_min", "") or "")
        # R209 mirror of SD-R64.
        or bool(req.get("ternary_aot_capable_required"))
        or int(req.get("zmm_int8_lanes_min", 0) or 0) > 0
        # R211 mirror of SD-R68.
        or (req.get("host_features_required", "") or "").strip()
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "sovereign-os mirror of selfdef SD-R14 + SD-R15 module gate (R170). "
            "Reads selfdef capabilities JSON + module manifests + host config; "
            "reports which selfdef modules will apply vs skip on this host."
        )
    )
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
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--verdict-only",
        action="store_true",
        help="exit 0 when every active module would apply, 1 otherwise",
    )
    args = p.parse_args()

    caps = load_capabilities(args.caps_path)
    if caps is None:
        caps = probe_caps_via_sain01_match()
    if caps is None:
        sys.stderr.write(
            "ERROR  R170: no capabilities JSON and probe fallback failed\n"
        )
        return 2

    # Catalog: read every <slug>/module.toml under the modules dir.
    catalog: list[dict[str, Any]] = []
    if args.modules_dir.exists() and args.modules_dir.is_dir():
        for entry in sorted(args.modules_dir.iterdir()):
            mt = entry / "module.toml"
            if mt.exists():
                try:
                    catalog.append(parse_module_toml(mt))
                except OSError as e:
                    sys.stderr.write(f"WARN  R170: {mt}: {e}\n")
    # Active = intersection of catalog with host config; if host config
    # is missing, every catalog module is considered active for the
    # dry-run.
    host_slugs = read_host_active_modules(args.host_config)
    if host_slugs:
        host_set = set(host_slugs)
        active = [m for m in catalog if m["name"] in host_set]
    else:
        active = catalog

    kept: list[tuple[str, str]] = []
    skipped: list[tuple[str, list[str]]] = []
    for m in active:
        name = m["name"]
        req = m.get("requires_hardware", {}) or {}
        if is_empty_req(req):
            kept.append((name, "no [requires_hardware] block"))
            continue
        unmet = evaluate(req, caps)
        if not unmet:
            kept.append((name, "all hardware requirements met"))
        else:
            skipped.append((name, unmet))

    if args.verdict_only:
        # Print 'pass' / 'fail' for trivial shell consumption AND
        # exit-code-encode the answer.
        if skipped:
            print("fail")
            return 1
        print("pass")
        return 0

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "caps_source": (
                        "capabilities_json"
                        if args.caps_path.exists()
                        else "sain01_match_fallback"
                    ),
                    "total": len(active),
                    "kept": [{"module": n, "reason": r} for n, r in kept],
                    "skipped": [
                        {"module": n, "unmet": u} for n, u in skipped
                    ],
                },
                indent=2,
            )
        )
        return 0

    print("# R170: sovereign-os mirror of selfdef SD-R15 hardware-gate dry-run")
    print(
        f"# caps from: "
        f"{'capabilities JSON' if args.caps_path.exists() else 'sain01-match.py fallback'}"
    )
    print(f"# {len(active)} active selfdef module(s)")
    if kept:
        print()
        print(f"WOULD APPLY ({len(kept)}):")
        for n, r in kept:
            print(f"  ✓ {n}  ({r})")
    if skipped:
        print()
        print(f"WOULD SKIP ({len(skipped)}):")
        for n, reasons in skipped:
            print(f"  ✗ {n}")
            for u in reasons:
                print(f"      - {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
