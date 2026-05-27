#!/usr/bin/env python3
"""scripts/mirror/selfdef-profile-mirror.py — READ-ONLY consumer of the selfdef
active-profile mirror (M060 D-02 / R10063-R10068).

The data model behind the D-02 profile-choices cockpit dashboard. CROSS-REPO
MIRROR: the authoritative profile-authority state lives in selfdef (the IPS) —
MS040 six-profile authority matrix (private/fast/careful/autonomous/
experimental/production) + MS039 L0..L6 authority levels + Ring 0..4. selfdef
publishes the ACTIVE profile + the transition history through the MS007
typed-mirror crate `selfdef-profile-mirror`; sovereign-os renders it READ-ONLY.
Profile switches are `sovereign profile set` / selfdefctl + MS003-signed verbs
on the IPS side ONLY (MS043 R10212) — sovereign-os NEVER mutates IPS state. The
six-profile envelopes themselves are static doctrine rendered client-side.

Mirror artifact (selfdef-profile-mirror::ProfileMirrorSnapshot 1.0.0):
  schema_version · active · since · actor · envelope ·
  history[{ts,from,to,actor,rationale,signature}]

Sovereignty: stdlib-only. Absent artifact → the MS040 R09535 offline default
(active=private, envelope "L0-L1 only · no Ring 4", empty history), NEVER a
crash. This is the `core` surface for the sovereign-os mirror; `scripts/
operator/profile-mirror-api.py` serves it (as /api/profile/show — the exact
contract the D-02 webapp already fetches), `sovereign-osctl profile-mirror`
drives it, the D-02 webapp renders it.

  selfdef-profile-mirror.py show [--json]   the /api/profile/show payload
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

PROFILE_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_PROFILE_MIRROR",
    "/run/sovereign-os/selfdef-mirror/active-profile.json",
))

# MS040 six-profile authority matrix.
PROFILES = ("private", "fast", "careful", "autonomous", "experimental", "production")
# MS040 R09535 offline default resolver: Private when no explicit selection.
OFFLINE_DEFAULT = {
    "active": "private",
    "since": "(offline default per MS040 R09535)",
    "actor": "(no operator key loaded)",
    "envelope": "L0-L1 only · no Ring 4",
    "history": [],
}


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _history(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for h in raw:
        if not isinstance(h, dict):
            continue
        out.append({
            "ts": h.get("ts"),
            "from": h.get("from"),
            "to": h.get("to"),
            "actor": h.get("actor", "unknown"),
            "rationale": h.get("rationale", ""),
            "signature": h.get("signature"),
        })
    return out


def show() -> dict[str, Any]:
    """The /api/profile/show payload, projected from the selfdef mirror.
    Online → the published active profile + history; offline → MS040 R09535
    default (Private)."""
    mirror = _read_mirror(PROFILE_MIRROR)
    if not mirror:
        return {
            "schema_version": SCHEMA_VERSION,
            "mirror_status": "offline",
            "mirror_source": "selfdef-profile-mirror (MS007 typed mirror, read-only)",
            **OFFLINE_DEFAULT,
        }
    active = mirror.get("active")
    if active not in PROFILES:
        active = "private"
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online",
        "mirror_source": "selfdef-profile-mirror (MS007 typed mirror, read-only)",
        "active": active,
        "since": mirror.get("since", "—"),
        "actor": mirror.get("actor", "unknown"),
        "envelope": mirror.get("envelope", "—"),
        "history": _history(mirror.get("history")),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef active-profile mirror consumer (M060 D-02)")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("show")
    sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    _print(show())
    return 0


if __name__ == "__main__":
    sys.exit(main())
