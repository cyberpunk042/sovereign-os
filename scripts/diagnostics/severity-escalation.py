#!/usr/bin/env python3
"""scripts/diagnostics/severity-escalation.py — R273 (E6.M6).

Operator-named (verbatim): "autohealth and doctor and analysis and
event and notification and messaging" — without an escalation policy,
"attention" findings live forever at attention and never tip into
"critical" no matter how long they've been ignored. R273 closes
E6.M6: a state-file-backed escalation engine that bumps lingering
attention findings to critical after operator-configurable dwell-time.

Logic:
  - Read R266 diagnose run --json (the cross-axis synthesizer output).
  - For each finding at severity ∈ {attention, critical}, hash a stable
    identity key (source + module + title).
  - Compare against state file /var/lib/sovereign-os/severity-state.json
    (env override: SOVEREIGN_OS_SEVERITY_STATE).
  - For findings present in prior state at the same severity:
      duration = now - first_seen
      If attention AND duration ≥ escalate_after_seconds → bump to critical.
  - For findings NEW vs prior state: record first_seen = now.
  - Write new state atomically (tempfile → rename).

CLI:
  severity-escalation.py evaluate [--escalate-after-seconds N] [--json]
                                          fold prior state into a new
                                          escalated finding set
  severity-escalation.py state [--json]    dump current state file
  severity-escalation.py reset             clear state (operator-confirm)

Exit codes:
  0  evaluated; no escalations
  1  ≥1 finding escalated this run
  2  usage error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = Path("/var/lib/sovereign-os/severity-state.json")
DEFAULT_ESCALATE_AFTER_SECONDS = 4 * 3600  # 4 hours


def resolve_state_path() -> Path:
    env = os.environ.get("SOVEREIGN_OS_SEVERITY_STATE")
    if env:
        return Path(env)
    return DEFAULT_STATE


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "findings": {}, "last_eval_at": None}
    try:
        with path.open() as fh:
            d = json.load(fh)
        if "findings" not in d:
            d["findings"] = {}
        return d
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "findings": {}, "last_eval_at": None}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(state, fh, indent=2)
    tmp.replace(path)


def finding_identity(f: dict[str, Any]) -> str:
    """Stable hash key for a finding. Uses source + module + title so
    that re-running diagnose on a refreshed host emits the SAME key
    for the SAME issue."""
    parts = "|".join([
        str(f.get("source", "")),
        str(f.get("module", "")),
        str(f.get("title", "")),
    ])
    return hashlib.sha256(parts.encode()).hexdigest()[:16]


def call_diagnose() -> dict[str, Any]:
    """Invoke R266 diagnose run --json + return parsed payload.
    Empty dict on failure (defense-in-depth)."""
    bin_path = REPO_ROOT / "scripts" / "diagnostics" / "doctor.py"
    if not bin_path.exists():
        return {}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "run", "--all", "--json"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if r.returncode not in (0, 1):
        return {}
    try:
        return json.loads(r.stdout) or {}
    except json.JSONDecodeError:
        return {}


def evaluate(escalate_after_seconds: int, source_findings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Returns the escalation report. If source_findings is None,
    calls R266 diagnose to fetch them."""
    state_path = resolve_state_path()
    state = load_state(state_path)
    prior = state.get("findings") or {}
    now = time.time()
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

    if source_findings is None:
        diag = call_diagnose()
        source_findings = (diag or {}).get("findings") or []

    new_state_findings: dict[str, Any] = {}
    output_findings: list[dict[str, Any]] = []
    escalated_count = 0
    new_count = 0

    for f in source_findings:
        if f.get("severity") not in {"attention", "critical"}:
            continue
        key = finding_identity(f)
        prior_entry = prior.get(key)
        if prior_entry and prior_entry.get("severity") == f.get("severity"):
            # Same finding still active; carry first_seen.
            first_seen = prior_entry.get("first_seen", now)
            duration_s = now - first_seen
            escalated = False
            effective_severity = f["severity"]
            if (
                f["severity"] == "attention"
                and duration_s >= escalate_after_seconds
            ):
                effective_severity = "critical"
                escalated = True
                escalated_count += 1
            new_state_findings[key] = {
                "first_seen": first_seen,
                "first_seen_iso": prior_entry.get("first_seen_iso") or now_iso,
                "severity": f.get("severity"),  # record OBSERVED severity
                "title": f.get("title"),
                "source": f.get("source"),
                "module": f.get("module"),
            }
            output_findings.append({
                **f,
                "identity_key": key,
                "first_seen_iso": prior_entry.get("first_seen_iso") or now_iso,
                "duration_s": round(duration_s),
                "duration_hours": round(duration_s / 3600.0, 2),
                "observed_severity": f["severity"],
                "effective_severity": effective_severity,
                "escalated": escalated,
            })
        else:
            # New finding (or severity changed) — reset first_seen.
            new_state_findings[key] = {
                "first_seen": now,
                "first_seen_iso": now_iso,
                "severity": f.get("severity"),
                "title": f.get("title"),
                "source": f.get("source"),
                "module": f.get("module"),
            }
            output_findings.append({
                **f,
                "identity_key": key,
                "first_seen_iso": now_iso,
                "duration_s": 0,
                "duration_hours": 0.0,
                "observed_severity": f["severity"],
                "effective_severity": f["severity"],
                "escalated": False,
            })
            new_count += 1

    new_state = {
        "version": 1,
        "last_eval_at": now_iso,
        "escalate_after_seconds": escalate_after_seconds,
        "findings": new_state_findings,
    }
    save_state(state_path, new_state)

    return {
        "round": "R273",
        "vector": "E6.M6 (severity-escalation)",
        "evaluated_at": now_iso,
        "state_path": str(state_path),
        "escalate_after_seconds": escalate_after_seconds,
        "escalate_after_hours": round(escalate_after_seconds / 3600.0, 2),
        "input_finding_count": len(source_findings),
        "tracked_finding_count": len(new_state_findings),
        "new_count": new_count,
        "escalated_count": escalated_count,
        "findings": output_findings,
    }


