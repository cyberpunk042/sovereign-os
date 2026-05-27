#!/usr/bin/env python3
"""scripts/mirror/selfdef-capability-mirror.py — READ-ONLY consumer of the
selfdef capability-token mirror (M060 D-14 / R10116-R10117).

The data model behind the D-14 capability-tokens cockpit dashboard. CROSS-REPO
MIRROR: the authoritative capability-token state lives in selfdef (the IPS) —
MS035 64-bit capability_word tokens + MS039 Ring 0..4 trust topology + L0..L6
authority levels + F04146 parent-child inheritance, published through the MS007
typed-mirror crate `selfdef-capability-mirror`. sovereign-os renders it
READ-ONLY. Token issue/revoke are selfdefctl + MS003 verbs on the IPS side ONLY
(R10117 + MS043 R10212) — sovereign-os NEVER mutates IPS state.

Mirror artifact (selfdef-capability-mirror::CapabilityMirrorSnapshot 1.0.0):
  schema_version · captured_at · summaries[{ring,active,pending,expired_24h,
  revoked_24h,quarantined}] · tokens[{token_id,capability_word,actor,profile,
  trust_ring,authority_level,allowed_tools[],sandbox_tier,issued_at,expires_at,
  ttl_seconds,state,trace_id,parent_token_id}]

Sovereignty: stdlib-only. Absent artifact → 5 zeroed ring summaries + empty
tokens + mirror_status="offline" (graceful), NEVER a crash.

  selfdef-capability-mirror.py snapshot [--json]   full dashboard model
  selfdef-capability-mirror.py summaries [--json]   per-ring summary tiles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

CAPABILITY_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_CAPABILITY_MIRROR",
    "/run/sovereign-os/selfdef-mirror/capability-tokens.json",
))

# MS039 Ring 0..4 trust topology.
RINGS = ("ring0", "ring1", "ring2", "ring3", "ring4")
# token lifecycle states.
_VALID_STATE = frozenset({"active", "pending", "expired", "revoked", "quarantined"})
_SUMMARY_FIELDS = ("active", "pending", "expired_24h", "revoked_24h", "quarantined")


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
        if isinstance(s, dict) and s.get("ring") in RINGS:
            raw[s["ring"]] = s
    out = []
    for ring in RINGS:
        s = raw.get(ring, {})
        row = {"ring": ring}
        for f in _SUMMARY_FIELDS:
            v = s.get(f)
            row[f] = int(v) if isinstance(v, (int, float)) else 0
        out.append(row)
    return out


def _tokens(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("tokens")
    if not isinstance(raw, list):
        return []
    out = []
    for t in raw:
        if not isinstance(t, dict) or not t.get("token_id"):
            continue
        ring = t.get("trust_ring")
        if ring not in RINGS:
            continue
        state = t.get("state")
        if state not in _VALID_STATE:
            state = "active"
        tools = t.get("allowed_tools")
        out.append({
            "token_id": str(t["token_id"]),
            "capability_word": t.get("capability_word", "0x0000000000000000"),
            "actor": t.get("actor", "unknown"),
            "profile": t.get("profile", "private"),
            "trust_ring": ring,
            "authority_level": t.get("authority_level", "l0_observe"),
            "allowed_tools": tools if isinstance(tools, list) else [],
            "sandbox_tier": t.get("sandbox_tier", "A"),
            "issued_at": t.get("issued_at"),
            "expires_at": t.get("expires_at"),
            "ttl_seconds": t.get("ttl_seconds"),
            "state": state,
            "trace_id": t.get("trace_id"),
            "parent_token_id": t.get("parent_token_id", ""),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-14 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(CAPABILITY_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-capability-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "tokens": _tokens(mirror),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef capability mirror consumer (M060 D-14)")
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
