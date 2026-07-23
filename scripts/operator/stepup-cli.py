#!/usr/bin/env python3
"""scripts/operator/stepup-cli.py — SDD-509 §5 manual CLI escape hatch.

The cockpit pane is the PRIMARY step-up surface; this is the terminal mirror for
a headless box or an operator who prefers the shell. It drives the SAME
`scripts/operator/lib/stepup.py` logic the exec daemon does — enroll a TOTP
factor + break-glass codes, verify a factor (mint an elevation so a pending
high-privilege cockpit op proceeds), read status, and curate per-control tiers.

No new dependency beyond the repo's YAML (already required). The step-up dir is
`$SOVEREIGN_OS_STEPUP_DIR` (default /run/sovereign-os/stepup) — the SAME store
the daemon reads, so a CLI verify elevates a cockpit action and vice-versa.

Verbs:
  status  [--json]                    enrollment + factors + recovery codes + tiers
  enroll  [--account NAME]            mint a TOTP secret + break-glass codes (shown ONCE)
  verify  --factor F --code C         verify a factor → mint a step-up elevation
  request-otp --factor sms|email     deliver an out-of-band code (needs notifykit)
  tier    --list                     show the curatable controls + effective tier
  tier    CONTROL_ID TIER            curate a control into none|operator-present|step-up
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _load_stepup():
    p = Path(__file__).resolve().parent / "lib" / "stepup.py"
    spec = importlib.util.spec_from_file_location("_stepup_cli_mod", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _stepup_dir() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_STEPUP_DIR", "/run/sovereign-os/stepup"))


def _notify_config() -> Path:
    return Path(os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", _REPO / "config" / "notifykit.toml"))


def _controls() -> list[dict]:
    """The control registry (id + fields) for tier resolution — read straight
    from config/control-systems.yaml so the CLI needs no daemon."""
    try:
        import yaml
        data = yaml.safe_load((_REPO / "config" / "control-systems.yaml").read_text())
        return [{"id": s.get("id"), **s} for s in data.get("systems", []) if s.get("id")]
    except Exception:
        return []


def _cmd_status(su, args) -> int:
    st = su.status(_stepup_dir(), _notify_config(), controls=_controls())
    if args.json:
        print(json.dumps(st, indent=2))
        return 0
    print(f"enrolled:            {'yes' if st['enrolled'] else 'no'}")
    print(f"factors:             {', '.join(st['factors']) or '(none)'}")
    print(f"recovery codes left: {st['break_glass_remaining']}")
    print(f"elevation window:    {st['elevation_window_seconds']}s")
    print(f"step-up controls:    {', '.join(st['step_up_controls']) or '(none)'}")
    return 0


def _cmd_enroll(su, args) -> int:
    d = _stepup_dir()
    if su.is_enrolled(d):
        print("already enrolled — re-enrolling from the CLI would rotate your secret.\n"
              "Re-enroll from the pane (it gates on a live elevation) or clear the\n"
              f"step-up dir ({d}) deliberately first.", file=sys.stderr)
        return 2
    secret, uri = su.enroll(d, args.account)
    codes = su.generate_break_glass(d)
    print("== SHOWN ONCE — save these now ==")
    print(f"TOTP secret (enter in your authenticator): {secret}")
    print(f"otpauth URI: {uri}")
    print("recovery codes (each single-use, for a lost phone):")
    for c in codes:
        print(f"  {c}")
    return 0


def _cmd_verify(su, args) -> int:
    res = su.verify_factor_and_elevate(
        _stepup_dir(), _notify_config(), "operator-cli", args.factor, args.code)
    if res is None:
        print(f"factor {args.factor!r} is not set up", file=sys.stderr)
        return 2
    if not res:
        print("invalid code — not elevated", file=sys.stderr)
        return 1
    print("verified — step-up elevation minted (your pending high-privilege op may proceed)")
    return 0


def _cmd_request_otp(su, args) -> int:
    ok, detail = su.request_otp_and_deliver(
        _stepup_dir(), _notify_config(), "operator-cli", args.factor)
    print(detail)
    return 0 if ok else 1


def _cmd_tier(su, args) -> int:
    d = _stepup_dir()
    if args.list or not args.control_id:
        st = su.status(d, _notify_config(), controls=_controls())
        for c in st["curatable_controls"]:
            mark = " (overridden)" if c["overridden"] else ""
            print(f"{c['id']:<24} {c['tier']}{mark}")
        return 0
    if not args.tier:
        print("tier CONTROL_ID TIER  (tier: none|operator-present|step-up)", file=sys.stderr)
        return 2
    if args.control_id in ("selfdef", "perimeter"):
        print(f"{args.control_id} is proxy-only and not curatable", file=sys.stderr)
        return 2
    if not su.set_tier_override(d, args.control_id, args.tier):
        print("tier must be none|operator-present|step-up", file=sys.stderr)
        return 2
    print(f"{args.control_id} → {args.tier}")
    return 0


def main(argv: list[str] | None = None) -> int:
    su = _load_stepup()
    ap = argparse.ArgumentParser(prog="sovereign-osctl stepup",
                                 description="Step-up MFA — the manual CLI escape hatch (SDD-509 §5).")
    sub = ap.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("status", help="enrollment + factors + recovery codes + tiers")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_cmd_status)

    p = sub.add_parser("enroll", help="mint a TOTP secret + break-glass codes (shown once)")
    p.add_argument("--account", default="operator@sain-01")
    p.set_defaults(fn=_cmd_enroll)

    p = sub.add_parser("verify", help="verify a factor → mint a step-up elevation")
    p.add_argument("--factor", required=True, choices=["totp", "sms", "email", "breakglass"])
    p.add_argument("--code", required=True)
    p.set_defaults(fn=_cmd_verify)

    p = sub.add_parser("request-otp", help="deliver an out-of-band code (needs notifykit)")
    p.add_argument("--factor", required=True, choices=["sms", "email"])
    p.set_defaults(fn=_cmd_request_otp)

    p = sub.add_parser("tier", help="show or curate per-control step-up tiers")
    p.add_argument("control_id", nargs="?")
    p.add_argument("tier", nargs="?")
    p.add_argument("--list", action="store_true")
    p.set_defaults(fn=_cmd_tier)

    args = ap.parse_args(argv)
    return args.fn(su, args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
