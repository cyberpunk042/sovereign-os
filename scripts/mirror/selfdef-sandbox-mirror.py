#!/usr/bin/env python3
"""scripts/mirror/selfdef-sandbox-mirror.py — READ-ONLY consumer of the selfdef
sandbox mirror (M060 D-15 / R10118-R10119).

The data model behind the D-15 sandboxes cockpit dashboard. CROSS-REPO MIRROR:
the authoritative sandbox-allocation state lives in selfdef (the IPS) — MS032
sandbox-tiers + MS036 tool-sandboxes (the 8-level isolation ladder from
host_seccomp → firecracker_microvm), exposed by the selfdef `/v1/sandbox-tiers`
surface and published through the MS007 typed-mirror crate
`selfdef-sandbox-mirror`. sovereign-os renders it READ-ONLY. sandbox
checkpoint/release are selfdefctl + MS003 verbs on the IPS side ONLY
(R10119 + MS043 R10212) — sovereign-os NEVER mutates IPS state.

Mirror artifact (selfdef-sandbox-mirror::SandboxMirrorSnapshot 1.0.0):
  schema_version · captured_at · summaries[{tier,running,pending,checkpointed,
  idle,released_24h,quarantined}] · allocations[{allocation_id,tier,ms032_tier,
  isolation,tool,capability_token_id,profile,actor,allocated_at,release_at,
  ttl_seconds,resident_mb,cpu_percent,state,trace_id}]

Sovereignty: stdlib-only. Absent artifact → 4 zeroed tier summaries + empty
allocations + mirror_status="offline" (graceful), NEVER a crash.

  selfdef-sandbox-mirror.py snapshot [--json]   full dashboard model
  selfdef-sandbox-mirror.py summaries [--json]   per-tier summary tiles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

SANDBOX_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_SANDBOX_MIRROR",
    "/run/sovereign-os/selfdef-mirror/sandboxes.json",
))

# MS032 4 sandbox tiers (A/B/C/D).
TIERS = ("tier-a", "tier-b", "tier-c", "tier-d")
# allocation lifecycle states.
_VALID_STATE = frozenset({"running", "pending", "checkpointed", "idle", "released"})
_SUMMARY_FIELDS = ("running", "pending", "checkpointed", "idle", "released_24h", "quarantined")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _summaries(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = {}
    for s in (mirror.get("summaries") or []):
        if isinstance(s, dict) and s.get("tier") in TIERS:
            raw[s["tier"]] = s
    out = []
    for tier in TIERS:
        s = raw.get(tier, {})
        row = {"tier": tier}
        for f in _SUMMARY_FIELDS:
            v = s.get(f)
            row[f] = int(v) if isinstance(v, (int, float)) else 0
        out.append(row)
    return out


def _num(v: Any, default: int = 0) -> int:
    return int(v) if isinstance(v, (int, float)) else default


def _allocations(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("allocations")
    if not isinstance(raw, list):
        return []
    out = []
    for a in raw:
        if not isinstance(a, dict) or not a.get("allocation_id"):
            continue
        tier = a.get("tier")
        if tier not in TIERS:
            continue
        state = a.get("state")
        if state not in _VALID_STATE:
            state = "running"
        out.append({
            "allocation_id": str(a["allocation_id"]),
            "tier": tier,
            "ms032_tier": _num(a.get("ms032_tier")),
            "isolation": a.get("isolation", "?"),
            "tool": a.get("tool", "?"),
            "capability_token_id": a.get("capability_token_id"),
            "profile": a.get("profile", "private"),
            "actor": a.get("actor", "unknown"),
            "allocated_at": a.get("allocated_at"),
            "release_at": a.get("release_at"),
            "ttl_seconds": a.get("ttl_seconds"),
            "resident_mb": _num(a.get("resident_mb")),
            "cpu_percent": _num(a.get("cpu_percent")),
            "state": state,
            "trace_id": a.get("trace_id"),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-15 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(SANDBOX_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-sandbox-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "allocations": _allocations(mirror),
        "signature": mirror.get("signature"),  # MS003 sig over canonical JSON
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef sandbox mirror consumer (M060 D-15)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "summaries"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "summaries":
        _print(snapshot()["summaries"])
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