def cmd_evaluate(args: argparse.Namespace) -> int:
    report = evaluate(args.escalate_after_seconds)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"── R273 sovereign-os severity-escalation evaluate (E6.M6) ──")
        print(f"  evaluated_at:           {report['evaluated_at']}")
        print(f"  escalate_after_hours:   {report['escalate_after_hours']}")
        print(f"  input findings:         {report['input_finding_count']}")
        print(f"  tracked findings:       {report['tracked_finding_count']}")
        print(f"  new this run:           {report['new_count']}")
        print(f"  escalated this run:     {report['escalated_count']}")
        for f in report["findings"]:
            mark = "↑" if f["escalated"] else " "
            print(f"\n  {mark} [{f['effective_severity']:9s}] {f['title']}")
            print(f"      first_seen: {f['first_seen_iso']}  (age: {f['duration_hours']}h)")
            print(f"      identity:   {f['identity_key']}  ({f.get('source')}/{f.get('module','?')})")
    return 1 if report["escalated_count"] > 0 else 0


def cmd_state(args: argparse.Namespace) -> int:
    path = resolve_state_path()
    state = load_state(path)
    out = {
        "round": "R273",
        "vector": "E6.M6 (severity-escalation-state)",
        "state_path": str(path),
        "exists": path.exists(),
        "state": state,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R273 sovereign-os severity-escalation state (E6.M6) ──")
    print(f"  path:           {path}")
    print(f"  exists:         {path.exists()}")
    print(f"  last_eval_at:   {state.get('last_eval_at')}")
    findings = state.get("findings") or {}
    print(f"  tracked count:  {len(findings)}")
    for k, v in findings.items():
        print(f"\n  {k}  {v.get('severity')}  first_seen={v.get('first_seen_iso')}")
        print(f"      {v.get('source')}/{v.get('module')}  {v.get('title')}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    path = resolve_state_path()
    if not args.confirm and os.environ.get("SOVEREIGN_OS_CONFIRM_DESTROY") != "YES":
        print(
            "ERROR `reset` clears the escalation state file. Add --confirm "
            "OR set SOVEREIGN_OS_CONFIRM_DESTROY=YES.",
            file=sys.stderr,
        )
        return 2
    if path.exists():
        path.unlink()
    out = {
        "round": "R273",
        "vector": "E6.M6 (severity-escalation-reset)",
        "state_path": str(path),
        "removed": True,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R273 severity-escalation reset ──")
        print(f"  cleared: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="severity-escalation.py",
        description="R273 (E6.M6) — escalation engine: attention → critical after dwell-time.",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    pe = sub.add_parser("evaluate", help="fold prior state into new escalated findings")
    pe.add_argument("--escalate-after-seconds", type=int, default=DEFAULT_ESCALATE_AFTER_SECONDS)
    pe.add_argument("--json", action="store_true")
    pe.set_defaults(func=cmd_evaluate)

    ps = sub.add_parser("state", help="dump current state file")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_state)

    pr = sub.add_parser("reset", help="clear state (operator-confirm)")
    pr.add_argument("--confirm", action="store_true")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_reset)

    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
