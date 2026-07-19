#!/usr/bin/env python3
"""tools/notifykit/cli.py — the notification-settings command surface.

Backs `sovereign-osctl notifykit …` and the cockpit's shared
notification-settings overlay panel (settings pane, top-right header —
operator directive 2026-07-19, docs/standing-directives/
2026-07-19-notification-settings-overlay-panel.md).

"The whole settings range": channel enable, per-channel gates
(min_priority × min_urgency), static pins, the global default override,
and trigger markdown-frontmatter properties ("important:true and such
markdown properties & metadata as much has in the header").

Writes go to the JSON OVERRIDES overlay (default
/etc/sovereign-os/notifykit-overrides.json, env
SOVEREIGN_OS_NOTIFYKIT_OVERRIDES) — the operator's hand-edited base
TOML is never rewritten (SDD-030 operator-overlay doctrine).

Verbs:
  show [--json]                        effective config (base+overlay)
  set <channel> <key> <value>          key ∈ {enabled, min_priority,
                                       min_urgency, min_priority_static,
                                       min_urgency_static} — *_static
                                       sets the value AND pins it static
  global-override <key> <value>        key ∈ {min_priority, min_urgency}
  global-override clear all            drop the global override
  trigger <name> <prop> <value>        set a frontmatter-style prop
                                       (true/false/int parsed; else str)
  trigger <name> unset <prop>          remove a prop
  test [--priority P] [--urgency U] [--source S]
                                       dispatch a synthetic event

Exit codes: 0 ok · 1 delivery failure (test) · 2 usage error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import (
    DEFAULT_OVERRIDES_PATH,
    GATE_KEYS,
    NotifyConfig,
)
from .event import PRIORITY_LEVELS, URGENCY_LEVELS, Event

DEFAULT_BASE = "/etc/sovereign-os/notifykit.toml"

SET_KEYS = ("enabled", "min_priority", "min_urgency",
            "min_priority_static", "min_urgency_static")


def _base_path() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_NOTIFYKIT_CONFIG", DEFAULT_BASE))


def _overrides_path() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_NOTIFYKIT_OVERRIDES",
                               DEFAULT_OVERRIDES_PATH))


def _load_overlay() -> dict:
    p = _overrides_path()
    if p.is_file():
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_overlay(overlay: dict) -> None:
    p = _overrides_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(overlay, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _load_config() -> NotifyConfig:
    base = _base_path()
    if not base.is_file():
        # No base config yet — the overlay alone still forms a config.
        from .config import merge_overrides
        return NotifyConfig.from_dict(merge_overrides({}, _load_overlay()))
    return NotifyConfig.load(base, _overrides_path())


def _parse_scalar(raw: str):
    """Markdown-frontmatter-style scalar parsing: true/false/int/float,
    else the string itself."""
    low = raw.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def cmd_show(args: argparse.Namespace) -> int:
    cfg = _load_config()
    payload = {
        "base": str(_base_path()),
        "overrides": str(_overrides_path()),
        "sms_present": cfg.sms_present(),
        "global_override": cfg.global_override,
        "channels": {
            name: {
                "kind": c.kind,
                "enabled": c.enabled,
                "effective_gate": cfg.effective_gate(name),
                "static_keys": sorted(c.static_keys),
            }
            for name, c in cfg.channels.items()
        },
        "triggers": cfg.triggers,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    print("── notifykit settings (effective = base TOML + JSON overlay) ──")
    print(f"  base:      {payload['base']}")
    print(f"  overrides: {payload['overrides']}")
    print(f"  SMS present: {payload['sms_present']}"
          "  (no SMS → resend starting point high/urgent per the verbatim)")
    if cfg.global_override:
        print(f"  global override: {cfg.global_override}")
    for name, ch in payload["channels"].items():
        gate = ch["effective_gate"]
        pins = f"  static={ch['static_keys']}" if ch["static_keys"] else ""
        print(f"  {name:10s} kind={ch['kind']:8s} "
              f"{'ON ' if ch['enabled'] else 'off'}  "
              f"gate {gate['min_priority']}/{gate['min_urgency']}{pins}")
    for name, props in payload["triggers"].items():
        print(f"  trigger {name}: {props}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    if args.key not in SET_KEYS:
        print(f"ERROR key {args.key!r} not in {SET_KEYS}", file=sys.stderr)
        return 2
    overlay = _load_overlay()
    ch = overlay.setdefault("channels", {}).setdefault(args.channel, {})
    if args.key == "enabled":
        if args.value.lower() not in ("on", "off", "true", "false"):
            print("ERROR enabled expects on|off", file=sys.stderr)
            return 2
        ch["enabled"] = args.value.lower() in ("on", "true")
    else:
        gate_key = args.key.replace("_static", "")
        levels = PRIORITY_LEVELS if gate_key == "min_priority" else URGENCY_LEVELS
        if args.value not in levels:
            print(f"ERROR {gate_key} expects one of {levels}", file=sys.stderr)
            return 2
        ch[gate_key] = args.value
        if args.key.endswith("_static"):
            static = set(ch.get("static") or [])
            static.add(gate_key)
            ch["static"] = sorted(static)
    _save_overlay(overlay)
    print(f"set {args.channel}.{args.key} = {args.value} "
          f"→ {_overrides_path()}")
    return 0


def cmd_global_override(args: argparse.Namespace) -> int:
    overlay = _load_overlay()
    if args.key == "clear":
        overlay.pop("global_override", None)
        _save_overlay(overlay)
        print(f"global override cleared → {_overrides_path()}")
        return 0
    if args.key not in GATE_KEYS:
        print(f"ERROR key {args.key!r} not in {GATE_KEYS} (or 'clear')",
              file=sys.stderr)
        return 2
    levels = PRIORITY_LEVELS if args.key == "min_priority" else URGENCY_LEVELS
    if args.value not in levels:
        print(f"ERROR {args.key} expects one of {levels}", file=sys.stderr)
        return 2
    overlay.setdefault("global_override", {})[args.key] = args.value
    _save_overlay(overlay)
    print(f"global override {args.key} = {args.value} → {_overrides_path()} "
          "(static-pinned channel keys remain as is)")
    return 0


def cmd_trigger(args: argparse.Namespace) -> int:
    overlay = _load_overlay()
    triggers = overlay.setdefault("triggers", {})
    if args.prop == "unset":
        props = triggers.get(args.name) or {}
        props.pop(args.value, None)
        triggers[args.name] = props
        _save_overlay(overlay)
        print(f"trigger {args.name}: unset {args.value}")
        return 0
    props = triggers.setdefault(args.name, {})
    props[args.prop] = _parse_scalar(args.value)
    _save_overlay(overlay)
    print(f"trigger {args.name}: {args.prop} = {props[args.prop]!r} "
          f"→ {_overrides_path()}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    from .registry import ChannelRegistry
    cfg = _load_config()
    registry = ChannelRegistry(cfg)
    receipts = registry.dispatch(Event(
        title="notifykit test",
        message="synthetic settings-surface test event",
        priority=args.priority, urgency=args.urgency,
        source=args.source,
    ))
    failed = False
    for r in receipts:
        state = "SKIP" if r.skipped else ("OK  " if r.ok else "FAIL")
        failed = failed or (not r.ok and not r.skipped)
        print(f"  [{state}] {r.channel:10s} {r.detail}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="notifykit",
        description="Notification settings — the whole settings range "
        "(channels, gates, static pins, global override, trigger "
        "frontmatter props). Writes the JSON overlay, never the base TOML.",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    ps = sub.add_parser("show", help="effective settings")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_show)

    pt = sub.add_parser("set", help="set a channel key")
    pt.add_argument("channel")
    pt.add_argument("key", help=f"one of {SET_KEYS}")
    pt.add_argument("value")
    pt.set_defaults(func=cmd_set)

    pg = sub.add_parser("global-override", help="set/clear the global override")
    pg.add_argument("key", help="min_priority | min_urgency | clear")
    pg.add_argument("value")
    pg.set_defaults(func=cmd_global_override)

    pr = sub.add_parser("trigger", help="frontmatter-style trigger props")
    pr.add_argument("name")
    pr.add_argument("prop", help="property name, or 'unset'")
    pr.add_argument("value", help="value (true/false/int parsed), or the prop to unset")
    pr.set_defaults(func=cmd_trigger)

    pe = sub.add_parser("test", help="dispatch a synthetic event")
    pe.add_argument("--priority", default="normal", choices=PRIORITY_LEVELS)
    pe.add_argument("--urgency", default="normal", choices=URGENCY_LEVELS)
    pe.add_argument("--source", default="settings-test")
    pe.set_defaults(func=cmd_test)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
