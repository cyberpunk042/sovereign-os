#!/usr/bin/env python3
"""scripts/inference/goal-ctl.py — the `/goal` locked-goal state + verbs
(SDD-719, implementation slice 1; the operator-facing surface of SDD-718's
local-agent autonomy).

A single durable, root-owned goal the agent loop pursues on its own (SDD-719
loop-until-goal, driven by goal-driver.py). The goal `text` is
OPERATOR-VERBATIM and SACROSANCT — only `set` writes it; the loop only ever
appends progress + bumps the iteration count, never rewrites the objective.

State (atomic os.replace): /etc/sovereign-os/agent-state.json (env-overridable
SOVEREIGN_OS_AGENT_STATE), shared by both SDD-718 tiers + the cockpit:

  {"goal": {"text","status","plan","set_at","set_by","iterations","last_progress"}}

status: active | paused | done | abandoned. Absent file / no goal → "(no goal)".

Sovereignty: stdlib-only; DRY-nothing-destructive (every verb is a small state
edit, never executes anything); non-root against /etc fails cleanly (rc 2).

  goal-ctl.py set "<text>" [--plan step --plan step ...]
  goal-ctl.py show [--json]
  goal-ctl.py pause | resume | done | abandon
  goal-ctl.py progress "<one-line>"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

STATE_PATH = Path(
    os.environ.get("SOVEREIGN_OS_AGENT_STATE", "/etc/sovereign-os/agent-state.json")
)

VALID_STATUS = frozenset({"active", "paused", "done", "abandoned"})


def _read_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict[str, Any]) -> int:
    """Atomic write; rc 0 ok, rc 2 not writable (e.g. non-root against /etc)."""
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_PATH)
        return 0
    except OSError as e:
        print(f"goal-ctl: cannot write {STATE_PATH}: {e}", file=sys.stderr)
        return 2


def _now() -> int:
    # Wall-clock is intentional here (a goal's set_at is a real timestamp).
    import time

    return int(time.time())


def set_goal(text: str, plan: list[str] | None) -> int:
    text = text.strip()
    if not text:
        print("goal-ctl: goal text is empty", file=sys.stderr)
        return 2
    state = _read_state()
    state["goal"] = {
        "text": text,  # SACROSANCT — operator-verbatim; never rewritten by the loop
        "status": "active",
        "plan": plan or [],
        "set_at": _now(),
        "set_by": "operator",
        "iterations": 0,
        "last_progress": "",
    }
    rc = _write_state(state)
    if rc == 0:
        print(f"goal locked (active): {text}")
    return rc


def _get_goal() -> dict[str, Any] | None:
    g = _read_state().get("goal")
    return g if isinstance(g, dict) and g.get("text") else None


def _set_status(status: str) -> int:
    g = _get_goal()
    if not g:
        print("goal-ctl: no goal set", file=sys.stderr)
        return 2
    g["status"] = status
    state = _read_state()
    state["goal"] = g
    rc = _write_state(state)
    if rc == 0:
        print(f"goal → {status}: {g['text']}")
    return rc


def add_progress(line: str) -> int:
    g = _get_goal()
    if not g:
        print("goal-ctl: no goal set", file=sys.stderr)
        return 2
    g["iterations"] = int(g.get("iterations", 0)) + 1
    g["last_progress"] = line.strip()
    # The loop appends progress + bumps iterations; it NEVER touches `text`.
    state = _read_state()
    state["goal"] = g
    return _write_state(state)


def show(as_json: bool) -> int:
    g = _get_goal()
    if as_json:
        print(json.dumps(g or {}, indent=2))
        return 0
    if not g:
        print("(no goal)")
        return 0
    print(f"goal   : {g['text']}")
    print(f"status : {g['status']}   iterations: {g.get('iterations', 0)}")
    if g.get("plan"):
        print("plan   :")
        for i, step in enumerate(g["plan"], 1):
            print(f"  {i}. {step}")
    if g.get("last_progress"):
        print(f"last   : {g['last_progress']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_set = sub.add_parser("set", help="lock a new goal (status active)")
    p_set.add_argument("text")
    p_set.add_argument("--plan", action="append", default=None, help="a plan step (repeatable)")

    p_show = sub.add_parser("show", help="show the current goal")
    p_show.add_argument("--json", action="store_true")

    sub.add_parser("pause", help="stop the loop pursuing it (goal stays locked)")
    sub.add_parser("resume", help="restart the loop")
    sub.add_parser("done", help="close the goal as done")
    sub.add_parser("abandon", help="close the goal as abandoned")

    p_prog = sub.add_parser("progress", help="append a progress note (loop writes these)")
    p_prog.add_argument("line")

    args = ap.parse_args(argv)

    if args.cmd == "set":
        return set_goal(args.text, args.plan)
    if args.cmd == "show":
        return show(args.json)
    if args.cmd in ("pause", "resume", "done", "abandon"):
        status = {"pause": "paused", "resume": "active", "done": "done", "abandon": "abandoned"}[args.cmd]
        return _set_status(status)
    if args.cmd == "progress":
        return add_progress(args.line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
