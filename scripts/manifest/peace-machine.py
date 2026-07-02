#!/usr/bin/env python3
"""scripts/manifest/peace-machine.py — peace-machine health core
(M060 D-20 / R10126-R10128).

The data model behind the D-20 peace-machine-health cockpit dashboard. This is
sovereign-os-NATIVE — the peace machine is M059's sovereign close ("the
super-model is the whole governed machine"). It surfaces the 5 peace-machine
properties (M059 E0577, dump 18338-18341, VERBATIM) and overlays the live
verdict from the `sovereign-os-peace-check` validator (R09980-R09982).

  M059 5 peace-machine properties (dump 18338-18341, verbatim):
    powerful   — "powerful enough to act"
    disciplined— "disciplined enough to explain itself"
    reversible — "reversible enough to trust"
    flexible   — "flexible enough to evolve"
    sovereign  — "sovereign enough that intelligence remains in the user's hands"
  Each is enforced by M048..M058 modules collectively (R09966); the validator
  exits 0 ONLY when all 5 pass (R09981).

The live verdict is read from the peace-check validator's published JSON
(/run/sovereign-os/peace-check.json) — the validator runs the checks; this core
only READS its result. Absent → each property status "unknown" + overall
"unknown" + the static M059 doctrine (never a crash, never fabricates a PASS).

Sovereignty: stdlib-only. This is the `core` surface; `scripts/operator/
peace-machine-api.py` serves it, `sovereign-osctl peace-machine` drives it, the
D-20 webapp renders it.

  peace-machine.py snapshot   [--json]   full dashboard model
  peace-machine.py properties [--json]   the 5 M059 properties + status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

PEACE_CHECK = Path(os.environ.get(
    "SOVEREIGN_OS_PEACE_CHECK", "/run/sovereign-os/peace-check.json",
))

# M059 E0577 (dump 18338-18341) verbatim quotes + the modules that enforce each
# property (R09966-R09971). Static doctrine — the LIVE status comes from the
# validator; this is the always-true contract the dashboard renders.
PROPERTIES = (
    {"key": "powerful", "name": "Powerful", "quote": "powerful enough to act",
     "backed": "Blackwell + 4090 + AVX compute online (M058 scheduler, R09967)"},
    {"key": "disciplined", "name": "Disciplined", "quote": "disciplined enough to explain itself",
     "backed": "M049 13-field span + MS033 policy trace active (R09968)"},
    {"key": "reversible", "name": "Reversible", "quote": "reversible enough to trust",
     "backed": "ZFS snapshots + MS041 commit chain (M047 continuity, R09969)"},
    {"key": "flexible", "name": "Flexible", "quote": "flexible enough to evolve",
     "backed": "M046 LoRA Foundry promote pipeline (R09970)"},
    {"key": "sovereign", "name": "Sovereign", "quote": "sovereign enough that intelligence remains in the user's hands",
     "backed": "MS003 key chain + no mandatory cloud, operator-controlled (R09965/R09971)"},
)
_PROP_KEYS = tuple(p["key"] for p in PROPERTIES)
_VALID_STATUS = frozenset({"healthy", "degraded", "failing", "unknown"})
_VALID_OVERALL = frozenset({"healthy", "degraded", "failing", "unknown"})


def _read_check(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _validator_log(check: dict[str, Any]) -> list[dict[str, str]]:
    raw = check.get("validator_log")
    if not isinstance(raw, list):
        return []
    out = []
    for ln in raw:
        if isinstance(ln, dict) and "text" in ln:
            cls = ln.get("cls")
            out.append({"cls": cls if cls in ("ok", "warn", "bad", "muted") else "muted",
                        "text": str(ln["text"])})
    return out


def snapshot() -> dict[str, Any]:
    """The full D-20 dashboard model. Static M059 doctrine + live validator
    verdict (or 'unknown' when the validator hasn't published)."""
    check = _read_check(PEACE_CHECK)
    online = bool(check)
    statuses = check.get("properties") if isinstance(check.get("properties"), dict) else {}

    properties = []
    for p in PROPERTIES:
        st = statuses.get(p["key"])
        if st not in _VALID_STATUS:
            st = "unknown"
        properties.append({**p, "status": st})

    overall = check.get("overall")
    if overall not in _VALID_OVERALL:
        overall = "unknown"

    exit_code = check.get("exit_code") if isinstance(check.get("exit_code"), int) else None

    log = _validator_log(check)
    if not log and not online:
        log = [{"cls": "muted",
                "text": "sovereign-os-peace-check has not published a result yet "
                        "(run /usr/bin/sovereign-os-peace-check --json; R09980-R09982)"}]

    return {
        "schema_version": SCHEMA_VERSION,
        "validator_status": "online" if online else "offline",
        "overall": overall,
        "captured_at": check.get("captured_at"),
        "exit_code": exit_code,
        "properties": properties,
        "validator_log": log,
        "closing_doctrine": "powerful · disciplined · reversible · flexible · sovereign "
                            "— five properties enforced by M048..M058 collectively (M059 R09966)",
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="peace-machine health core (M060 D-20)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "properties"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "properties":
        _print(snapshot()["properties"])
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
