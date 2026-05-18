#!/usr/bin/env python3
"""scripts/trinity/trinity-inspect.py — R514 (E5++) JSON inspection
helper for the Genesis Trinity (master spec § 17).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Backs the `--json` mode of `sovereign-osctl trinity {status, pulse,
weaver, auditor}` so the MCP surface (R514) and any automation can
consume structured Trinity-tier state instead of pretty-printed text.

Read-only by design — Trinity inspection has no mutation verbs at any
surface (operator §17 sovereignty boundary; the pinned-process state
fabric is mutated by the runtime profile switcher, not by inspection).

Usage:
  trinity-inspect.py status
  trinity-inspect.py pulse
  trinity-inspect.py weaver
  trinity-inspect.py auditor
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

CPUINFO = Path("/proc/cpuinfo")

AVX512_FLAGS = (
    "avx512f", "avx512dq", "avx512bw", "avx512vl",
    "avx512bf16", "avx512fp16", "avx512_vnni",
)


def _cpuinfo_text() -> str:
    try:
        return CPUINFO.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _systemctl_active(unit: str) -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        cp = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return cp.returncode == 0


def _avx512_markers() -> dict[str, bool]:
    text = _cpuinfo_text()
    return {flag: (f" {flag} " in text or text.startswith(flag + " "))
            for flag in AVX512_FLAGS}


def pulse_payload() -> dict:
    markers = _avx512_markers()
    return {
        "tier": "pulse",
        "name": "Vector Core",
        "spec_ref": "master spec § 17 Module 1",
        "ccd": "CCD0 cores 0-5",
        "thread_mask": "0xfff",
        "avx512_markers": markers,
        "avx512_present": markers.get("avx512_vnni", False),
        "service": {
            "name": "sovereign-pulse",
            "active": _systemctl_active("sovereign-pulse"),
        },
        "backend_file": "scripts/inference/backends/bitnet.py",
        "start_script": "scripts/inference/start-pulse.sh",
    }


def weaver_payload() -> dict:
    return {
        "tier": "weaver",
        "name": "Sandboxed Fabric",
        "spec_ref": "master spec § 17 Module 2",
        "ccd": "CCD1 cores 0-9",
        "podman_available": shutil.which("podman") is not None,
        "vfio_modules_loaded": Path("/sys/module/vfio").exists(),
        "service": {
            "name": "sovereign-weaver",
            "active": _systemctl_active("sovereign-weaver"),
        },
    }


def auditor_payload() -> dict:
    return {
        "tier": "auditor",
        "name": "Immutable Gatekeeper",
        "spec_ref": "master spec § 17 Module 3",
        "always_on": True,
        "tetragon_available": shutil.which("tetra") is not None
            or Path("/usr/local/bin/tetragon").exists()
            or Path("/usr/bin/tetragon").exists(),
        "service": {
            "name": "sovereign-auditor",
            "active": _systemctl_active("sovereign-auditor"),
        },
    }


def status_payload() -> dict:
    return {
        "module": "trinity",
        "spec_ref": "master spec § 17",
        "tiers": {
            "pulse": pulse_payload(),
            "weaver": weaver_payload(),
            "auditor": auditor_payload(),
        },
        "standing_rule": "We do not minimize anything.",
    }


VERBS = {
    "status":  status_payload,
    "pulse":   pulse_payload,
    "weaver":  weaver_payload,
    "auditor": auditor_payload,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.stderr.write(
            "usage: trinity-inspect.py {status|pulse|weaver|auditor}\n"
        )
        return 0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2
    verb = argv[1]
    fn = VERBS.get(verb)
    if fn is None:
        sys.stderr.write(f"unknown verb: {verb!r}\n")
        sys.stderr.write(f"available: {sorted(VERBS)}\n")
        return 2
    print(json.dumps(fn(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
