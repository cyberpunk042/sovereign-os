#!/usr/bin/env python3
"""scripts/intelligence/next-action-advisor.py — R329 (E2.M22).

Operator-pull "what should I do now?" decision-support layer.
Examines R322 unified state snapshot + emits operator-readable
ranked list of most-impactful verbs to run next.

For each probe in the snapshot:
  - if rc == 2 (critical) → high priority recommendation
  - if rc == 1 (attention) → medium priority recommendation
  - if rc == 0 (ok) → no recommendation
Each recommendation carries: priority, source-probe, suggested-verb,
operator-readable rationale.

CLI:
  next-action-advisor.py list   [--limit N] [--config P] [--json|--human]
                                  ranked recommendations (top N)
  next-action-advisor.py top                                  [--config P] [--json|--human]
                                  the single most-impactful next action

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/next-action-advisor.toml
  - max_recommendations  (default 10)
  - per_probe_timeout_sec (default 12 — slightly larger than R322's)

Exit codes:
  0  any-state rendered
  1  no recommendations (everything clean)
  2  usage error / snapshot unavailable
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R329"
SDD_VECTOR = "E2.M22"


DEFAULTS = {
    "max_recommendations": 10,
    "per_probe_timeout_sec": 12,
}


# Per-probe → suggested-verb mapping. When a probe returns a
# non-zero rc, the advisor recommends the operator run the
# corresponding verb. NULL entries mean "investigate manually".
PROBE_TO_VERB: dict[str, dict[str, Any]] = {
    "heat-oc-throttle": {
        "verb": "sovereign-osctl heat-oc-throttle status",
        "axis": "thermal/oc",
        "rationale": "Heat-OC throttle has recommendations — review "
                      "and decide whether to apply with the triple-gate.",
    },
    "memory-pressure-damper": {
        "verb": "sovereign-osctl memory-pressure-damper status",
        "axis": "memory",
        "rationale": "Memory pressure indicates dampening recommended.",
    },
    "thermal-oc": {
        "verb": "sovereign-osctl thermal-oc-budget status",
        "axis": "thermal/oc",
        "rationale": "Thermal-OC budget has changed; check before "
                      "raising OC further.",
    },
    "operator-posture": {
        "verb": "sovereign-osctl operator-posture status",
        "axis": "posture",
        "rationale": "Operator-posture rollup shows axis attention.",
    },
    "storage-health": {
        "verb": "sovereign-osctl storage-health status",
        "axis": "storage",
        "rationale": "Storage-health rollup found drift; investigate.",
    },
    "autohealth": {
        "verb": "sovereign-osctl autohealth status",
        "axis": "diagnostics",
        "rationale": "Autohealth synthesizer flagged a finding.",
    },
    "kernel-cmdline": {
        "verb": "sovereign-osctl kernel-cmdline diff",
        "axis": "kernel",
        "rationale": "Kernel cmdline diverges from operator-recommended set.",
    },
    "hardening-base": {
        "verb": "sovereign-osctl hardening-base check",
        "axis": "hardening",
        "rationale": "Hardening posture mismatch found.",
    },
    "network-stack": {
        "verb": "sovereign-osctl network-stack status",
        "axis": "network",
        "rationale": "Network stack reports a degraded service.",
    },
    "battery-ladder": {
        "verb": "sovereign-osctl battery-ladder status",
        "axis": "lifecycle",
        "rationale": "Battery-ladder reports state worth checking.",
    },
    "cpu-hotswap": {
        "verb": "sovereign-osctl cpu-hotswap status",
        "axis": "cpu",
        "rationale": "CPU hotswap detected drift from pinned mode.",
    },
    "psu-oc-mode": {
        "verb": "sovereign-osctl psu-oc-mode status",
        "axis": "power",
        "rationale": "PSU OC-mode declaration needs operator input.",
    },
    "board-advisor": {
        "verb": "sovereign-osctl board-advisor status",
        "axis": "hardware",
        "rationale": "Host board not in catalog; operator may want to "
                      "add their board via overlay.",
    },
}


PRIORITY_RANK = {"critical": 2, "attention": 1, "informational": 0,
                   "unknown": 0}


def severity_from_rc(rc: int | None) -> str:
    if rc == 2:
        return "critical"
    if rc == 1:
        return "attention"
    if rc == 0:
        return "informational"
    return "unknown"


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("next-action-advisor", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def fetch_snapshot(timeout: int) -> dict | None:
    """Spawn R322 snapshot snapshot --json + parse."""
    snap_script = REPO_ROOT / "scripts" / "diagnostics" / "state-snapshot.py"
    if not snap_script.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(snap_script), "snapshot", "--json"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def derive_recommendations(snapshot: dict | None,
                            max_recs: int) -> list[dict[str, Any]]:
    if snapshot is None:
        return []
    recs: list[dict[str, Any]] = []
    for p in snapshot.get("probes", []):
        if not isinstance(p, dict):
            continue
        name = p.get("name", "?")
        rc = p.get("rc")
        sev = severity_from_rc(rc)
        if sev == "informational":
            continue
        verb_spec = PROBE_TO_VERB.get(name, {})
        # Pull verdict + message from probe's own output.
        out = p.get("output") or {}
        verdict = (out.get("verdict") or out.get("status") or "(no-verdict)") \
            if isinstance(out, dict) else "(no-output)"
        message = ""
        if isinstance(out, dict):
            message = out.get("message", "") or ""
        rec = {
            "probe": name,
            "axis": verb_spec.get("axis", p.get("axis", "?")),
            "severity": sev,
            "rc": rc,
            "verdict": verdict,
            "suggested_verb": verb_spec.get(
                "verb", f"# investigate {name} manually"),
            "rationale": verb_spec.get(
                "rationale", "Probe returned non-zero rc."),
            "probe_message": message[:200] if isinstance(message, str) else "",
            "priority": PRIORITY_RANK.get(sev, 0),
        }
        recs.append(rec)

    recs.sort(key=lambda r: (-r["priority"], r["probe"]))
    return recs[:max_recs]


def render_human(recs: list[dict], snapshot: dict | None) -> str:
    lines = [f"── R329 sovereign-os next-action advisor (E2.M22) ──"]
    if snapshot is not None:
        lines.append(f"  source: R322 snapshot taken "
                      f"{snapshot.get('snapshot_at')}")
    lines.append(f"  recommendations: {len(recs)}")
    lines.append("")
    if not recs:
        lines.append("  (no recommendations — fleet looks all-clear)")
        return "\n".join(lines) + "\n"
    for i, r in enumerate(recs, start=1):
        mark = {"critical": "[!!]",
                 "attention": "[??]"}.get(r["severity"], "[--]")
        lines.append(f"  {i}. {mark} {r['probe']:28s} "
                      f"({r['axis']})  rc={r['rc']}  verdict={r['verdict']}")
        lines.append(f"        $ {r['suggested_verb']}")
        lines.append(f"        {r['rationale']}")
        if r.get("probe_message"):
            lines.append(f"        probe message: {r['probe_message'][:80]}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="next-action-advisor.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--limit", type=int)
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    pt = sub.add_parser("top")
    pt.add_argument("--config", type=Path)
    ft = pt.add_mutually_exclusive_group()
    ft.add_argument("--json", dest="fmt", action="store_const", const="json")
    ft.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    timeout = int(cfg["per_probe_timeout_sec"])
    snap = fetch_snapshot(timeout)
    if snap is None:
        print(json.dumps({
            "error": ("R322 snapshot unavailable — verify "
                      "scripts/diagnostics/state-snapshot.py present"),
            "round": ROUND,
            "rc": 2,
        }, indent=2), file=sys.stderr)
        return 2

    max_recs = args.limit if (args.cmd == "list" and args.limit) \
        else int(cfg["max_recommendations"])
    recs = derive_recommendations(snap, max_recs)

    if args.cmd == "top":
        top = recs[0] if recs else None
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "snapshot_at": snap.get("snapshot_at"),
                "top_recommendation": top,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R329 next-action TOP (E2.M22) ──")
            if top is None:
                print("  (no recommendations — fleet all-clear)")
            else:
                mark = {"critical": "[!!]", "attention": "[??]"}.get(
                    top["severity"], "[--]")
                print(f"  {mark} {top['probe']} ({top['axis']})  "
                      f"verdict={top['verdict']}")
                print(f"  $ {top['suggested_verb']}")
                print(f"  rationale: {top['rationale']}")
        return 0 if recs else 1

    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "snapshot_at": snap.get("snapshot_at"),
            "recommendation_count": len(recs),
            "recommendations": recs,
            "overlay": meta,
        }, indent=2))
    else:
        print(render_human(recs, snap), end="")
    return 0 if recs else 1


if __name__ == "__main__":
    sys.exit(main())
