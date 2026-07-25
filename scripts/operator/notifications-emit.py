#!/usr/bin/env python3
"""scripts/operator/notifications-emit.py — OPTIONAL outbound fan-out of the
notifications inbox (the 🔔 badge items) through the notifykit channels.

OFF BY DEFAULT. Does nothing unless SOVEREIGN_OS_NOTIFICATIONS_FANOUT is set.
Meant to run as a periodic oneshot (systemd timer), NOT from the API's GET
handler — a GET must be side-effect free, and delivery must not fire on every
page poll.

Flow: import the SAME `collect()` the API serves (no HTTP self-call) → filter to
fresh items (de-dup vs a state file so each distinct item is delivered at most
ONCE until it clears and re-fires) → dispatch through notifykit. notifykit's own
per-channel gates (SMS needs high/high, etc.) + the operator's config decide which
channels actually fire; this just hands each item over with a severity-mapped
priority/urgency.

De-dup state: /var/lib/sovereign-os/notifications-fanout-state.json — the set of
item keys (`id:severity`) already delivered. Keys absent from the current
aggregate are pruned, so a cleared-then-returning item fires again.

Env:
  SOVEREIGN_OS_NOTIFICATIONS_FANOUT         master switch (unset → exit 0, send nothing)
  SOVEREIGN_OS_NOTIFICATIONS_FANOUT_STATE   override the de-dup state path (tests)
  + the standard notifykit env (SOVEREIGN_OS_NOTIFYKIT_CONFIG / _OVERRIDES).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_REPO_ROOT))   # for `import tools.notifykit`
sys.path.insert(0, str(_HERE))        # sibling operator modules

STATE_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_NOTIFICATIONS_FANOUT_STATE",
    "/var/lib/sovereign-os/notifications-fanout-state.json"))

# severity → (priority, urgency). notifykit's per-channel gates filter from here;
# `down` (something failed) is escalated so SMS-class gates can trip.
SEV_TO_LEVELS = {
    "down": ("high", "urgent"),
    "attention": ("normal", "high"),
}


def _fanout_enabled() -> bool:
    return bool(os.environ.get("SOVEREIGN_OS_NOTIFICATIONS_FANOUT"))


def _load_collect():
    """Load `collect` from the hyphenated sibling notifications-api.py by path."""
    spec = importlib.util.spec_from_file_location(
        "notifications_api", _HERE / "notifications-api.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.collect


def _read_state() -> set[str]:
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _write_state(keys: set[str]) -> bool:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(sorted(keys)), encoding="utf-8")
        return True
    except OSError:
        return False


def _key(item: dict) -> str:
    return f"{item.get('id')}:{item.get('severity')}"


def run(dry: bool = False) -> int:
    collect = _load_collect()
    env = collect()
    items = env.get("items", [])
    current = {_key(it): it for it in items}
    prior = _read_state()
    fresh = [current[k] for k in current if k not in prior]

    if dry:
        print(json.dumps({
            "fanout_enabled": _fanout_enabled(),
            "state_path": str(STATE_PATH),
            "current": sorted(current),
            "already_delivered": sorted(prior & set(current)),
            "would_send": [_key(it) for it in fresh],
        }, indent=2))
        return 0

    if not _fanout_enabled():
        return 0  # master switch off — deliver nothing

    if fresh:
        # Fail SAFE: if we can't persist the de-dup state, don't deliver — a
        # non-persistent run would re-send every distinct item on every tick.
        if not os.access(STATE_PATH.parent if STATE_PATH.parent.exists()
                         else STATE_PATH.parent.parent, os.W_OK):
            print(f"notifications-emit: state dir not writable ({STATE_PATH.parent}); "
                  "skipping delivery to avoid re-send spam", file=sys.stderr)
            return 0
        try:
            from tools.notifykit import Event, ChannelRegistry  # noqa: N811
            from tools.notifykit.cli import _load_config
        except Exception as e:  # noqa: BLE001 — no notifykit → nothing to do
            print(f"notifications-emit: notifykit unavailable ({e}); nothing sent",
                  file=sys.stderr)
            return 0
        registry = ChannelRegistry(_load_config())
        for it in fresh:
            pri, urg = SEV_TO_LEVELS.get(it.get("severity"), ("normal", "normal"))
            registry.dispatch(Event(
                title=str(it.get("title") or it.get("id")),
                message=str(it.get("remediation") or it.get("detail") or ""),
                priority=pri, urgency=urg,
                source="sovereign-notifications",
                dedupe_key=_key(it),
            ))

    # New state = the keys present in the CURRENT aggregate (delivered this run
    # or already delivered before). Cleared items drop out → they re-fire if they
    # return. Written even when `fresh` is empty so cleared items get pruned.
    _write_state(set(current.keys()))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="optional outbound fan-out of the notifications inbox")
    p.add_argument("--dry-run", action="store_true",
                   help="print what WOULD be delivered (respects the current de-dup state), send nothing")
    args = p.parse_args(argv)
    return run(dry=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
