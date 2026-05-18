#!/usr/bin/env python3
"""scripts/intelligence/morning-brief.py — R352 (E10.M2).

Operator-pull "give me the morning brief on my workstation" — a
single-screen rollup composing the most important operator-pull
intelligence verbs into one narrative + JSON output.

Composes (each is best-effort, NEVER-raise):
  R329 next-action-advisor top 3 ranked recommendations
  R351 module-state          attention_count + items
  R308 autohealth status     latest tick severity (best-effort probe)
  R349 guide topics          which topic is most relevant right now
                              given the current state

Output sections (operator-readable, top-down by urgency):
  1. Attention summary       counts across each axis
  2. Top recommendations     N most-impactful next actions
  3. Module gaps             non-configured / running-without-overlay
  4. Suggested topic guide   one R349 topic to read up on
  5. Quick-glance state      key R322-snapshot rollup verdicts

CLI:
  morning-brief.py rollup   [--limit N] [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/morning-brief.toml
— operator can tune per-section limits and which subverbs to invoke.

Exit codes:
  0  no critical items
  1  at least one critical item across composed sources
  2  usage
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R352"
SDD_VECTOR = "E10.M2"


DEFAULTS = {
    "next_action_limit": 3,
    "module_state_limit": 5,
    "per_probe_timeout_sec": 8,
    "include_autohealth": True,
    "include_guide_suggestion": True,
}


# Topic relevance hints: map attention-signal keyword → topic name.
# When recommendations or module gaps contain these keywords, surface
# the matching R349 topic. NEVER blocks the brief — purely additive.
TOPIC_RELEVANCE_MAP = {
    "thermal":     "memory",
    "memory":      "memory",
    "psu":         "psu",
    "wattage":     "psu",
    "battery":     "ups",
    "ups":         "ups",
    "fan":         "hardware",
    "gpu":         "gpu",
    "vfio":        "gpu",
    "inference":   "inference",
    "router":      "inference",
    "kernel":      "kernel",
    "sysctl":      "kernel",
    "network":     "network",
    "dns":         "network",
    "workload":    "workload-mode",
    "autohealth":  "autohealth",
    "selfdef":     "selfdef",
}


# ── Probe primitives ──────────────────────────────────────────────
def _probe(args: list[str], timeout: int) -> dict[str, Any]:
    """NEVER-raise subprocess wrapper. Returns
    {ok, rc, stdout_text, stderr_text, json (or None)}."""
    try:
        cp = subprocess.run(
            [str(OSCTL)] + args,
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception as e:
        return {"ok": False, "rc": -1, "stdout_text": "",
                "stderr_text": f"{type(e).__name__}: {e}", "json": None}
    out = {"ok": True, "rc": cp.returncode,
           "stdout_text": cp.stdout, "stderr_text": cp.stderr,
           "json": None}
    if cp.stdout.strip().startswith("{") or cp.stdout.strip().startswith("["):
        try:
            out["json"] = json.loads(cp.stdout)
        except Exception:
            out["json"] = None
    return out


def probe_next_action(limit: int, timeout: int) -> dict[str, Any]:
    res = _probe(["next-action", "list", "--limit", str(limit), "--json"],
                  timeout)
    if not res["ok"] or not res["json"]:
        return {"available": False, "items": [],
                "error": res.get("stderr_text", "")[:200]}
    items = res["json"].get("recommendations") or res["json"].get("items") or []
    if not isinstance(items, list):
        items = []
    return {"available": True, "rc": res["rc"], "items": items[:limit]}


def probe_module_state(limit: int, timeout: int) -> dict[str, Any]:
    res = _probe(["module-state", "recommend", "--json"], timeout)
    if not res["ok"] or not res["json"]:
        return {"available": False, "attention_count": 0,
                "items": [], "error": res.get("stderr_text", "")[:200]}
    d = res["json"]
    items = d.get("attention_items") or []
    if not isinstance(items, list):
        items = []
    return {"available": True, "rc": res["rc"],
            "attention_count": d.get("attention_count", len(items)),
            "items": items[:limit]}


def probe_autohealth(timeout: int) -> dict[str, Any]:
    res = _probe(["autohealth", "status", "--json"], timeout)
    if not res["ok"] or not res["json"]:
        return {"available": False, "severity": None,
                "error": res.get("stderr_text", "")[:200]}
    d = res["json"]
    sev = (d.get("severity") or d.get("verdict")
           or d.get("worst_severity"))
    return {"available": True, "rc": res["rc"],
            "severity": sev, "tick": d.get("tick_id") or d.get("tick")}


# ── Topic suggestion ──────────────────────────────────────────────
def suggest_topic(
    next_actions: list[dict], module_items: list[dict],
) -> str | None:
    """Score topics by keyword hits across recommendations + module
    gaps; pick the highest. None when no signal."""
    score: dict[str, int] = {}
    haystack: list[str] = []
    for r in next_actions:
        for k in ("source_probe", "verb", "suggested_verb", "rationale",
                  "title", "axis"):
            v = r.get(k)
            if isinstance(v, str):
                haystack.append(v.lower())
    for m in module_items:
        for k in ("module", "axis", "configure_verb"):
            v = m.get(k)
            if isinstance(v, str):
                haystack.append(v.lower())
    for s in haystack:
        for kw, topic in TOPIC_RELEVANCE_MAP.items():
            if kw in s:
                score[topic] = score.get(topic, 0) + 1
    if not score:
        return None
    return max(score, key=lambda t: score[t])


# ── Aggregation ───────────────────────────────────────────────────
def build_brief(cfg: dict) -> dict[str, Any]:
    timeout = int(cfg.get("per_probe_timeout_sec", 8))
    na = probe_next_action(int(cfg.get("next_action_limit", 3)), timeout)
    ms = probe_module_state(int(cfg.get("module_state_limit", 5)), timeout)
    ah = (probe_autohealth(timeout)
          if cfg.get("include_autohealth", True)
          else {"available": False, "severity": None})

    suggested = (suggest_topic(na["items"], ms["items"])
                 if cfg.get("include_guide_suggestion", True) else None)

    # Critical aggregation.
    critical_signals: list[str] = []
    for r in na["items"]:
        raw_prio = r.get("priority") or r.get("severity") or ""
        prio = str(raw_prio).lower()
        if prio in ("high", "critical"):
            critical_signals.append(
                f"next-action: {r.get('verb') or r.get('title') or 'unnamed'}"
            )
    if ah.get("severity", "") in ("critical", "high"):
        critical_signals.append(f"autohealth severity={ah['severity']}")
    if ms["attention_count"] > 0:
        # module attention is informational; only count it critical when
        # the module is 'running-without-overlay' (operator running stock)
        for m in ms["items"]:
            if m.get("verdict") == "running-without-overlay":
                critical_signals.append(
                    f"module {m['module']} running without operator overlay"
                )

    rc = 1 if critical_signals else 0

    return {
        "rc": rc,
        "critical_signals_count": len(critical_signals),
        "critical_signals": critical_signals,
        "sections": {
            "next_action":   na,
            "module_state":  ms,
            "autohealth":    ah,
        },
        "suggested_topic_guide": suggested,
        "suggested_topic_verb":
            (f"sovereign-osctl guide walkthrough {suggested}"
             if suggested else None),
    }


# ── Loading ───────────────────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "morning-brief", DEFAULTS, explicit_path=overlay_path,
        )
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


# ── Renderer ──────────────────────────────────────────────────────
def render_human(brief: dict) -> str:
    lines = ["── R352 sovereign-os morning-brief (E10.M2) ──"]
    lines.append(f"  critical signals: {brief['critical_signals_count']}")
    for s in brief["critical_signals"]:
        lines.append(f"    ⚠ {s}")
    lines.append("")
    secs = brief["sections"]
    # Next-action section
    na = secs["next_action"]
    if na.get("available"):
        lines.append(f"  next-actions (top {len(na['items'])}):")
        for r in na["items"]:
            raw_tag = r.get("priority") or r.get("severity") or "?"
            tag = str(raw_tag).upper()
            verb = r.get("verb") or r.get("suggested_verb") or r.get("title") or "?"
            lines.append(f"    [{tag}] {verb}")
    else:
        lines.append(f"  next-actions: (unavailable — {na.get('error', '?')[:60]})")
    lines.append("")
    # Module-state section
    ms = secs["module_state"]
    if ms.get("available"):
        lines.append(f"  module gaps: {ms['attention_count']} module(s) need attention")
        for m in ms["items"]:
            lines.append(f"    - {m['module']} [{m['verdict']}]")
            lines.append(f"        $ {m['configure_verb']}")
    else:
        lines.append("  module gaps: (unavailable)")
    lines.append("")
    # Autohealth section
    ah = secs["autohealth"]
    if ah.get("available"):
        lines.append(f"  autohealth: severity={ah['severity']} "
                      f"(tick={ah.get('tick')})")
    else:
        lines.append("  autohealth: (unavailable)")
    lines.append("")
    # Suggested topic
    if brief.get("suggested_topic_verb"):
        lines.append(f"  suggested reading:")
        lines.append(f"    $ {brief['suggested_topic_verb']}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="morning-brief.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("rollup")
    pr.add_argument("--limit", type=int, default=None,
                     help="override next_action_limit")
    pr.add_argument("--config", type=Path)
    fmt = pr.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(getattr(args, "config", None))
    if args.limit:
        cfg["next_action_limit"] = args.limit

    brief = build_brief(cfg)
    out = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        **brief,
        "overlay": meta,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(render_human(brief), end="")
    return brief["rc"]


if __name__ == "__main__":
    sys.exit(main())
