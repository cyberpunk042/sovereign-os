#!/usr/bin/env python3
"""scripts/mirror/selfdef-rules-mirror.py — READ-ONLY consumer of the
selfdef nftables rules mirror (M060 D-12 / MS024 + MS038 + MS039).

The data model behind the D-12 networking dashboards (network-edge +
edge-firewall). CROSS-REPO MIRROR: the authoritative nftables rule
set lives in selfdef (the IPS) — MS024 nftables boundary enforcement
+ MS038 network boundary + MS039 Ring 0..4 trust topology, published
through the MS007 typed-mirror crate `selfdef-rules-mirror` (read-only)
and the daemon-resident `selfdef-rules-registry`. sovereign-os renders
it READ-ONLY (R10212) — the operator never appends rules through this
surface (rules are installed via selfdefctl + nft at the IPS layer).

Mirror artifact (selfdef-rules-mirror::RulesMirrorSnapshot 1.0.0):
  schema_version · captured_at · summaries[{ring,rule_count,
  total_bytes,total_packets,pending_l3}] · rules[{handle,rule_id,
  ring,table,chain,match_expr,disposition,priority,packets,bytes,
  installed_at,installed_by,signature}] · signature

Sovereignty: stdlib-only. Absent artifact → empty rules + offline
mirror_status (graceful), NEVER a crash. The 5-ring topology
(SovereignKernel / TrustedLocal / Sandboxed / Experimental /
CloudExternal) maps to the D-12 dashboard's per-ring rows.

  selfdef-rules-mirror.py snapshot [--json]    full networking model
  selfdef-rules-mirror.py summaries [--json]   per-ring summaries only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

RULES_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_RULES_MIRROR",
    "/run/sovereign-os/selfdef-mirror/rules.json",
))

# MS039 5-ring trust topology per the rules-mirror crate (R10246-R10250).
TRUST_RINGS = (
    "sovereign_kernel", "trusted_local", "sandboxed",
    "experimental", "cloud_external",
)

# nftables dispositions per the rules-mirror crate.
DISPOSITIONS = ("accept", "drop", "reject", "jump", "continue", "return")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _summaries(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("summaries") or []
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        ring = s.get("ring", "experimental")
        if ring not in TRUST_RINGS:
            ring = "experimental"
        out.append({
            "ring": ring,
            "rule_count":    int(s.get("rule_count", 0)),
            "total_bytes":   int(s.get("total_bytes", 0)),
            "total_packets": int(s.get("total_packets", 0)),
            "pending_l3":    int(s.get("pending_l3", 0)),
        })
    return out


def _rules(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("rules")
    if not isinstance(raw, list):
        return []
    out = []
    for r in raw:
        if not isinstance(r, dict) or not r.get("rule_id"):
            continue
        ring = r.get("ring", "experimental")
        if ring not in TRUST_RINGS:
            ring = "experimental"
        dispo = r.get("disposition", "accept")
        if dispo not in DISPOSITIONS:
            dispo = "accept"
        out.append({
            "handle":       int(r.get("handle", 0)),
            "rule_id":      str(r["rule_id"]),
            "ring":         ring,
            "table":        str(r.get("table", "")),
            "chain":        str(r.get("chain", "")),
            "match_expr":   str(r.get("match_expr", "")),
            "disposition":  dispo,
            "priority":     int(r.get("priority", 0)),
            "packets":      int(r.get("packets", 0)),
            "bytes":        int(r.get("bytes", 0)),
            "installed_at": str(r.get("installed_at", "")),
            "installed_by": r.get("installed_by"),
            "signature":    str(r.get("signature", "")),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-12 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(RULES_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-rules-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "rules": _rules(mirror),
        "signature": mirror.get("signature"),  # MS003 sig over canonical JSON
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef rules mirror consumer (M060 D-12)")
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
