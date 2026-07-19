#!/usr/bin/env python3
"""scripts/notify/dispatch.py — R228 (SDD-026 Z-6 notification fan-out).

Operator-named (verbatim, from the 2026-05-17 expansion): "With scans
too. with autohealth and doctor and analysis and event and
notification and messaging."

R226 (health-scan.py) ships the SCAN — composite read-only autohealth
across every Z-vector card. R228 ships the FAN-OUT — read the scan's
--json output, derive event transitions, deliver to operator-configured
channels (file / webhook / ntfy).

Channels (all stdlib — no third-party deps):

  file      Append a JSONL event to a path. Always-on local audit
            trail. Default: /var/log/sovereign-os/notify.jsonl.
            This is the ONLY channel enabled by default — every other
            channel requires operator opt-in via config.

  webhook   HTTP POST a JSON body to an operator-supplied URL.
            URL comes from an env-var reference in the config
            (operator keys NEVER in-repo per SDD-009).

  ntfy      HTTP POST to an ntfy.sh-compatible server. URL + topic
            come from env-var references in the config. Severity is
            translated to ntfy "Priority" header so push notifications
            ring correctly on the operator's phone.

Dedup contract: the dispatcher tracks the last-seen severity per probe
in a state file (default /var/lib/sovereign-os/notify-state.json).
Channels fire only when a probe TRANSITIONS to a worse severity OR
when the probe appears for the first time. A probe that stays at
"attention" run-after-run does NOT spam the operator.

CLI:
  dispatch.py dispatch [--from-file PATH] [--dry-run] [--json]
              Read R226 health-scan --json (from --from-file or by
              shelling out), apply dedup, fan to all enabled channels.

  dispatch.py test --channel C [--severity S]
              Send a synthetic event through ONE channel. Used by
              `sovereign-osctl notify test`.

  dispatch.py list-channels [--json]
              Show every channel + its enabled/disabled state.

  dispatch.py state [--json]
              Dump the dedup state file.

Exit codes:
  0  dispatch succeeded (or was a no-op, e.g. nothing transitioned)
  1  at least one channel failed to deliver
  2  usage error / config error

Environment variables (test + operator):
  SOVEREIGN_OS_NOTIFY_CONFIG   override /etc/sovereign-os/notify.toml path
  SOVEREIGN_OS_NOTIFY_STATE    override dedup state file path
  SOVEREIGN_OS_DRY_RUN         set to anything to force --dry-run mode
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/notify.toml")
DEV_CONFIG = REPO_ROOT / "config" / "notify.toml.example"
DEFAULT_STATE = Path("/var/lib/sovereign-os/notify-state.json")
DEFAULT_FILE_SINK = Path("/var/log/sovereign-os/notify.jsonl")

SEVERITY_ORDER = {"informational": 0, "ok": 1, "attention": 2, "down": 3}


# ----------------------------------------------------------------- config


def resolve_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("SOVEREIGN_OS_NOTIFY_CONFIG")
    if env:
        return Path(env)
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(path: Path | None) -> dict[str, Any]:
    """Returns config dict. Missing path = file-channel-only defaults."""
    if path is None or not path.exists():
        return {
            "channels": {
                "file": {
                    "enabled": True,
                    "path": str(DEFAULT_FILE_SINK),
                }
            },
            "_source": "(defaults — no config file present)",
        }
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    if "channels" not in doc:
        doc["channels"] = {}
    doc["_source"] = str(path)
    return doc


def env_ref(value: Any) -> str | None:
    """Resolve a string that may be a literal or an env-var reference.

    Operator keys NEVER live in-repo. The config carries env-var REFs:
        url = "env:SOVEREIGN_OS_NOTIFY_WEBHOOK_URL"
    and the dispatcher looks the actual URL up at delivery time.
    """
    if not isinstance(value, str):
        return None
    if value.startswith("env:"):
        return os.environ.get(value[4:])
    return value


# ----------------------------------------------------------------- state


def resolve_state_path() -> Path:
    env = os.environ.get("SOVEREIGN_OS_NOTIFY_STATE")
    if env:
        return Path(env)
    return DEFAULT_STATE


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "probes": {}}
    try:
        with path.open() as fh:
            d = json.load(fh)
        if "probes" not in d:
            d["probes"] = {}
        return d
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "probes": {}}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(state, fh, indent=2)
    tmp.replace(path)


# ------------------------------------------------------------- health-scan


def fetch_health_scan(from_file: Path | None) -> dict[str, Any]:
    """Returns parsed R226 health-scan --json output."""
    if from_file is not None:
        with from_file.open() as fh:
            return json.load(fh)
    bin_path = REPO_ROOT / "scripts" / "hardware" / "health-scan.py"
    if not bin_path.exists():
        raise RuntimeError(f"{bin_path} missing — R226 health-scan unavailable")
    r = subprocess.run(
        [sys.executable, str(bin_path), "--json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    # rc=0 healthy, rc=1 attention — both yield valid JSON.
    if r.returncode not in (0, 1):
        raise RuntimeError(
            f"health-scan failed rc={r.returncode}: {r.stderr.strip()}"
        )
    return json.loads(r.stdout)


# ----------------------------------------------------------------- dedup


def derive_events(
    scan: dict[str, Any], state: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return events for probes that TRANSITIONED to a worse severity.

    An event is emitted when:
      * probe is new (no prior state), OR
      * probe severity rose (e.g. ok -> attention, attention -> down).

    Probes that stayed at the same severity OR recovered are NOT
    fired. (Recovery events anchored to a future round — anti-min-waiver: R480 recovery-event-emission-arc-Stage-2-SDD-023-extension — for now silence is
    "still bad, no new news.")
    """
    events: list[dict[str, Any]] = []
    prior = state.get("probes", {})
    for probe in scan.get("probes", []):
        pid = probe.get("probe")
        if not pid:
            continue
        cur_sev = probe.get("severity", "informational")
        cur_rank = SEVERITY_ORDER.get(cur_sev, -1)
        prior_sev = prior.get(pid, {}).get("severity")
        prior_rank = (
            SEVERITY_ORDER.get(prior_sev, -2) if prior_sev is not None else -2
        )
        is_new = prior_sev is None
        rose = cur_rank > prior_rank
        actionable = cur_sev in {"attention", "down"}
        if actionable and (is_new or rose):
            events.append(
                {
                    "probe": pid,
                    "severity": cur_sev,
                    "round": probe.get("round"),
                    "vector": probe.get("vector"),
                    "detail": probe.get("detail"),
                    "flagged_items": probe.get("flagged_items", []),
                    "transition": "new" if is_new else f"{prior_sev}->{cur_sev}",
                    "emitted_at": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                    ),
                }
            )
    return events


