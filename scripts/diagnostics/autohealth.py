#!/usr/bin/env python3
"""scripts/diagnostics/autohealth.py — R308 (E2.M14).

Operator-named (§1b mandate row, verbatim): "autohealth and doctor ,
notification and messaging". Closes E2.M14.

R266 (doctor) ships one-shot multi-axis health probe. R308 adds the
PERIODIC autohealth layer: a tick-driven synthesizer that runs the
cross-axis rollups shipped in recent rounds, persists findings to a
JSONL state file, and emits notify-dispatch COMMANDS the operator
runs (or a confirmed automation pipes) when severity crosses
threshold + suppression window has elapsed.

The 5 rollups composed:
  R226 health-scan          → raw multi-probe
  R296 thermal-oc-budget    → thermal × OC combined
  R298 storage-health       → log+raid+partition+journal
  R300 operator-posture     → 5-axis worst-axis rollup
  R304 mem-pressure-damper  → memory → OC dampening

NEVER auto-mutates — emits notify-send / notify-dispatch commands
the operator runs. The autohealth state file tracks last-tick +
per-finding suppression so the operator isn't spammed.

CLI:
  autohealth.py tick     [--config P] [--json|--human]
                        run one synthesis pass, persist state,
                        emit notify-dispatch commands
  autohealth.py status   [--config P] [--json|--human]
                        last-tick state + suppressed counts
  autohealth.py history  [--limit N] [--config P] [--json|--human]
                        recent ticks from state JSONL
  autohealth.py advisory [--config P] [--json|--human]
                        most-recent findings ranked by severity

State: /var/lib/sovereign-os/autohealth.jsonl (one JSON object per
tick). Operator-overlay (R283/SDD-030): /etc/sovereign-os/autohealth.toml.

Exit codes:
  0  no critical findings
  1  ≥1 attention finding
  2  ≥1 critical finding
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R308"
SDD_VECTOR = "E2.M14"


DEFAULTS = {
    "state_path": "/var/lib/sovereign-os/autohealth.jsonl",
    # Notification suppression window per finding key, in seconds.
    "notify_suppress_seconds": 1800,  # 30 min — don't spam
    # Which axes to synthesize (operator can disable any).
    "axes": [
        "operator-posture",
        "thermal-oc-budget",
        "storage-health",
        "memory-pressure-damper",
        "health-scan",
    ],
    # Min severity that triggers a notify-dispatch command.
    "notify_min_severity": "attention",
}


# Axis → command tuple (script path, args). Each emits JSON with a
# `verdict` field that maps to severity.
AXES_MAP = {
    "operator-posture": ("scripts/hardware/operator-posture.py",
                          ["status", "--json"]),
    "thermal-oc-budget": ("scripts/hardware/thermal-oc-budget.py",
                          ["status", "--json"]),
    "storage-health":   ("scripts/hardware/storage-health-rollup.py",
                          ["status", "--json"]),
    "memory-pressure-damper": ("scripts/hardware/memory-pressure-oc-damper.py",
                               ["status", "--json"]),
    "health-scan":      ("scripts/hardware/health-scan.py",
                          ["--json"]),
}


# Verdict → severity classifier (axis-aware).
def classify_severity(verdict: str | None) -> str:
    if verdict is None:
        return "informational"
    v = verdict.lower()
    critical = {"degraded", "critical", "over-budget", "pull-oc-now",
                "dampen-fully"}
    attention = {"watch", "tight", "drift", "headroom-tight",
                 "thermal-watch", "psu-watch", "both-tight",
                 "dampen-by-1", "memory-probe-unavailable",
                 "probes-unavailable", "warn"}
    if v in critical:
        return "critical"
    if v in attention:
        return "attention"
    return "informational"


def _run_axis(rel_path: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / rel_path
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def collect_findings(axes: list[str]) -> list[dict[str, Any]]:
    """For each enabled axis, run the rollup + map its verdict to a
    finding with severity + message."""
    findings: list[dict[str, Any]] = []
    for axis in axes:
        spec = AXES_MAP.get(axis)
        if spec is None:
            findings.append({
                "axis": axis,
                "verdict": "unknown-axis",
                "severity": "informational",
                "message": f"axis `{axis}` not in AXES_MAP",
                "probe": "(internal)",
            })
            continue
        doc = _run_axis(*spec)
        if doc is None:
            findings.append({
                "axis": axis,
                "verdict": "probe-unavailable",
                "severity": "attention",
                "message": f"{axis} probe unavailable (script missing or "
                           f"non-JSON output)",
                "probe": spec[0],
            })
            continue
        verdict = doc.get("verdict") or doc.get("status")
        severity = classify_severity(verdict)
        message = doc.get("message") or ""
        # Some axes (notably health-scan) signal state via `needs_attention`
        # (bool) + per-probe severities instead of a single `verdict`/`status`
        # string. Without this, their verdict reads as None → classify_severity
        # floors them to "informational", which is BELOW notify_min_severity
        # ("attention") — so autohealth would NEVER alert on them even when
        # needs_attention is true. health-scan covers gpu/network/cpu/fs/raid,
        # exactly the cross-cutting failures autohealth exists to surface, so
        # this dead axis silently defeated the whole notify path. Map it.
        if verdict is None and doc.get("needs_attention") is True:
            verdict = "needs-attention"
            severity = "attention"
            summary = doc.get("summary")
            if isinstance(summary, dict) and summary.get("attention"):
                message = f"{summary['attention']} probe(s) need attention"
        findings.append({
            "axis": axis,
            "verdict": verdict,
            "severity": severity,
            "message": message,
            "probe": spec[0],
        })
    return findings


def notify_commands(findings: list[dict[str, Any]], cfg: dict,
                    suppression_state: dict[str, float]) -> list[dict]:
    """Build operator-runnable notify-dispatch commands for each
    finding above the threshold + not in suppression window."""
    sev_rank = {"informational": 0, "attention": 1, "critical": 2}
    min_rank = sev_rank.get(cfg["notify_min_severity"], 1)
    now = time.time()
    sw = float(cfg["notify_suppress_seconds"])
    out = []
    for f in findings:
        if sev_rank.get(f["severity"], 0) < min_rank:
            continue
        key = f"{f['axis']}::{f['verdict']}"
        last_at = suppression_state.get(key, 0.0)
        if (now - last_at) < sw:
            out.append({
                "axis": f["axis"],
                "verdict": f["verdict"],
                "severity": f["severity"],
                "suppressed": True,
                "suppressed_until_sec": (last_at + sw) - now,
                "command": None,
            })
            continue
        # Operator-runnable notify dispatch (composes R254 notify).
        msg = f["message"] or f["verdict"] or "(no message)"
        axis = f["axis"]
        full_msg = f"[{axis}] {msg}"
        cmd = (f"sovereign-osctl notify send --severity {f['severity']} "
               f"--message {json.dumps(full_msg)}")
        out.append({
            "axis": f["axis"],
            "verdict": f["verdict"],
            "severity": f["severity"],
            "suppressed": False,
            "command": cmd,
        })
    return out


def load_state(state_path: Path) -> tuple[list[dict], dict[str, float]]:
    """Load (history rows, per-finding-key last-notify timestamps)."""
    if not state_path.is_file():
        return [], {}
    rows: list[dict] = []
    suppression: dict[str, float] = {}
    try:
        body = state_path.read_text(encoding="utf-8")
    except OSError:
        return rows, suppression
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(row)
        # Walk findings for last-notify timestamps.
        for n in row.get("notify_commands", []) or []:
            if n.get("suppressed"):
                continue
            if n.get("command") is None:
                continue
            key = f"{n.get('axis')}::{n.get('verdict')}"
            ts = row.get("tick_at_epoch", 0.0)
            if ts > suppression.get(key, 0.0):
                suppression[key] = ts
    return rows, suppression


def write_tick(state_path: Path, row: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with state_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        # Persistence failure must NOT take the verb down.
        pass


def build_tick(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("autohealth", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]

    state_path = Path(cfg["state_path"])
    _history, suppression = load_state(state_path)

    findings = collect_findings(cfg["axes"])
    notify_cmds = notify_commands(findings, cfg, suppression)

    # Severity rollup.
    sev_counts = {"critical": 0, "attention": 0, "informational": 0}
    for f in findings:
        sev_counts[f["severity"]] = sev_counts.get(f["severity"], 0) + 1
    if sev_counts["critical"] > 0:
        rc = 2
        verdict = "critical-findings"
    elif sev_counts["attention"] > 0:
        rc = 1
        verdict = "attention-findings"
    else:
        rc = 0
        verdict = "all-clear"

    now = time.time()
    row = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "tick_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "tick_at_epoch": now,
        "verdict": verdict,
        "rc": rc,
        "severity_counts": sev_counts,
        "findings": findings,
        "notify_commands": notify_cmds,
        "config": cfg,
        "overlay": meta,
    }
    write_tick(state_path, row)
    return row


def render_human(doc: dict) -> str:
    lines = ["── R308 sovereign-os autohealth tick (E2.M14) ──"]
    lines.append(f"  tick_at:     {doc['tick_at']}")
    lines.append(f"  verdict:     {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  critical:    {doc['severity_counts']['critical']}")
    lines.append(f"  attention:   {doc['severity_counts']['attention']}")
    lines.append(f"  informational: {doc['severity_counts']['informational']}")
    lines.append("")
    lines.append("  findings:")
    for f in doc["findings"]:
        mark = {"critical": "!!", "attention": "??",
                "informational": "OK"}.get(f["severity"], "??")
        lines.append(f"    [{mark}] {f['axis']:24s} verdict={f['verdict']}")
        if f.get("message"):
            lines.append(f"          {f['message'][:80]}")
    if doc.get("notify_commands"):
        lines.append("")
        lines.append("  notify dispatch:")
        for n in doc["notify_commands"]:
            tag = "SUPPRESSED" if n.get("suppressed") else "EMIT      "
            lines.append(f"    [{tag}] {n['axis']} → severity={n['severity']}")
            if n.get("command"):
                lines.append(f"      $ {n['command']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="autohealth.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("tick", "status", "advisory"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")
    ph = sub.add_parser("history")
    ph.add_argument("--limit", type=int, default=10)
    ph.add_argument("--config", type=Path)
    fh = ph.add_mutually_exclusive_group()
    fh.add_argument("--json", dest="fmt", action="store_const", const="json")
    fh.add_argument("--human", dest="fmt", action="store_const", const="human")
    ph.set_defaults(fmt="json")

    args = p.parse_args(argv)

    if args.verb == "tick":
        doc = build_tick(args.config)
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_human(doc), end="")
        return doc["rc"]

    # status / advisory / history pull from state JSONL.
    cfg_meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("autohealth", DEFAULTS,
                                    explicit_path=args.config)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        cfg_meta["_source"] = loaded.get("_source", cfg_meta["_source"])
        cfg_meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
    state_path = Path(cfg["state_path"])
    history, suppression = load_state(state_path)

    if args.verb == "history":
        rows = history[-args.limit:]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "state_path": str(state_path),
                "total_rows": len(history),
                "returned_rows": len(rows),
                "rows": rows,
                "overlay": cfg_meta,
            }, indent=2))
        else:
            print(f"── R308 autohealth history (E2.M14) ──")
            print(f"  state path:    {state_path}")
            print(f"  total rows:    {len(history)}")
            for r in rows:
                print(f"  {r.get('tick_at', '?')}  verdict={r.get('verdict')} "
                      f"crit={r.get('severity_counts', {}).get('critical', 0)} "
                      f"attn={r.get('severity_counts', {}).get('attention', 0)}")
        return 0

    # status / advisory: report last-tick + suppression state.
    last = history[-1] if history else None
    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "state_path": str(state_path),
            "tick_count": len(history),
            "last_tick": last,
            "suppression_keys": list(suppression.keys()),
            "overlay": cfg_meta,
        }, indent=2))
    else:
        if last is None:
            print("── R308 autohealth status (E2.M14) ──")
            print(f"  state path:  {state_path}")
            print("  no ticks recorded — run `sovereign-osctl autohealth tick`")
        else:
            print(render_human(last), end="")
            print()
            print(f"  total ticks: {len(history)}")
            print(f"  suppression keys: {len(suppression)}")
    return (last or {}).get("rc", 0)


if __name__ == "__main__":
    sys.exit(main())
