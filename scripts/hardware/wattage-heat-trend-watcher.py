#!/usr/bin/env python3
"""scripts/hardware/wattage-heat-trend-watcher.py — R316 (E1.M36).

Operator-named (§1b mandate row, verbatim): "real time tracking and
intelligence around it". Closes E1.M36.

Periodic tick: samples wattage + GPU/CPU temp tuples → JSONL state.
Rolling-window trend analysis on each tick: classifies last-N vs
prior-N as {stable / climbing / climbing-fast}. Composes the time-
series streams shipped in prior rounds:

  R258 wattage-time-series-sampler  → host wattage estimate
  R265 heat-integration             → thermal multi-sensor readout

NEVER auto-mutates. Emits the trend verdict; operator (or R308
autohealth) decides whether to act.

CLI:
  wattage-heat-trend-watcher.py tick    [--config P] [--json|--human]
  wattage-heat-trend-watcher.py status  [--config P] [--json|--human]
  wattage-heat-trend-watcher.py history [--limit N] [--config P]
                                         [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/wattage-heat-
trend-watcher.toml.

Exit codes:
  0  stable
  1  climbing (1+ signal rising)
  2  climbing-fast (1+ signal rising sharply — operator action)
"""
from __future__ import annotations

import argparse
import json
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
ROUND = "R316"
SDD_VECTOR = "E1.M36"


DEFAULTS = {
    "state_path": "/var/lib/sovereign-os/wattage-heat-trend.jsonl",
    # Rolling-window comparison: last_N vs prior_N samples.
    "window_size": 5,
    # Climb classification (% increase from prior window to last):
    "climb_pct_warn": 10.0,   # ≥10% rise → climbing
    "climb_pct_crit": 25.0,   # ≥25% rise → climbing-fast
}


def _run_json(rel: str, args: list[str]) -> dict[str, Any] | None:
    p = REPO_ROOT / rel
    if not p.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(p), *args],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def sample_signals() -> dict[str, float | None]:
    """Sample wattage + CPU/GPU temps via existing probes."""
    out: dict[str, float | None] = {
        "wattage_w": None,
        "cpu_temp_c": None,
        "gpu_temp_c": None,
    }
    # Wattage estimate via R252 power-status `budget` (best-effort). NOTE:
    # power-status.py REQUIRES a verb {psu,ups,budget,advisories} — calling
    # it bare (`--json`, no verb) exits rc=2 with empty stdout, so the old
    # probe captured no wattage at all. `budget` is the load/headroom view;
    # its canonical field is `estimated_load_watts` (legacy *_w kept as
    # fallback for robustness).
    ps = _run_json("scripts/hardware/power-status.py", ["budget", "--json"])
    if isinstance(ps, dict):
        summary = ps.get("summary") if isinstance(
            ps.get("summary"), dict) else {}
        for src, key in ((ps, "estimated_load_watts"),
                         (summary, "estimated_load_w"),
                         (ps, "estimated_load_w")):
            w = src.get(key)
            if isinstance(w, (int, float)):
                out["wattage_w"] = float(w)
                break

    # Heat probe via R296 thermal-oc-budget (E2.M10): `thermal.hottest_*_c`
    # is the canonical hottest-sensor reading, present (possibly null) even
    # with no sensors wired. (Was a dangling ref to a never-created
    # heat-integration.py — the trend watcher never captured temps.)
    heat = _run_json("scripts/hardware/thermal-oc-budget.py",
                      ["status", "--json"])
    if isinstance(heat, dict):
        thermal = heat.get("thermal") if isinstance(
            heat.get("thermal"), dict) else {}
        summary = heat.get("summary") if isinstance(
            heat.get("summary"), dict) else {}
        # CPU temp: thermal.hottest_cpu_c (canonical), then legacy fallbacks.
        for src, key in ((thermal, "hottest_cpu_c"),
                         (summary, "cpu_temp_max_c"), (heat, "cpu_temp_c"),
                         (heat, "cpu_max_c")):
            v = src.get(key)
            if isinstance(v, (int, float)):
                out["cpu_temp_c"] = float(v)
                break
        for src, key in ((thermal, "hottest_gpu_c"),
                         (summary, "gpu_temp_max_c"), (heat, "gpu_temp_c"),
                         (heat, "gpu_max_c")):
            v = src.get(key)
            if isinstance(v, (int, float)):
                out["gpu_temp_c"] = float(v)
                break
    return out


def classify_trend(prior_avg: float | None, last_avg: float | None,
                    warn_pct: float, crit_pct: float) -> str:
    if prior_avg is None or last_avg is None or prior_avg <= 0:
        return "no-data"
    pct = ((last_avg - prior_avg) / prior_avg) * 100.0
    if pct >= crit_pct:
        return "climbing-fast"
    if pct >= warn_pct:
        return "climbing"
    if pct <= -warn_pct:
        return "dropping"
    return "stable"