def update_state(
    state: dict[str, Any], scan: dict[str, Any]
) -> dict[str, Any]:
    probes = state.setdefault("probes", {})
    for probe in scan.get("probes", []):
        pid = probe.get("probe")
        if not pid:
            continue
        probes[pid] = {
            "severity": probe.get("severity"),
            "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    state["last_dispatch"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return state


# ----------------------------------------------------------------- channels


def deliver_file(
    cfg: dict[str, Any], events: list[dict[str, Any]], dry_run: bool
) -> tuple[bool, str]:
    sink = Path(cfg.get("path") or str(DEFAULT_FILE_SINK))
    if dry_run:
        return (True, f"would append {len(events)} event(s) to {sink}")
    try:
        sink.parent.mkdir(parents=True, exist_ok=True)
        with sink.open("a") as fh:
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
        return (True, f"appended {len(events)} event(s) to {sink}")
    except OSError as e:
        return (False, f"file sink {sink}: {e}")


def deliver_webhook(
    cfg: dict[str, Any], events: list[dict[str, Any]], dry_run: bool
) -> tuple[bool, str]:
    url = env_ref(cfg.get("url"))
    if not url:
        return (False, "webhook url unresolved (env-var missing?)")
    if dry_run:
        return (True, f"would POST {len(events)} event(s) to {url}")
    body = json.dumps({"events": events}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            code = resp.status
        if 200 <= code < 300:
            return (True, f"POST {url} -> {code} ({len(events)} event(s))")
        return (False, f"POST {url} -> {code}")
    except (urllib.error.URLError, OSError) as e:
        return (False, f"POST {url} failed: {e}")


def deliver_ntfy(
    cfg: dict[str, Any], events: list[dict[str, Any]], dry_run: bool
) -> tuple[bool, str]:
    base = env_ref(cfg.get("base_url")) or "https://ntfy.sh"
    topic = env_ref(cfg.get("topic"))
    if not topic:
        return (False, "ntfy topic unresolved (env-var missing?)")
    url = f"{base.rstrip('/')}/{topic}"
    if dry_run:
        return (True, f"would POST {len(events)} event(s) to {url}")
    ok = 0
    failed = 0
    for ev in events:
        priority = "5" if ev.get("severity") == "down" else "4"
        title = f"sovereign-os {ev.get('probe')} {ev.get('severity')}"
        body = f"{ev.get('detail') or ''}".encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "warning,sovereign-os",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                if 200 <= resp.status < 300:
                    ok += 1
                else:
                    failed += 1
        except (urllib.error.URLError, OSError):
            failed += 1
    msg = f"ntfy {url}: {ok} delivered, {failed} failed"
    return (failed == 0, msg)


CHANNEL_DELIVERERS = {
    "file": deliver_file,
    "webhook": deliver_webhook,
    "ntfy": deliver_ntfy,
}


# ------------------------------------------------- notifykit bridge (2026-07-19)
#
# The shared notification library (tools/notifykit — the 2026-07-19
# standing directive's "new shared library" decision) becomes reachable
# from the R228 health fan-out ADDITIVELY: the three legacy channels
# above stay byte-identical (their contract is pinned by
# tests/nspawn/test_notify_dispatch.sh); when a notifykit config exists
# ($SOVEREIGN_OS_NOTIFYKIT_CONFIG, default /etc/sovereign-os/
# notifykit.toml), every derived event ALSO dispatches through the
# library's gated channels — which is how health transitions reach
# Resend email + Twilio SMS under the operator's verbatim gates (SMS
# needs priority>=high AND urgency>=high; no-SMS Resend starts at
# high/urgent), the global override + static pins, and the
# `r228-health` trigger's frontmatter props.
#
# Severity -> the two axes (mirrors the legacy ntfy mapping 4/5):
#   attention -> priority high, urgency high
#   down      -> priority max,  urgency urgent
SEVERITY_AXES = {
    "attention": ("high", "high"),
    "down": ("max", "urgent"),
}


def notifykit_config_path() -> Path:
    return Path(os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", "/etc/sovereign-os/notifykit.toml"))


def deliver_notifykit_bridge(
    events: list[dict[str, Any]], dry_run: bool
) -> tuple[bool, str] | None:
    """Dispatch events through the notifykit registry. Returns None when
    the bridge is inactive (no config file) — the legacy contract then
    holds exactly. Never raises: the health dispatch must not die on a
    notification-library problem."""
    cfg_path = notifykit_config_path()
    if not cfg_path.is_file():
        return None
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from tools.notifykit import ChannelRegistry, Event, NotifyConfig
        registry = ChannelRegistry(NotifyConfig.load(cfg_path))
        if dry_run:
            enabled = [n for n, c in registry.config.channels.items()
                       if c.enabled]
            return (True, f"would dispatch {len(events)} event(s) through "
                          f"notifykit channels {enabled or '(none enabled)'}")
        sent = gated = failed = 0
        for ev in events:
            prio, urg = SEVERITY_AXES.get(
                str(ev.get("severity")), ("normal", "normal"))
            receipts = registry.dispatch(Event(
                title=f"sovereign-os {ev.get('probe')} {ev.get('severity')}",
                message=(f"{ev.get('detail') or ''} "
                         f"(transition={ev.get('transition')})").strip(),
                priority=prio, urgency=urg,
                tags=["warning", "sovereign-os"],
                source="r228-health",
            ))
            for r in receipts:
                if r.skipped:
                    gated += 1
                elif r.ok:
                    sent += 1
                else:
                    failed += 1
        msg = (f"notifykit: {sent} delivered, {gated} gated/disabled, "
               f"{failed} failed ({cfg_path})")
        return (failed == 0, msg)
    except Exception as e:
        return (False, f"notifykit bridge error: {e}")


def enabled_channels(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return [(name, channel_cfg)] for channels with enabled=true."""
    out: list[tuple[str, dict[str, Any]]] = []
    for name, cfg in (config.get("channels") or {}).items():
        if not isinstance(cfg, dict):
            continue
        if cfg.get("enabled") is True:
            out.append((name, cfg))
    return out


# ----------------------------------------------------------------- verbs


def cmd_dispatch(args: argparse.Namespace) -> int:
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    state_path = resolve_state_path()
    state = load_state(state_path)
    try:
        scan = fetch_health_scan(args.from_file)
    except (RuntimeError, json.JSONDecodeError, OSError) as e:
        print(f"ERROR fetching health-scan: {e}", file=sys.stderr)
        return 2

    events = derive_events(scan, state)
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    deliveries: list[dict[str, Any]] = []
    any_failed = False
    if events:
        for name, ch_cfg in enabled_channels(config):
            fn = CHANNEL_DELIVERERS.get(name)
            if fn is None:
                deliveries.append(
                    {"channel": name, "ok": False, "detail": "no deliverer"}
                )
                any_failed = True
                continue
            ok, detail = fn(ch_cfg, events, dry_run=bool(dry))
            deliveries.append({"channel": name, "ok": ok, "detail": detail})
            if not ok:
                any_failed = True
        # 2026-07-19 additive bridge: events ALSO flow through the shared
        # notifykit stack when its config exists (None = inactive; the
        # legacy contract — incl. deliveries==[] with 0 events — holds).
        bridge = deliver_notifykit_bridge(events, dry_run=bool(dry))
        if bridge is not None:
            b_ok, b_detail = bridge
            deliveries.append(
                {"channel": "notifykit-bridge", "ok": b_ok, "detail": b_detail})
            if not b_ok:
                any_failed = True

    # Always update state (even on dry-run? No — only on real runs).
    if not dry and events:
        update_state(state, scan)
        save_state(state_path, state)

    report = {
        "round": "R228",
        "vector": "SDD-026 Z-6 (notification fan-out)",
        "config_source": config.get("_source"),
        "state_path": str(state_path),
        "dry_run": bool(dry),
        "events_emitted": len(events),
        "events": events,
        "deliveries": deliveries,
        "scan_summary": scan.get("summary"),
        "scan_needs_attention": scan.get("needs_attention"),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_dispatch_human(report)
    return 1 if any_failed else 0


def print_dispatch_human(r: dict[str, Any]) -> None:
    print("── R228 / SDD-026 Z-6 notify dispatch ──")
    print(f"  config:    {r.get('config_source')}")
    print(f"  state:     {r.get('state_path')}")
    print(f"  dry-run:   {r.get('dry_run')}")
    print(f"  events:    {r.get('events_emitted')} emitted")
    if r.get("scan_summary"):
        s = r["scan_summary"]
        print(
            f"  scan:      ok={s.get('ok')} attention={s.get('attention')} "
            f"informational={s.get('informational')} total={s.get('total')}"
        )
    for ev in r.get("events", []) or []:
        print(f"    [{ev['severity']:11s}] {ev['probe']:10s} {ev['detail']}")
        print(f"                  transition={ev['transition']}")
    if r.get("deliveries"):
        print("  deliveries:")
        for d in r["deliveries"]:
            mark = "OK " if d["ok"] else "FAIL"
            print(f"    {mark} {d['channel']:8s} {d['detail']}")


def cmd_test(args: argparse.Namespace) -> int:
    # 2026-07-19: `test --channel notifykit` exercises the ADDITIVE bridge
    # (synthetic event through the shared library's gated channels).
    if args.channel == "notifykit":
        synth = [{
            "probe": "synthetic", "severity": args.severity,
            "detail": "test event from `sovereign-osctl notify test`",
            "transition": "test",
        }]
        dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
        bridge = deliver_notifykit_bridge(synth, dry_run=bool(dry))
        if bridge is None:
            print(f"channel=notifykit ok=False detail=bridge inactive — "
                  f"no config at {notifykit_config_path()}")
            return 2
        b_ok, b_detail = bridge
        print(f"channel=notifykit ok={b_ok} detail={b_detail}")
        return 0 if b_ok else 1

    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    ch_cfg = (config.get("channels") or {}).get(args.channel)
    if ch_cfg is None:
        print(
            f"ERROR channel '{args.channel}' not configured "
            f"(known: {sorted((config.get('channels') or {}).keys())})",
            file=sys.stderr,
        )
        return 2
    fn = CHANNEL_DELIVERERS.get(args.channel)
    if fn is None:
        print(
            f"ERROR no deliverer for channel '{args.channel}' "
            f"(known: {sorted(CHANNEL_DELIVERERS.keys())} + 'notifykit' "
            f"via `test --channel notifykit`)",
            file=sys.stderr,
        )
        return 2
    synth = [
        {
            "probe": "synthetic",
            "severity": args.severity,
            "round": "R228",
            "vector": "SDD-026 Z-6 test event",
            "detail": "test event from `sovereign-osctl notify test`",
            "flagged_items": [],
            "transition": "test",
            "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    ]
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    ok, detail = fn(ch_cfg, synth, dry_run=bool(dry))
    print(f"channel={args.channel} ok={ok} detail={detail}")
    return 0 if ok else 1


def cmd_list_channels(args: argparse.Namespace) -> int:
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    channels = []
    for name, ch_cfg in (config.get("channels") or {}).items():
        channels.append(
            {
                "name": name,
                "enabled": bool(isinstance(ch_cfg, dict) and ch_cfg.get("enabled")),
                "has_deliverer": name in CHANNEL_DELIVERERS,
            }
        )
    # Always include the built-in deliverers even if absent from config.
    declared = {c["name"] for c in channels}
    for builtin in CHANNEL_DELIVERERS:
        if builtin not in declared:
            channels.append(
                {"name": builtin, "enabled": False, "has_deliverer": True}
            )
    nk_path = notifykit_config_path()
    out = {
        "round": "R228",
        "vector": "SDD-026 Z-6",
        "config_source": config.get("_source"),
        "channels": sorted(channels, key=lambda c: c["name"]),
        # 2026-07-19 additive bridge status — a SEPARATE key so the
        # legacy `channels` contract stays byte-stable.
        "notifykit_bridge": {
            "active": nk_path.is_file(),
            "config": str(nk_path),
        },
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R228 notify channels (config: {out['config_source']}) ──")
        for c in out["channels"]:
            mark = "[on] " if c["enabled"] else "[off]"
            shipped = "shipped" if c["has_deliverer"] else "(no deliverer)"
            print(f"  {mark} {c['name']:10s} {shipped}")
        b = out["notifykit_bridge"]
        print(f"  [{'on' if b['active'] else 'off'}]  notifykit-bridge "
              f"(shared library — resend/twilio/gates; config {b['config']})")
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    state_path = resolve_state_path()
    state = load_state(state_path)
    out = {
        "round": "R228",
        "state_path": str(state_path),
        "exists": state_path.exists(),
        "state": state,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("── R228 notify dedup state ──")
        print(f"  path:   {state_path}")
        print(f"  exists: {state_path.exists()}")
        for pid, info in (state.get("probes") or {}).items():
            print(
                f"    {pid:10s} severity={info.get('severity'):12s} "
                f"last_seen={info.get('last_seen')}"
            )
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    """Fan an ARBITRARY operator message to ALL enabled channels (no dedup,
    no health-scan). This is the ad-hoc push path used by the graceful-shutdown
    warnings, the battery-escalation ladder, and the apc-default-profile — each
    of which composes `sovereign-osctl notify send --severity S --message '…'`.
    Unlike `dispatch` (transition-gated), every `send` delivers immediately."""
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    event = {
        "probe": args.probe,
        "severity": args.severity,
        "round": "R228",
        "vector": "manual send",
        "detail": args.message,
        "title": args.title or f"sovereign-os {args.severity}",
        "flagged_items": [],
        "transition": "manual",
        "emitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    channels = enabled_channels(config)
    if not channels:  # file sink is always-on even with a minimal/absent config
        channels = [("file", {"enabled": True, "path": str(DEFAULT_FILE_SINK)})]
    deliveries: list[dict[str, Any]] = []
    any_failed = False
    for name, ch_cfg in channels:
        fn = CHANNEL_DELIVERERS.get(name)
        if fn is None:
            deliveries.append({"channel": name, "ok": False, "detail": "no deliverer"})
            any_failed = True
            continue
        ok, detail = fn(ch_cfg, [event], dry_run=bool(dry))
        deliveries.append({"channel": name, "ok": ok, "detail": detail})
        if not ok:
            any_failed = True
    report = {
        "round": "R228",
        "vector": "SDD-026 Z-6 (manual send)",
        "config_source": config.get("_source"),
        "dry_run": bool(dry),
        "severity": args.severity,
        "message": args.message,
        "deliveries": deliveries,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"── R228 notify send (severity={args.severity}, dry_run={bool(dry)}) ──")
        print(f"  message: {args.message}")
        for d in deliveries:
            mark = "OK " if d["ok"] else "FAIL"
            print(f"    {mark} {d['channel']:8s} {d['detail']}")
    return 1 if any_failed else 0


# ----------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dispatch.py",
        description="R228 (SDD-026 Z-6) notification fan-out for R226 health-scan.",
    )
    p.add_argument(
        "--config", type=Path, default=None, help="override config file path"
    )
    sub = p.add_subparsers(dest="verb", required=True)

    pd = sub.add_parser("dispatch", help="read health-scan + fan to channels")
    pd.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="read scan JSON from path instead of shelling out",
    )
    pd.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would fire without delivering or updating state",
    )
    pd.add_argument("--json", action="store_true")
    pd.set_defaults(func=cmd_dispatch)

    pt = sub.add_parser("test", help="send a synthetic event through one channel")
    pt.add_argument(
        "--channel",
        required=True,
        choices=sorted(CHANNEL_DELIVERERS) + ["notifykit"],
    )
    pt.add_argument(
        "--severity",
        default="attention",
        choices=sorted(SEVERITY_ORDER),
    )
    pt.add_argument("--dry-run", action="store_true")
    pt.set_defaults(func=cmd_test)

    pl = sub.add_parser("list-channels", help="show configured channels")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list_channels)

    ps = sub.add_parser("state", help="dump dedup state")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_state)

    pse = sub.add_parser(
        "send", help="fan an arbitrary message to all enabled channels (no dedup)"
    )
    pse.add_argument("--message", required=True, help="the message body to deliver")
    pse.add_argument(
        "--severity", default="attention", choices=sorted(SEVERITY_ORDER),
        help="severity (maps to ntfy priority; default attention)",
    )
    pse.add_argument("--title", default=None, help="optional title/subject line")
    pse.add_argument("--probe", default="manual", help="source label (default: manual)")
    pse.add_argument("--dry-run", action="store_true")
    pse.add_argument("--json", action="store_true")
    pse.set_defaults(func=cmd_send)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
