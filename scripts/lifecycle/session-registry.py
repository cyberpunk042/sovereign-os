#!/usr/bin/env python3
"""scripts/lifecycle/session-registry.py — active-session registry core
(M060 D-01 / R10059-R10062).

The data model behind the D-01 active-sessions cockpit dashboard. Reads the
M057 lifecycle engine's published session registry and projects each task
session onto the dashboard shape: where it sits in the M057 12-step lifecycle,
its profile envelope, SRP agent (M075), branch count and ETA.

  M057 12-step Task Lifecycle (E0548 / M00952-M00964, verbatim):
    1 Intake · 2 Normalize · 3 Profile Resolve · 4 Map · 5 Plan/Compile ·
    6 Route · 7 Execute · 8 Observe · 9 Evaluate · 10 Commit/Rollback ·
    11 Learn · 12 Resume/Archive
  M057 9 task states (E0556 / M00964, verbatim):
    active · paused · waiting_user · waiting_tool · hibernated · completed ·
    failed · rolled_back · archived
  M057 Critical Data Flow Law (M00965): "Text is not the system state. Text
  is payload inside typed state."

Sovereignty: stdlib-only. The registry path follows the established
/run/sovereign-os/*.json convention (model-state.json, scheduler-backpressure
.json). Absent/empty registry → zero sessions (the dashboard shows "no active
sessions — invoke `sovereign run`"), NEVER a crash. This is the `core` surface
of the §1g 8-surface ladder for the sessions module; `scripts/operator/
sessions-api.py` serves it, `sovereign-osctl sessions` drives it, the D-01
webapp renders it.

  session-registry.py active  [--json]   full dashboard model (sessions+summary)
  session-registry.py summary [--json]    the four summary counters only
  session-registry.py steps   [--json]    the M057 12-step + 9-state reference
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

SESSION_REGISTRY = Path(os.environ.get(
    "SOVEREIGN_OS_SESSION_REGISTRY", "/run/sovereign-os/sessions.json",
))

# M057 verbatim (E0548). Index i (0-based) → lifecycle step i+1.
LIFECYCLE_STEPS = (
    "Intake", "Normalize", "Profile Resolve", "Map", "Plan/Compile", "Route",
    "Execute", "Observe", "Evaluate", "Commit/Rollback", "Learn", "Resume/Archive",
)
# M057 verbatim (E0556 / M00964) — the 9 task states.
TASK_STATES = (
    "active", "paused", "waiting_user", "waiting_tool", "hibernated",
    "completed", "failed", "rolled_back", "archived",
)
# Dashboard summary buckets: which M057 states count as "blocked" (stalled
# awaiting something) for the D-01 blocked counter.
_BLOCKED_STATES = frozenset({"paused", "waiting_user", "waiting_tool"})


def _read_registry(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _clamp_step(v: Any) -> int:
    try:
        s = int(v)
    except (TypeError, ValueError):
        return 1
    return max(1, min(12, s))


def _normalise(rec: dict[str, Any]) -> dict[str, Any]:
    """Project a raw registry record onto the D-01 session shape. Unknown
    state passes through (the dashboard renders it muted); step clamped 1-12."""
    state = rec.get("state")
    if state is None:
        state = "active"  # a registry entry with no state is presumed running
    # A present-but-unrecognised state passes through unchanged (honest — we
    # never relabel engine data); it renders muted and counts in no bucket.
    step = _clamp_step(rec.get("step"))
    out = {
        "id": str(rec.get("id", "?")),
        "kind": rec.get("kind", "task"),
        "profile": rec.get("profile", "private"),
        "state": state,
        "step": step,
        "step_name": LIFECYCLE_STEPS[step - 1],
        "srp_agent": rec.get("srp_agent", "Conductor"),
        "started_at": rec.get("started_at"),
        "eta_seconds": rec.get("eta_seconds"),
        "branch_count": rec.get("branch_count", 0),
    }
    # SDD-057 (M047 save-state): read-only passthrough of the continuity fields the
    # save-state orchestrator + the future M057 session-process runtime populate —
    # `pid` (the CRIU checkpoint target) + `dataset` (the ZFS-snapshot dataset key).
    # Surfaced only when present; the reader stays pure (never invents them).
    if rec.get("pid") is not None:
        out["pid"] = rec.get("pid")
    if rec.get("dataset") is not None:
        out["dataset"] = rec.get("dataset")
    return out


def list_sessions(registry: Path = SESSION_REGISTRY) -> list[dict[str, Any]]:
    reg = _read_registry(registry)
    raw = reg.get("sessions")
    if not isinstance(raw, list):
        return []
    return [_normalise(r) for r in raw if isinstance(r, dict) and r.get("id")]


def _summary(sessions: list[dict[str, Any]]) -> dict[str, int]:
    active = sum(1 for s in sessions if s["state"] == "active")
    hibernated = sum(1 for s in sessions if s["state"] == "hibernated")
    blocked = sum(1 for s in sessions if s["state"] in _BLOCKED_STATES)
    branches = sum(int(s.get("branch_count") or 0) for s in sessions)
    return {"active": active, "hibernated": hibernated,
            "blocked": blocked, "branches": branches}


def active(registry: Path = SESSION_REGISTRY) -> dict[str, Any]:
    """The full D-01 dashboard model."""
    sessions = list_sessions(registry)
    return {
        "schema_version": SCHEMA_VERSION,
        "sessions": sessions,
        "summary": _summary(sessions),
    }


def steps_reference() -> dict[str, Any]:
    return {
        "lifecycle_steps": list(LIFECYCLE_STEPS),
        "task_states": list(TASK_STATES),
        "law": "Text is not the system state. Text is payload inside typed state.",
        "source": "M057 E0548 + E0556 + M00965",
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="active-session registry core (M060 D-01)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("active", "summary", "steps"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "active"
    if cmd == "summary":
        _print(active()["summary"])
    elif cmd == "steps":
        _print(steps_reference())
    else:
        _print(active())
    return 0


if __name__ == "__main__":
    sys.exit(main())