def derive_trends(history: list[dict], cfg: dict) -> dict[str, Any]:
    """Walk history, split into last-N and prior-N windows per signal,
    classify each signal's trend."""
    n = int(cfg["window_size"])
    signals = ["wattage_w", "cpu_temp_c", "gpu_temp_c"]
    out: dict[str, Any] = {}
    if len(history) < 2 * n:
        for s in signals:
            out[s] = {"trend": "insufficient-data",
                       "last_avg": None, "prior_avg": None,
                       "pct_change": None}
        return out
    last_rows = history[-n:]
    prior_rows = history[-(2 * n):-n]
    for s in signals:
        last_vals = [r["signals"].get(s) for r in last_rows
                      if isinstance(r.get("signals"), dict)
                      and isinstance(r["signals"].get(s), (int, float))]
        prior_vals = [r["signals"].get(s) for r in prior_rows
                       if isinstance(r.get("signals"), dict)
                       and isinstance(r["signals"].get(s), (int, float))]
        if not last_vals or not prior_vals:
            out[s] = {"trend": "no-data",
                       "last_avg": None, "prior_avg": None,
                       "pct_change": None}
            continue
        last_avg = sum(last_vals) / len(last_vals)
        prior_avg = sum(prior_vals) / len(prior_vals)
        trend = classify_trend(prior_avg, last_avg,
                                cfg["climb_pct_warn"],
                                cfg["climb_pct_crit"])
        pct_change = ((last_avg - prior_avg) / prior_avg * 100.0
                      if prior_avg > 0 else None)
        out[s] = {"trend": trend,
                   "last_avg": last_avg,
                   "prior_avg": prior_avg,
                   "pct_change": pct_change}
    return out


def aggregate_verdict(trends: dict) -> tuple[str, int]:
    any_crit = any(t.get("trend") == "climbing-fast"
                   for t in trends.values())
    any_warn = any(t.get("trend") == "climbing"
                   for t in trends.values())
    if any_crit:
        return "climbing-fast", 2
    if any_warn:
        return "climbing", 1
    return "stable", 0


def load_history(state_path: Path) -> list[dict]:
    if not state_path.is_file():
        return []
    rows = []
    try:
        body = state_path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_tick(state_path: Path, row: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with state_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def build_tick(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("wattage-heat-trend-watcher", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    state_path = Path(cfg["state_path"])
    history = load_history(state_path)
    signals = sample_signals()
    now = time.time()
    row = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "tick_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "tick_at_epoch": now,
        "signals": signals,
    }
    write_tick(state_path, row)
    # Reload to include the just-written row.
    history = load_history(state_path)
    trends = derive_trends(history, cfg)
    verdict, rc = aggregate_verdict(trends)
    row["trends"] = trends
    row["verdict"] = verdict
    row["rc"] = rc
    row["history_count"] = len(history)
    row["config"] = cfg
    row["overlay"] = meta
    return row


def render_human(doc: dict) -> str:
    lines = [f"── R316 sovereign-os wattage+heat trend watcher (E1.M36) ──",
             f"  tick_at:        {doc['tick_at']}",
             f"  history count:  {doc['history_count']}",
             f"  verdict:        {doc['verdict']} (rc={doc['rc']})",
             ""]
    lines.append("  current signals:")
    for s, v in doc["signals"].items():
        lines.append(f"    {s:>12s}: {v}")
    lines.append("")
    lines.append("  trends (last vs prior window):")
    for s, t in (doc.get("trends") or {}).items():
        pct = t.get("pct_change")
        pct_s = f"{pct:+.1f}%" if isinstance(pct, (int, float)) else "n/a"
        lines.append(f"    {s:>12s}: {t.get('trend'):>18s}  "
                      f"last={t.get('last_avg')}  prior={t.get('prior_avg')}  "
                      f"Δ={pct_s}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wattage-heat-trend-watcher.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("tick", "status"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")
    ph = sub.add_parser("history")
    ph.add_argument("--limit", type=int, default=20)
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

    # status / history
    cfg_meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("wattage-heat-trend-watcher", DEFAULTS,
                                    explicit_path=args.config)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        cfg_meta["_source"] = loaded.get("_source", cfg_meta["_source"])
        cfg_meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
    state_path = Path(cfg["state_path"])
    history = load_history(state_path)

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
            print(f"── R316 history (E1.M36) ──")
            print(f"  total rows: {len(history)}")
            for r in rows:
                s = r.get("signals") or {}
                print(f"  {r.get('tick_at', '?')}  W={s.get('wattage_w')} "
                      f"cpu={s.get('cpu_temp_c')}°C gpu={s.get('gpu_temp_c')}°C")
        return 0

    # status
    trends = derive_trends(history, cfg)
    verdict, rc = aggregate_verdict(trends)
    last = history[-1] if history else None
    if args.fmt == "json":
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "state_path": str(state_path),
            "history_count": len(history),
            "last_tick": last,
            "trends": trends,
            "verdict": verdict,
            "rc": rc,
            "overlay": cfg_meta,
        }, indent=2))
    else:
        if last is None:
            print(f"── R316 status (E1.M36) ──")
            print(f"  state path: {state_path}")
            print(f"  no ticks recorded — run "
                  f"`sovereign-osctl wattage-heat-trend tick`")
            return 0
        # Synthesize a status doc to reuse the render.
        last["trends"] = trends
        last["verdict"] = verdict
        last["rc"] = rc
        last["history_count"] = len(history)
        print(render_human(last), end="")
    return rc


if __name__ == "__main__":
    sys.exit(main())
