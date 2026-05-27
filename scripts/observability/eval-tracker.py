#!/usr/bin/env python3
"""scripts/observability/eval-tracker.py — eval-history aggregation core
(M060 D-10 / R10106-R10108).

The data model behind the D-10 eval-history cockpit dashboard. Reads the
Eval-Value fabric's append-only eval-run log (JSONL) and aggregates per-task
pass/fail, per-model score trend, benchmark-suite progress, and the
adapter-promotion candidate list — the last cross-referenced against the
D-11 adapter registry (via the SAME adapter-foundry core, no drift).

  M079 WB/BB DISAGGREGATION (R13131-R13136, arXiv 2604.09839 formal proof):
  white-box benchmarks (activation steering, weight edits) are NEVER averaged
  with black-box benchmarks (prompt-only). This core computes `bb_pass_pct`
  ONLY over intervention_class=="bb" runs and `wb_pass_pct` ONLY over
  intervention_class=="wb" runs — they are never combined.

  Benchmark suites surfaced (frontend keys): math_avg / alfworld / arc_agi_1 /
  arc_agi_2 / sudoku (M078 HölderPO + M080 HRM/TRM targets) + activation_steer
  (WB, disaggregated).

Eval-run record (one JSONL line; missing fields tolerated):
  ts · task · suite · intervention_class(bb|wb) · model · role · score(0-1) ·
  passed(bool) · baseline_score · trace_id · adapter_id

Sovereignty: stdlib-only. Absent store/registry → empty aggregates (the
dashboard shows "no data"), NEVER a crash. This is the `core` surface of the
§1g 8-surface ladder for the eval module; `scripts/operator/evals-api.py`
serves it, `sovereign-osctl evals` drives it, the D-10 webapp renders it.

  eval-tracker.py summary    [--window N] [--json]   full dashboard model
  eval-tracker.py suites     [--json]                benchmark-suite block only
  eval-tracker.py candidates [--json]                adapter-promotion candidates
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_EVAL_STORE", "/var/log/sovereign-os/evals.jsonl",
))
MAX_RUNS = int(os.environ.get("SOVEREIGN_OS_EVAL_STORE_MAX", "50000"))

# Benchmark suites the D-10 suites table renders (frontend writeSuite keys).
SUITE_KEYS = ("math_avg", "alfworld", "arc_agi_1", "arc_agi_2", "sudoku", "activation_steer")
TREND_LEN = 20

# Import the adapter-foundry core (single source for promotion-candidate state).
_AF_CORE_PATH = _REPO_ROOT / "scripts" / "inference" / "adapter-foundry.py"
_spec = importlib.util.spec_from_file_location("_adapterfoundry_for_eval", _AF_CORE_PATH)
_af = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_af)  # type: ignore[union-attr]


def _now_ms() -> float:
    return time.time() * 1000.0


def _coerce_ms(ts: Any) -> float | None:
    if isinstance(ts, (int, float)):
        return float(ts) * 1000.0 if ts < 1_000_000_000_000 else float(ts)
    if isinstance(ts, str):
        try:
            from datetime import datetime
            return datetime.fromisoformat(ts.strip().replace("Z", "+00:00")).timestamp() * 1000.0
        except (ValueError, OSError):
            return None
    return None


def _as_pct(score: Any) -> float | None:
    """Normalise a score to a 0-100 percentage. ≤1.0 → fraction → *100;
    otherwise already a percent. None → None."""
    if not isinstance(score, (int, float)):
        return None
    return round(score * 100.0, 2) if score <= 1.0 else round(float(score), 2)


def load_runs(store: Path = EVAL_STORE) -> list[dict[str, Any]]:
    """Read the JSONL eval-run log → list of records. Tolerates blank/malformed
    lines. Absent store → empty list (graceful)."""
    if not store.is_file():
        return []
    runs: list[dict[str, Any]] = []
    try:
        with store.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(rec, dict) and rec.get("task"):
                    runs.append(rec)
    except OSError:
        return []
    return runs[-MAX_RUNS:]


def _passed(run: dict[str, Any]) -> bool:
    p = run.get("passed")
    if isinstance(p, bool):
        return p
    # fall back to score ≥ 0.5 (fraction) / ≥ 50 (percent) when no explicit pass
    pct = _as_pct(run.get("score"))
    return pct is not None and pct >= 50.0


def summary(window_secs: int = 2_592_000, store: Path | None = None) -> dict[str, Any]:
    """The full D-10 dashboard model over the time window (default 30d)."""
    runs_all = load_runs(store) if store is not None else load_runs()
    cutoff = _now_ms() - window_secs * 1000.0
    runs = [r for r in runs_all if (_coerce_ms(r.get("ts")) or _now_ms()) >= cutoff]
    runs.sort(key=lambda r: _coerce_ms(r.get("ts")) or 0.0)

    # --- M079 disaggregated pass rates (NEVER mixed) -----------------------
    bb = [r for r in runs if str(r.get("intervention_class", "")).lower() == "bb"]
    wb = [r for r in runs if str(r.get("intervention_class", "")).lower() == "wb"]
    bb_pass = round(100.0 * sum(_passed(r) for r in bb) / len(bb), 2) if bb else None
    wb_pass = round(100.0 * sum(_passed(r) for r in wb) / len(wb), 2) if wb else None

    # --- benchmark suites --------------------------------------------------
    suites: dict[str, Any] = {}
    for key in SUITE_KEYS:
        srun = [r for r in runs if r.get("suite") == key]
        scores = [p for r in srun if (p := _as_pct(r.get("score"))) is not None]
        suites[key] = {
            "current_pct": scores[-1] if scores else None,
            "trend": scores[-TREND_LEN:],
            "run_count": len(srun),
        }

    # --- per-task ----------------------------------------------------------
    by_task: dict[str, dict[str, Any]] = {}
    for r in runs:
        t = str(r.get("task"))
        e = by_task.setdefault(t, {
            "name": t, "intervention_class": r.get("intervention_class"),
            "run_count": 0, "_passed": 0, "trend": [], "last_run_ts": None,
            "trace_id": r.get("trace_id"),
        })
        e["run_count"] += 1
        if _passed(r):
            e["_passed"] += 1
        p = _as_pct(r.get("score"))
        if p is not None:
            e["trend"].append(p)
        ts = r.get("ts")
        if ts:
            e["last_run_ts"] = ts
            e["trace_id"] = r.get("trace_id") or e["trace_id"]
    tasks = []
    for e in by_task.values():
        e["pass_pct"] = round(100.0 * e["_passed"] / e["run_count"], 1) if e["run_count"] else None
        e["trend"] = e["trend"][-TREND_LEN:]
        del e["_passed"]
        tasks.append(e)
    tasks.sort(key=lambda t: t["last_run_ts"] or "", reverse=True)

    # --- per-model ---------------------------------------------------------
    by_model: dict[str, dict[str, Any]] = {}
    for r in runs:
        m = r.get("model")
        if not m:
            continue
        e = by_model.setdefault(str(m), {
            "name": str(m), "role": r.get("role"), "_scores": [], "_base": [], "trend": [],
        })
        p = _as_pct(r.get("score"))
        if p is not None:
            e["_scores"].append(p)
            e["trend"].append(p)
        b = _as_pct(r.get("baseline_score"))
        if b is not None:
            e["_base"].append(b)
    models = []
    for e in by_model.values():
        avg = round(sum(e["_scores"]) / len(e["_scores"]), 1) if e["_scores"] else None
        base = round(sum(e["_base"]) / len(e["_base"]), 1) if e["_base"] else None
        e["eval_avg"] = avg
        e["vs_baseline_pct"] = round(avg - base, 1) if (avg is not None and base is not None) else None
        e["trend"] = e["trend"][-TREND_LEN:]
        del e["_scores"], e["_base"]
        models.append(e)
    models.sort(key=lambda m: m["eval_avg"] or 0, reverse=True)

    # --- adapter-promotion candidates (from the D-11 adapter core) ---------
    candidates = []
    for a in _af.list_adapters():
        if a["status"] != "pending":
            continue
        g = a.get("gates", {})
        if g.get("snapshot") == "passed" and g.get("test_eval") == "passed" \
                and (g.get("oracle") == "passed" or g.get("human") == "passed"):
            gate_status = "ready"
        elif g.get("test_eval") != "passed":
            gate_status = "pending-test"
        else:
            gate_status = "pending-oracle"
        candidates.append({
            "adapter_id": a["id"], "base_model": a["base_model"],
            "training_method": a.get("training", "sft"),
            "eval_gain_pct": a.get("eval_gain_pct"), "gate_status": gate_status,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total_runs": len(runs),
            "bb_pass_pct": bb_pass,
            "wb_pass_pct": wb_pass,
            "candidate_count": len(candidates),
        },
        "suites": suites,
        "tasks": tasks,
        "models": models,
        "candidates": candidates,
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="eval-history aggregation core (M060 D-10)")
    sub = p.add_subparsers(dest="cmd")
    sm = sub.add_parser("summary")
    sm.add_argument("--window", type=int, default=2_592_000)
    sm.add_argument("--json", action="store_true")
    for name in ("suites", "candidates"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "summary"
    if cmd == "suites":
        _print(summary()["suites"])
    elif cmd == "candidates":
        _print(summary()["candidates"])
    else:
        _print(summary(getattr(args, "window", 2_592_000)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
