#!/usr/bin/env python3
"""scripts/observability/cost-tracker.py — cost aggregation core
(M060 D-04 / R10075-R10082).

The data model behind the D-04 costs cockpit dashboard. Joins two real
sources — never invents spend:

  - cost policy   /etc/sovereign-os/cost-policy.toml (operator-controlled,
                  dump 9885-9930 verbatim keys: cloud_enabled /
                  cloud_requires_approval / daily_budget_usd /
                  per_request_max_usd / private_paths_never_cloud /
                  log_prompts). Sovereign-safe defaults when absent
                  (cloud disabled, private paths never cloud).
  - span store    the observability fabric's M049 span log — the per-span
                  `cost` attribute (M049 cost field, R08197) is summed by
                  UTC day / project / MS040 profile / model. Read through the
                  SAME trace-store core the D-05 traces dashboard uses, so the
                  span schema never drifts.

Aggregates: today's spend vs budget + request count + avg/request + forecast,
cost-by-project, cost-by-profile (the six MS040 profiles), cost-by-model
(+ tokens + $/Mtok), and the 30-day spend trend.

Sovereignty: stdlib-only (tomllib for the policy, json for spans). Absent
policy/spans → safe defaults + zero spend (the dashboard shows "no … activity"),
NEVER a crash. This is the `core` surface of the §1g 8-surface ladder for the
costs module; `scripts/operator/costs-api.py` serves it, `sovereign-osctl
costs` drives it ad-hoc, the D-04 webapp renders it.

  cost-tracker.py summary [--json]   full dashboard model
  cost-tracker.py policy  [--json]   resolved cost policy only
  cost-tracker.py today   [--json]   today's spend block only
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
COST_POLICY_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_COST_POLICY", "/etc/sovereign-os/cost-policy.toml",
))

# Sovereign-safe defaults (dump 9885-9930): local-only until the operator
# explicitly enables cloud; private paths never leave the box.
POLICY_DEFAULTS: dict[str, Any] = {
    "cloud_enabled": False,
    "cloud_requires_approval": True,
    "daily_budget_usd": None,
    "per_request_max_usd": None,
    "private_paths_never_cloud": True,
    "log_prompts": "local_only",
}

# The six MS040 profiles the dashboard's profile table enumerates.
MS040_PROFILES = ("private", "fast", "careful", "autonomous", "experimental", "production")

# Import the trace-store core (single source of truth for the span schema).
_TRACE_CORE_PATH = _REPO_ROOT / "scripts" / "observability" / "trace-store.py"
_spec = importlib.util.spec_from_file_location("_tracestore_for_cost", _TRACE_CORE_PATH)
_tracestore = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_tracestore)  # type: ignore[union-attr]


def load_policy(path: Path = COST_POLICY_PATH) -> dict[str, Any]:
    """Resolve the cost policy: file values over sovereign-safe defaults.
    Absent/malformed file → defaults (never raises)."""
    policy = dict(POLICY_DEFAULTS)
    if path.is_file():
        try:
            with path.open("rb") as fh:
                doc = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError, ValueError):
            return policy
        # accept either flat keys or a [cost] table
        src = doc.get("cost") if isinstance(doc.get("cost"), dict) else doc
        for k in POLICY_DEFAULTS:
            if k in src:
                policy[k] = src[k]
    return policy


def _span_cost(span: dict[str, Any]) -> float:
    """The per-span USD cost from the M049 `cost` attribute (R08197). Absent /
    non-numeric → 0.0 (a free local span contributes nothing)."""
    attrs = span.get("attributes") or {}
    v = attrs.get("cost", span.get("cost"))
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _utc_date(span: dict[str, Any]) -> str | None:
    ms = _tracestore._coerce_start_ms(span.get("start_ts"))
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def _attr(span: dict[str, Any], key: str) -> Any:
    return (span.get("attributes") or {}).get(key)


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def summary(store: Path | None = None) -> dict[str, Any]:
    """The full D-04 dashboard model. `store` overrides the span-store path
    (test seam); default reads trace-store's configured store."""
    spans = _tracestore.load_spans(store) if store is not None else _tracestore.load_spans()
    policy = load_policy()

    now = datetime.now(tz=timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    # day-fraction elapsed for the end-of-day forecast (guard against 0)
    secs_into_day = now.hour * 3600 + now.minute * 60 + now.second
    day_frac = max(secs_into_day / 86400.0, 1e-6)

    # date → spend (30-day trend) + today aggregates
    by_date: dict[str, float] = {}
    today_spend = 0.0
    today_requests = 0
    today_max_req = 0.0
    by_project: dict[str, dict[str, Any]] = {}
    by_profile: dict[str, dict[str, float]] = {p: {"today": 0.0, "7d": 0.0, "30d": 0.0} for p in MS040_PROFILES}
    by_model: dict[str, dict[str, Any]] = {}

    cutoff_7d = now.timestamp() * 1000 - 7 * 86400 * 1000
    cutoff_30d = now.timestamp() * 1000 - 30 * 86400 * 1000

    for s in spans:
        cost = _span_cost(s)
        ms = _tracestore._coerce_start_ms(s.get("start_ts"))
        d = _utc_date(s)
        if d:
            by_date[d] = by_date.get(d, 0.0) + cost
        in_7d = ms is not None and ms >= cutoff_7d
        in_30d = ms is not None and ms >= cutoff_30d
        is_today = d == today_str

        if is_today:
            today_spend += cost
            today_requests += 1
            today_max_req = max(today_max_req, cost)

        # by project (attributes.project) — only when the span declares one
        proj = _attr(s, "project")
        if proj:
            pe = by_project.setdefault(str(proj), {
                "name": str(proj), "today": 0.0, "7d": 0.0, "30d": 0.0,
                "profile": s.get("profile") or "—", "dominant_route": _attr(s, "route"),
            })
            if is_today:
                pe["today"] += cost
            if in_7d:
                pe["7d"] += cost
            if in_30d:
                pe["30d"] += cost

        # by profile (the six MS040 profiles)
        prof = s.get("profile")
        if prof in by_profile:
            if is_today:
                by_profile[prof]["today"] += cost
            if in_7d:
                by_profile[prof]["7d"] += cost
            if in_30d:
                by_profile[prof]["30d"] += cost

        # by model (attributes.model)
        model = _attr(s, "model")
        if model and is_today:
            me = by_model.setdefault(str(model), {
                "name": str(model), "role": _attr(s, "role") or "—",
                "today": 0.0, "tokens_in": 0.0, "tokens_out": 0.0,
            })
            me["today"] += cost
            ti = _num(_attr(s, "tokens_in"))
            to = _num(_attr(s, "tokens_out"))
            if ti is not None:
                me["tokens_in"] += ti
            if to is not None:
                me["tokens_out"] += to

    # finalise model rows ($/Mtok)
    models = []
    for m in by_model.values():
        toks = (m["tokens_in"] or 0) + (m["tokens_out"] or 0)
        m["usd_per_mtok"] = round(m["today"] / (toks / 1_000_000), 4) if toks > 0 else None
        m["tokens_in"] = int(m["tokens_in"]) or None
        m["tokens_out"] = int(m["tokens_out"]) or None
        m["today"] = round(m["today"], 6)
        models.append(m)
    models.sort(key=lambda m: m["today"], reverse=True)

    # 30-day trend (oldest→newest), only days within 30d window
    trend = []
    for i in range(29, -1, -1):
        day = (now.timestamp() - i * 86400)
        ds = datetime.fromtimestamp(day, tz=timezone.utc).strftime("%Y-%m-%d")
        trend.append({"date": ds, "spend": round(by_date.get(ds, 0.0), 6)})

    budget = policy.get("daily_budget_usd")
    today_block = {
        "spend": round(today_spend, 6),
        "budget": budget,
        "requests": today_requests,
        "avg_req_cost": round(today_spend / today_requests, 6) if today_requests else None,
        "per_request_max": round(today_max_req, 6) if today_requests else None,
        "eod_forecast": round(today_spend / day_frac, 6) if today_spend else 0.0,
    }

    projects = sorted(by_project.values(), key=lambda p: p["30d"], reverse=True)
    for p in projects:
        for k in ("today", "7d", "30d"):
            p[k] = round(p[k], 6)
    for p in by_profile.values():
        for k in ("today", "7d", "30d"):
            p[k] = round(p[k], 6)

    return {
        "schema_version": SCHEMA_VERSION,
        "today": today_block,
        "projects": projects,
        "profiles": by_profile,
        "models": models,
        "trend30d": trend,
        "policy": policy,
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="cost aggregation core (M060 D-04)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("summary", "policy", "today"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "summary"
    if cmd == "policy":
        _print(load_policy())
    elif cmd == "today":
        _print(summary()["today"])
    else:
        _print(summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
