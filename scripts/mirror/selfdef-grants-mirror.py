#!/usr/bin/env python3
"""scripts/mirror/selfdef-grants-mirror.py — READ-ONLY consumer of the selfdef
grants mirror (M060 D-13 / R10114-R10115).

The data model behind the D-13 filesystem-grants cockpit dashboard. This is a
**cross-repo mirror consumer**, not a native source: the authoritative grant
state lives in selfdef (the IPS) — MS037 fanotify filesystem grants, MS038
network grants, MS035 capability grants, MS034 communication grants, MS032/
MS036 sandbox grants. selfdef publishes them through the MS007 typed-mirror
crate `selfdef-grants-mirror`; sovereign-os reads that published artifact and
renders it READ-ONLY. Grant sign/revoke/approve/deny are selfdefctl + MS003
verbs on the IPS side ONLY (R10115 + MS043 R10212) — sovereign-os NEVER mutates
IPS state. No IPS enforcement logic is authored here (operator project-boundary
directive: IPS features live in selfdef).

Mirror artifact (selfdef-grants-mirror::GrantsMirrorSnapshot schema 1.0.0):
  schema_version · captured_at · summaries[{kind,active,pending,expired_24h,
  revoked_24h,quarantined}] · grants[{grant_id,kind,scope,reason,issued_at,
  expires_at,ttl_seconds,profile,actor,state,trace_id}] · pending[{grant_id,
  kind,scope,requester}]

Sovereignty: stdlib-only. Absent artifact → 5 zeroed summaries + empty grants/
pending + mirror_status="offline" (the dashboard renders empty, honestly
showing the mirror isn't published yet), NEVER a crash. This is the `core`
surface for the sovereign-os mirror; `scripts/operator/grants-mirror-api.py`
serves it, `sovereign-osctl grants-mirror` drives it, the D-13 webapp renders it.

  selfdef-grants-mirror.py snapshot [--json]   full dashboard model
  selfdef-grants-mirror.py summaries [--json]   per-kind summary tiles only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# The selfdef daemon publishes the MS007 typed-mirror snapshot here.
GRANTS_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_GRANTS_MIRROR",
    "/run/sovereign-os/selfdef-mirror/grants.json",
))

# 5 grant kinds (selfdef MS037/MS038/MS035/MS034/MS032+MS036).
GRANT_KINDS = ("filesystem", "network", "capability", "communication", "sandbox")
_VALID_STATE = frozenset({"active", "pending", "quarantined", "expired", "revoked"})
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
    """One summary row per grant kind, in canonical order, zero-filled."""
    raw = {}
    for s in (mirror.get("summaries") or []):
        if isinstance(s, dict) and s.get("kind") in GRANT_KINDS:
            raw[s["kind"]] = s
    out = []
    for kind in GRANT_KINDS:
        s = raw.get(kind, {})
        row = {"kind": kind}
        for f in _SUMMARY_FIELDS:
            v = s.get(f)
            row[f] = int(v) if isinstance(v, (int, float)) else 0
        out.append(row)
    return out


def _grants(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("grants")
    if not isinstance(raw, list):
        return []
    out = []
    for g in raw:
        if not isinstance(g, dict) or not g.get("grant_id"):
            continue
        kind = g.get("kind")
        if kind not in GRANT_KINDS:
            continue
        state = g.get("state")
        if state not in _VALID_STATE:
            state = "active"
        out.append({
            "grant_id": str(g["grant_id"]),
            "kind": kind,
            "scope": g.get("scope", ""),
            "reason": g.get("reason", ""),
            "issued_at": g.get("issued_at"),
            "expires_at": g.get("expires_at"),
            "ttl_seconds": g.get("ttl_seconds"),
            "profile": g.get("profile", "private"),
            "actor": g.get("actor", "unknown"),
            "state": state,
            "trace_id": g.get("trace_id"),
        })
    return out


def _pending(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("pending")
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if not isinstance(p, dict) or not p.get("grant_id"):
            continue
        kind = p.get("kind")
        if kind not in GRANT_KINDS:
            continue
        out.append({
            "grant_id": str(p["grant_id"]),
            "kind": kind,
            "scope": p.get("scope", ""),
            "requester": p.get("requester", "unknown"),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-13 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(GRANTS_MIRROR)
    online = bool(mirror)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if online else "offline",
        "mirror_source": "selfdef-grants-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "grants": _grants(mirror),
        "pending": _pending(mirror),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef grants mirror consumer (M060 D-13)")
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
