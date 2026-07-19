#!/usr/bin/env python3
"""
scripts/operator/lib/jobs_cli.py — the `sovereign-osctl jobs` CLI face.

The CLI + control-exec entry to the Background Tasks runtime (jobs-api :8142):
list / status / submit / cancel. `submit` and `cancel` are the actions the
cockpit routes through the sanctioned execute daemon (control-exec-api), so this
is the one place a Background Task is created or stopped. Stdlib only; loopback.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ADDR = os.environ.get("SOVEREIGN_JOBS_API_ADDR", "127.0.0.1:8142")


def _call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    # Forward the shared token when the operator has provisioned one — the
    # daemon's mutation_guard requires it for command-executing submits. No
    # token configured → header omitted → daemon relies on loopback+origin.
    _tok = os.environ.get("SOVEREIGN_OS_JOBS_TOKEN", "").strip()
    if _tok:
        headers["X-Sovereign-Jobs-Token"] = _tok
    req = urllib.request.Request(
        f"http://{ADDR}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (loopback)
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read().decode("utf-8", "replace")).get("error", f"HTTP {e.code}")}
        except (ValueError, OSError):
            return {"error": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"jobs-api unreachable at {ADDR}: {e}"}


def _print(obj: dict, as_json: bool) -> int:
    # An error RESPONSE has an `error` but no job `id`/`jobs`; a JOB has an `id`
    # and an (often empty) `error` field — don't conflate the two.
    is_error = bool(obj.get("error")) and "id" not in obj and "jobs" not in obj
    if as_json:
        print(json.dumps(obj, indent=2))
    elif is_error:
        print(f"error: {obj.get('error', 'unknown')}", file=sys.stderr)
    elif "jobs" in obj:
        s = obj.get("summary", {})
        print(f"{s.get('total', 0)} job(s) — {s.get('running', 0)} running, {s.get('queued', 0)} queued")
        for j in obj["jobs"][:40]:
            prio = j.get("priority", "normal")
            att = j.get("attempt", 1)
            tag = f"{prio[:4]:<4}" + (f" a{att}" if att > 1 else "   ")
            print(f"  {j['id']}  {j['state']:<9} {j['progress']:>3}%  {tag}  {j['kind']:<12} "
                  f"{j['device']:<12} {j['title']}")
    else:
        print(f"{obj.get('id', '?')}  {obj.get('state', '?')}  {obj.get('progress', 0)}%  "
              f"{obj.get('kind', '?')}  {obj.get('title', '')}")
        if obj.get("output"):
            print(f"  → {obj['output']}")
        if obj.get("error"):
            print(f"  ! {obj['error']}")
    return 1 if is_error else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sovereign-osctl jobs", description="Background Tasks runtime")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="list all jobs")
    sub.add_parser("plane", help="the compute plane — devices + live free VRAM + claims")
    p_status = sub.add_parser("status", help="one job's status")
    p_status.add_argument("id")
    p_cancel = sub.add_parser("cancel", help="cancel a job")
    p_cancel.add_argument("id")
    p_store = sub.add_parser("store", help="show or switch the registry backend (json|sqlite)")
    p_store.add_argument("backend", nargs="?", choices=["json", "sqlite"],
                         help="switch to this backend (migrate every job + persist the choice); "
                              "omit to show the active backend")
    p_sub = sub.add_parser("submit", help="submit a background job")
    p_sub.add_argument("kind", choices=["deliberation", "eval", "model-load", "gpu-job", "demo"])
    p_sub.add_argument("--title", default="")
    p_sub.add_argument("--device", default="cpu")
    p_sub.add_argument("--priority", choices=["high", "normal", "low"], default="normal",
                       help="scheduling priority (high runs before normal before low)")
    p_sub.add_argument("--timeout-secs", type=int, default=0,
                       help="wall-clock cap for a command job (0 = per-kind default)")
    p_sub.add_argument("--problem", default="")   # deliberation
    p_sub.add_argument("--rung", default="coat")
    p_sub.add_argument("--topic", type=int, default=15)
    p_sub.add_argument("--steps", type=int, default=5)  # demo

    # Everything after a literal `--` is the command to run (eval/model-load/
    # gpu-job). Split it off BEFORE argparse so its flags aren't mis-parsed.
    cmd_tail: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        cmd_tail = argv[i + 1:]
        argv = argv[:i]

    args = ap.parse_args(argv)
    cmd = args.cmd or "list"

    if cmd == "plane":
        d = _call("GET", "/plane.json")
        if args.json:
            print(json.dumps(d, indent=2))
            return 1 if d.get("error") else 0
        if d.get("error"):
            print(f"error: {d['error']}", file=sys.stderr)
            return 1
        s = d.get("summary", {})
        print(f"compute plane — {s.get('gpus', 0)} GPU(s) · {s.get('free_vram_gb', 0)}/"
              f"{s.get('total_vram_gb', 0)} GB free · {s.get('active_claims', 0)} claim(s)")
        for dev in d.get("devices", []):
            eff = dev.get("effective_free_gb")
            eff = "cpu" if eff is None else f"{eff:g}GB free"
            print(f"  {dev['key']:<6} {dev['role']:<9} {dev.get('name', ''):<28} {eff}")
        for c in d.get("claims", []):
            print(f"  claim {c['id']}  {c['vram_gb']:g}GB on {c['device']}  ({c['kind']}: {c.get('job', '')})")
        return 0
    if cmd == "store":
        # A local config op (not an HTTP runtime call): read or switch the
        # registry backend. Switching migrates every job + persists the choice;
        # the running daemon picks it up on its next restart.
        import jobs_store as _js
        active = _js.resolve_backend()
        if not args.backend:
            out = {"backend": active, "backends": list(_js.BACKENDS),
                   "persisted": _js.persisted_backend()}
            if args.json:
                print(json.dumps(out, indent=2))
            else:
                print(f"jobs registry backend: {active} "
                      f"(persisted: {out['persisted'] or '—'}; options: {'/'.join(_js.BACKENDS)})")
            return 0
        target = args.backend
        cur = _js.open_store()
        tgt = _js.SqliteStore() if target == "sqlite" else _js.JsonStore()
        migrated = _js.migrate(cur, tgt)
        _js.set_persisted_backend(target)
        out = {"switched_to": target, "from": active, "migrated": migrated,
               "note": "restart sovereign-jobs-api for the running daemon to use it"}
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"jobs registry backend: {active} → {target} — migrated {migrated} job(s); "
                  f"restart sovereign-jobs-api to apply")
        return 0
    if cmd == "list":
        return _print(_call("GET", "/jobs.json"), args.json)
    if cmd == "status":
        return _print(_call("GET", f"/jobs/{args.id}"), args.json)
    if cmd == "cancel":
        return _print(_call("POST", f"/jobs/{args.id}/cancel"), args.json)
    if cmd == "submit":
        meta: dict = {}
        if args.kind == "deliberation":
            meta = {"problem": args.problem or args.title, "rung": args.rung, "topic": args.topic}
        elif args.kind == "demo":
            meta = {"steps": args.steps}
        else:
            if not cmd_tail:
                print("error: this kind needs a command: … submit eval -- python3 scripts/…", file=sys.stderr)
                return 2
            meta = {"command": cmd_tail}
            if args.timeout_secs > 0:
                meta["timeout_secs"] = args.timeout_secs
        title = args.title or (args.problem if args.kind == "deliberation" else args.kind)
        return _print(_call("POST", "/jobs", {
            "kind": args.kind, "title": title, "device": args.device,
            "priority": args.priority, "meta": meta}), args.json)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
