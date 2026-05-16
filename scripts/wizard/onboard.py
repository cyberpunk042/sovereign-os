#!/usr/bin/env python3
"""sovereign-os mirror of selfdef SD-R11 wizard (R169).

Operator-facing first-time walkthrough on the sovereign-os side:
probes hardware, recommends a sovereign-os PROFILE (sain-01 /
old-workstation / minimal / developer / headless), shows the
operator exactly what to run, cites the cross-repo bridge from
selfdef so the two CLIs deliver consistent guidance.

Pure-read: NEVER writes config. Operator authority always wins.

CLI:
  onboard.py                 — interactive-feel walkthrough
  onboard.py --json          — machine-readable recommendation
  onboard.py --verdict-only  — just the recommended profile name

Exit codes:
  0  successful walkthrough (regardless of verdict)
  2  hardware probe failed catastrophically
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Import the existing Sain01Match logic from sain01-match.py (R166).
# We do this via subprocess so this script stays a single-file CLI;
# the JSON output of `sain01-match.py --json` carries everything.

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def probe_hardware() -> dict:
    """Invoke the R166 sain01-match.py script and parse its JSON.
    Returns {} on failure (operator gets a graceful walkthrough on
    minimal hosts without /proc/cpuinfo etc.)."""
    match_script = REPO_ROOT / "scripts/hardware/sain01-match.py"
    if not match_script.exists():
        sys.stderr.write(
            f"WARN  R169 wizard: {match_script} missing — running degraded\n"
        )
        return {}
    try:
        r = subprocess.run(
            ["python3", str(match_script), "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(f"WARN  R169 wizard: probe failed: {e}\n")
        return {}
    if not r.stdout:
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


def recommend_profile(probe: dict) -> dict:
    """Profile recommendation:
      sain-01         FullMatch (or VNNI + 256GB + 2 GPUs)
      headless        AVX-512 but no GPUs (server-class)
      developer       AVX2 host with at least one GPU
      old-workstation legacy AMD/Intel with no AVX-512
      minimal         everything else (VM, CI runner)
    """
    snap = probe.get("snapshot", {}) if probe else {}
    m = probe.get("sain01_match", {}) if probe else {}
    cpu = snap.get("cpu", {})
    mem = snap.get("memory", {})
    gpus = snap.get("gpus", {})

    avx512_vnni = cpu.get("avx512_vnni", False)
    avx512_present = cpu.get("avx512_present", False)
    avx2 = "avx2" in (cpu.get("features", []) or [])
    mem_256 = mem.get("total_bytes", 0) >= 256 * 1024**3
    gpu_count = gpus.get("count", 0)
    verdict = m.get("overall", "NoMatch")

    if verdict == "FullMatch" or (avx512_vnni and mem_256 and gpu_count >= 2):
        profile = "sain-01"
        rationale = (
            "AVX-512 VNNI + ≥256 GiB + 2 GPUs → master spec § 17 Trinity tier "
            "can run at full speed; sain-01 profile gives every bell + whistle."
        )
    elif avx512_present and gpu_count == 0:
        profile = "headless"
        rationale = (
            "AVX-512 available but no GPUs detected → headless server profile: "
            "auditd + fail2ban + chrony + sshd hardening, no GUI, no VFIO."
        )
    elif avx2 and gpu_count >= 1:
        profile = "developer"
        rationale = (
            "AVX2 + at least one GPU → developer profile: polyglot toolchain + "
            "GPU available for ad-hoc inference experiments."
        )
    elif avx2:
        profile = "old-workstation"
        rationale = (
            "AVX2 baseline, no GPU → old-workstation profile: BitNet on CPU "
            "via substrate-default kernel; no custom Zen 5 build."
        )
    else:
        profile = "minimal"
        rationale = (
            "Legacy / VM / CI runner — minimal profile: VM-baseline + ext4 "
            "+ DHCP networking + no GUI."
        )

    # Cross-repo bridge: when selfdef daemon is wiring out the
    # capabilities JSON, sovereign-os Wasm-AOT picks it up.
    selfdef_caps_path = Path("/var/lib/selfdef/hardware-capabilities.json")
    selfdef_caps_present = selfdef_caps_path.exists()

    next_steps = []
    if profile == "sain-01":
        next_steps.extend(
            [
                "sovereign-osctl trinity profile switch ultra-sovereign-efficiency",
                "sovereign-osctl bootstrap verify --strict",
                "sovereign-osctl bootstrap phases  # confirm Phase I-V artifacts",
                "sovereign-osctl bootstrap hardware-match  # sanity-check verdict",
            ]
        )
    elif profile == "headless":
        next_steps.append("sovereign-osctl install --profile headless")
    elif profile == "developer":
        next_steps.append("sovereign-osctl install --profile developer")
    elif profile == "old-workstation":
        next_steps.append("sovereign-osctl install --profile old-workstation")
    else:
        next_steps.append("sovereign-osctl install --profile minimal")
    next_steps.append("sovereign-osctl overview  # consolidated cross-surface status")

    if not selfdef_caps_present:
        next_steps.insert(
            0,
            "# (optional) install selfdef and run `selfdefctl hardware export"
            " --output /var/lib/selfdef/hardware-capabilities.json` to enable"
            " adaptive AVX-512 flags in sovereign-os wasm-aot + build-bitnet",
        )

    # R186: per-profile selfdef-module recommendations. R188 factored
    # the matrix into scripts/hardware/lib/module-recommendations.py
    # (single source of truth) — closes SDD-019 T-5.
    has_vnni = bool(cpu.get("avx512_vnni", False))
    has_avx512 = bool(cpu.get("avx512_present", False)) or has_vnni
    # Import the shared helper lazily (the wizard runs as a script,
    # not a package; sys.path doesn't include `scripts/`).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "module_recommendations",
        str(REPO_ROOT / "scripts/hardware/lib/module-recommendations.py"),
    )
    _modrec = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_modrec)  # type: ignore[union-attr]
    try:
        selfdef_modules = _modrec.recommend_modules(
            profile, has_avx512=has_avx512, gpu_count=gpu_count
        )
    except ValueError:
        selfdef_modules = []
    if selfdef_modules:
        # Surface as copy-paste hints in next_steps. Use separate
        # list entries (no embedded \n) so JSON consumers can parse
        # without unescaping multi-line strings.
        next_steps.append("# (optional) add to /etc/selfdef/modules.toml:")
        for m in selfdef_modules:
            next_steps.append(f"#   [modules.{m}]")

    return {
        "recommended_profile": profile,
        "rationale": rationale,
        "selfdef_capabilities_present": selfdef_caps_present,
        "selfdef_module_recommendations": selfdef_modules,
        "next_steps": next_steps,
    }


def render_human(probe: dict, rec: dict) -> str:
    out = ["# sovereign-osctl wizard (R169) — first-time setup walkthrough", ""]
    out.append("## Step 1: Hardware probe")
    snap = probe.get("snapshot", {})
    cpu = snap.get("cpu", {})
    mem = snap.get("memory", {})
    gpus = snap.get("gpus", {})
    out.append(
        f"  CPU:          {cpu.get('model_name','(unknown)')} ({cpu.get('vendor','?')})"
    )
    out.append(f"  AVX-512 VNNI: {cpu.get('avx512_vnni', False)}")
    out.append(f"  AVX-512 BF16: {cpu.get('avx512_bf16', False)}")
    gib = mem.get("total_bytes", 0) / (1024**3)
    out.append(f"  Memory:       {gib:.1f} GiB")
    out.append(f"  GPUs:         {gpus.get('count', 0)} device(s)")
    m = probe.get("sain01_match", {})
    out.append(f"  Sain01Match:  {m.get('overall', 'NoMatch')}")
    out.append("")
    out.append("## Step 2: Recommendation")
    out.append(f"  → profile = {rec['recommended_profile']}")
    out.append(f"  rationale: {rec['rationale']}")
    out.append("")
    if rec["selfdef_capabilities_present"]:
        out.append("## Step 3: Cross-repo bridge — selfdef capabilities detected")
        out.append("  selfdef has already written")
        out.append("    /var/lib/selfdef/hardware-capabilities.json")
        out.append(
            "  sovereign-os scripts/pulse/wasm-aot.sh + build-bitnet.sh"
        )
        out.append(
            "  will read this file automatically and use this host's actual"
        )
        out.append("  AVX-512 feature set when compiling — no manual flag-pinning.")
    else:
        out.append("## Step 3: Cross-repo bridge — selfdef capabilities NOT detected")
        out.append("  Run `selfdefctl hardware export --output")
        out.append("    /var/lib/selfdef/hardware-capabilities.json`")
        out.append(
            "  to enable adaptive AVX-512 flag derivation in sovereign-os"
        )
        out.append("  wasm-aot + build-bitnet (R167 + R168).")
    out.append("")
    # R186: selfdef module recommendations inline.
    mods = rec.get("selfdef_module_recommendations") or []
    if mods:
        out.append("## Step 3.5: Recommended selfdef modules (R186)")
        out.append("  Based on your profile + probed hardware, these")
        out.append("  selfdef modules will land on this host:")
        for m in mods:
            out.append(f"    • {m}")
        out.append("  Copy this block into /etc/selfdef/modules.toml:")
        for m in mods:
            out.append(f"    [modules.{m}]")
        out.append("")
    out.append("## Step 4: Next steps")
    for s in rec["next_steps"]:
        out.append(f"  $ {s}")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="sovereign-osctl first-time wizard (R169)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--verdict-only", action="store_true", help="print recommended profile only"
    )
    args = parser.parse_args()

    probe = probe_hardware()
    rec = recommend_profile(probe)

    if args.verdict_only:
        print(rec["recommended_profile"])
    elif args.json:
        print(
            json.dumps(
                {"probe": probe, "recommendation": rec, "schema_version": "1.0.0",
                 "generated_at_unix": int(time.time())},
                indent=2,
            )
        )
    else:
        sys.stdout.write(render_human(probe, rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
