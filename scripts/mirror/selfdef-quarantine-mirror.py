#!/usr/bin/env python3
"""scripts/mirror/selfdef-quarantine-mirror.py — READ-ONLY consumer of the
selfdef tool-quarantine mirror (M060 D-17 / R10121-R10122).

The data model behind the D-17 quarantine cockpit dashboard. CROSS-REPO MIRROR:
the authoritative quarantine archive lives in selfdef (the IPS) — MS042
declaration-vs-observed discipline, the block+quarantine+trace response
(E0429-E0430, dump 17422-17445), exposed by the selfdef `/v1/quarantine`
surface (SDD-064, shipped) and published through the MS007 typed-mirror crate
`selfdef-quarantine-mirror`. sovereign-os renders it READ-ONLY. quarantine
trace/release/forfeit are selfdefctl + MS003 verbs on the IPS side ONLY
(R10122 + MS043 R10212) — sovereign-os NEVER mutates IPS state.

Mirror artifact (selfdef-quarantine-mirror::QuarantineMirrorSnapshot 1.0.0):
  schema_version · captured_at · summaries[{severity,quarantined,released_24h,
  forfeited_24h}] · entries[{quarantine_id,tool,declarer,capability_token_id?,
  blocked_at,updated_at,state,max_severity,mismatches[{field,declared,observed,
  first_observed_at,severity}],trace_id}]

Sovereignty: stdlib-only. Absent artifact → 4 zeroed severity summaries +
empty entries + mirror_status="offline" (graceful), NEVER a crash.

  selfdef-quarantine-mirror.py snapshot [--json]   full dashboard model
  selfdef-quarantine-mirror.py summaries [--json]   per-severity summary tiles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

QUARANTINE_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_QUARANTINE_MIRROR",
    "/run/sovereign-os/selfdef-mirror/quarantine.json",
))

# MS042 4-severity classifier.
SEVERITIES = ("critical", "major", "minor", "informational")
# quarantine entry lifecycle states.
_VALID_STATE = frozenset({"quarantined", "released", "forfeited"})
_SUMMARY_FIELDS = ("quarantined", "released_24h", "forfeited_24h")
# the 7 MS042 declaration fields a mismatch can be on (for the chart).
DECLARATION_FIELDS = ("read_paths", "write_paths", "network_domains", "env_vars",
                      "secret_access", "side_effects", "rollback")


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
        if isinstance(s, dict) and s.get("severity") in SEVERITIES:
            raw[s["severity"]] = s
    out = []
    for sev in SEVERITIES:
        s = raw.get(sev, {})
        row = {"severity": sev}
        for f in _SUMMARY_FIELDS:
            v = s.get(f)
            row[f] = int(v) if isinstance(v, (int, float)) else 0
        out.append(row)
    return out


def _mismatches(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw:
        if not isinstance(m, dict) or not m.get("field"):
            continue
        sev = m.get("severity")
        out.append({
            "field": str(m["field"]),
            "declared": m.get("declared", ""),
            "observed": m.get("observed", ""),
            "first_observed_at": m.get("first_observed_at"),
            "severity": sev if sev in SEVERITIES else "minor",
        })
    return out


def _entries(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("entries")
    if not isinstance(raw, list):
        return []
    out = []
    for e in raw:
        if not isinstance(e, dict) or not e.get("quarantine_id"):
            continue
        state = e.get("state")
        if state not in _VALID_STATE:
            state = "quarantined"
        max_sev = e.get("max_severity")
        out.append({
            "quarantine_id": str(e["quarantine_id"]),
            "tool": e.get("tool", "?"),
            "declarer": e.get("declarer", "unknown"),
            "capability_token_id": e.get("capability_token_id"),
            "blocked_at": e.get("blocked_at"),
            "updated_at": e.get("updated_at"),
            "state": state,
            "max_severity": max_sev if max_sev in SEVERITIES else "minor",
            "mismatches": _mismatches(e.get("mismatches")),
            "trace_id": e.get("trace_id"),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-17 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(QUARANTINE_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-quarantine-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "entries": _entries(mirror),
        "signature": mirror.get("signature"),  # MS003 sig over canonical JSON
        "declaration_fields": list(DECLARATION_FIELDS),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef quarantine mirror consumer (M060 D-17)")
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
