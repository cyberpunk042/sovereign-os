#!/usr/bin/env python3
"""scripts/hardware/profile-flex.py — R224 (SDD-026 Z-3) flex-profile state.

Operator-named: "not just a mode by profile but a profile that is
flexible and allow not only the AI and the tools but also me to
download, fine-tune, parameters, build, run, use and train and adapt
and use and eval".

The YAML profiles under profiles/runtime/ are the AUTHORED baseline.
Operator-runtime tweaks land in
/var/lib/sovereign-os/flex-profile.json as a JSON DELTA — no edit
to the YAML baseline required, fully reversible.

Sub-modes:
  show         Print the active profile id + the current flex deltas
               (each delta entry: { key, value, set_at }).
  set K V      Append a delta entry { key: K, value: V, set_at: now }.
               Operator surface for "I want to override `gpu.utilization`
               to 0.85 for the next 4 hours" without editing YAML.
  reset        Clear every delta entry. Profile reverts to YAML baseline.
  history      Print the chronological delta log (audit trail).
  promote      Defer — future round writes the current deltas back
               into the YAML baseline as the operator's blessed
               permanent setting.

Output --json for the future Z-1 dashboard "Profiles" tab; default
output is operator-readable banner.

Exit codes:
  0  operation succeeded
  1  set with no key/value, or reset on already-empty state (non-error
     warnings; future rounds may tighten)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_FLEX_STATE",
        "/var/lib/sovereign-os/flex-profile.json",
    )
)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1.0.0",
            "active_profile_id": _read_active_profile_id(),
            "deltas": [],
        }
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR reading {path}: {e}", file=sys.stderr)
        return {
            "schema_version": "1.0.0",
            "active_profile_id": _read_active_profile_id(),
            "deltas": [],
        }


def write_state(path: Path, state: dict[str, Any]) -> int:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        print(f"ERROR creating parent dir for {path}: {e}", file=sys.stderr)
        print(
            "  (override via --state PATH or SOVEREIGN_OS_FLEX_STATE env)",
            file=sys.stderr,
        )
        return 2
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        tmp.replace(path)
    except PermissionError as e:
        print(f"ERROR writing {path}: {e}", file=sys.stderr)
        return 2
    return 0


def _read_active_profile_id() -> str:
    # Best-effort: operator may set SOVEREIGN_OS_PROFILE or have an
    # /etc/sovereign-os/active-profile sentinel. Otherwise return
    # "(unknown)".
    env = os.environ.get("SOVEREIGN_OS_PROFILE")
    if env:
        return env
    sentinel = Path("/etc/sovereign-os/active-profile")
    if sentinel.exists():
        try:
            return sentinel.read_text().strip()
        except OSError:
            pass
    return "(unknown)"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --------------------------------------------------------- subcmds


def cmd_show(state: dict[str, Any], json_out: bool) -> int:
    if json_out:
        print(json.dumps(state, indent=2))
        return 0
    print("── R224 sovereign-os profile flex (SDD-026 Z-3) ──")
    print(f"  active profile: {state.get('active_profile_id', '(unknown)')}")
    deltas = state.get("deltas") or []
    if not deltas:
        print("  (no flex deltas — profile is at the authored YAML baseline)")
        return 0
    print(f"  {len(deltas)} delta(s) applied (most recent last):")
    for d in deltas:
        ts = d.get("set_at", "?")
        print(f"    [{ts}] {d.get('key', '?')} = {json.dumps(d.get('value'))}")
    return 0


def cmd_set(state: dict[str, Any], path: Path, key: str, value_raw: str, json_out: bool) -> int:
    # Try to parse value as JSON for natural typing (numbers / booleans /
    # nested structures). Fall back to string when not valid JSON.
    try:
        value: Any = json.loads(value_raw)
    except json.JSONDecodeError:
        value = value_raw
    state["deltas"].append(
        {"key": key, "value": value, "set_at": _now_iso()}
    )
    rc = write_state(path, state)
    if rc != 0:
        return rc
    if json_out:
        print(json.dumps(state["deltas"][-1], indent=2))
    else:
        print(f"# R224: flex delta applied — {key} = {json.dumps(value)}")
        print(f"# state file: {path}")
    return 0


def cmd_reset(state: dict[str, Any], path: Path, json_out: bool) -> int:
    if not state.get("deltas"):
        if json_out:
            print(json.dumps({"reset": False, "reason": "already empty"}))
        else:
            print("# R224: no deltas to clear — already at YAML baseline")
        return 1
    pre = len(state["deltas"])
    state["deltas"] = []
    rc = write_state(path, state)
    if rc != 0:
        return rc
    if json_out:
        print(json.dumps({"reset": True, "cleared_count": pre}))
    else:
        print(f"# R224: cleared {pre} flex delta(s); profile reverts to YAML baseline")
    return 0


def cmd_history(state: dict[str, Any], json_out: bool) -> int:
    deltas = state.get("deltas") or []
    if json_out:
        print(json.dumps({"deltas": deltas, "count": len(deltas)}, indent=2))
        return 0
    print("── R224 sovereign-os profile flex — history ──")
    if not deltas:
        print("  (empty)")
        return 0
    for d in deltas:
        print(
            f"  [{d.get('set_at', '?')}] {d.get('key', '?')} = "
            f"{json.dumps(d.get('value'))}"
        )
    return 0


# --------------------------------------------------------- entrypoint


def main() -> int:
    # Pre-scan argv for the order-independent options (--state /
    # --json) so the operator can pass them BEFORE OR AFTER the
    # subcommand. argparse's parent-parser default-merge would
    # otherwise clobber the operator's chosen value with the parent's
    # default when both parents declare the flag.
    argv = sys.argv[1:]
    state_path = DEFAULT_STATE_PATH
    json_out = False
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--state":
            if i + 1 >= len(argv):
                print("ERROR --state requires a path argument", file=sys.stderr)
                return 2
            state_path = Path(argv[i + 1])
            i += 2
            continue
        if a.startswith("--state="):
            state_path = Path(a.split("=", 1)[1])
            i += 1
            continue
        if a == "--json":
            json_out = True
            i += 1
            continue
        cleaned.append(a)
        i += 1

    p = argparse.ArgumentParser(
        description=(
            "R224 (SDD-026 Z-3) flex-profile JSON delta over YAML "
            "baselines. --state and --json are order-independent "
            "(may appear before OR after the subcommand)."
        )
    )
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("show", help="print active profile + applied deltas")
    p_set = sub.add_parser("set", help="apply one flex delta")
    p_set.add_argument("key")
    p_set.add_argument("value")
    sub.add_parser("reset", help="clear every delta — revert to YAML baseline")
    sub.add_parser("history", help="chronological delta log")
    args = p.parse_args(cleaned)
    args.state = state_path
    args.json = json_out

    state = load_state(args.state)
    if args.action == "show":
        return cmd_show(state, args.json)
    if args.action == "set":
        return cmd_set(state, args.state, args.key, args.value, args.json)
    if args.action == "reset":
        return cmd_reset(state, args.state, args.json)
    if args.action == "history":
        return cmd_history(state, args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
