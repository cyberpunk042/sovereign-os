#!/usr/bin/env python3
"""scripts/observability/trace-store.py — M049 13-field span store + query
core (M060 D-05 / R10083-R10087).

The data model behind the D-05 traces cockpit dashboard. Reads the
observability fabric's append-only span log (JSONL, one span per line) and
provides search / per-trace assembly / summary aggregation over the M049
13-field span schema:

  M049 13-field span (R08191-R08203, frontend line 110 verbatim):
    trace_id · span_id · parent_span_id · operation · start_ts ·
    duration_ms · severity · attributes · ocsf_class · actor · profile ·
    signature · schema_version
  (the `attributes` map carries the M049 GenAI content fields — model /
  provider / hardware / tokens / latency / cost / risk / memory_refs /
  tool_refs / policy_result / branch_id — per R08191-R08203.)

  OCSF 16-event taxonomy (selfdef MS026, the 5 surfaced classes):
    1001 System Activity · 1003 Audit Activity · 2004 Detection Finding ·
    4001 Network Activity · 5001 Configuration Change

Sovereignty: stdlib-only, zero added deps. The span log path is
env-configurable and follows the established /var/log/sovereign-os/*.jsonl
convention (modules.jsonl, notify.jsonl). Absent/empty store → empty result
+ zero summary (the dashboard shows "no spans match filter"), NEVER a crash.
This is the `core` surface of the §1g 8-surface ladder for the traces
module; `scripts/operator/traces-api.py` serves it, `sovereign-osctl traces`
drives it ad-hoc, the D-05 webapp renders it.

  trace-store.py spans   [--q Q] [--severity S] [--ocsf-class C] [--window N] [--json]
  trace-store.py trace   <trace_id> [--json]
  trace-store.py summary [--window N] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# 13-field span schema (M049 R08191-R08203 + D-05 frontend contract). Every
# emitted span is normalised to carry these keys (missing → null).
SPAN_FIELDS = (
    "trace_id", "span_id", "parent_span_id", "operation", "start_ts",
    "duration_ms", "severity", "attributes", "ocsf_class", "actor",
    "profile", "signature", "schema_version",
)

# OCSF classes the D-05 taxonomy panel counts (selfdef MS026).
OCSF_CLASSES = ("1001", "1003", "2004", "4001", "5001")

ERROR_SEVERITIES = frozenset({"critical", "error"})

SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl",
))
# Cap how many lines we read so a runaway log never OOMs the daemon. The
# dashboard windows by time anyway; this bounds worst-case work.
MAX_SPANS = int(os.environ.get("SOVEREIGN_OS_SPAN_STORE_MAX", "50000"))


def _now_ms() -> float:
    return time.time() * 1000.0


def _coerce_start_ms(ts: Any) -> float | None:
    """Span start_ts may be epoch-ms (int/float) or ISO-8601 string. Returns
    epoch-ms or None when unparseable."""
    if isinstance(ts, (int, float)):
        # Heuristic: seconds vs ms (anything < year-2001 in ms → treat as s).
        return float(ts) * 1000.0 if ts < 1_000_000_000_000 else float(ts)
    if isinstance(ts, str):
        s = ts.strip().replace("Z", "+00:00")
        try:
            from datetime import datetime
            return datetime.fromisoformat(s).timestamp() * 1000.0
        except (ValueError, OSError):
            return None
    return None


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a raw log record onto the 13-field schema (missing → null)."""
    span = {k: raw.get(k) for k in SPAN_FIELDS}
    if span.get("schema_version") is None:
        span["schema_version"] = SCHEMA_VERSION
    if span.get("attributes") is None:
        span["attributes"] = {}
    # ocsf_class is rendered as a string by the dashboard pill.
    if span.get("ocsf_class") is not None:
        span["ocsf_class"] = str(span["ocsf_class"])
    # carry the optional OCSF payload (detail panel reads span.ocsf_payload)
    if "ocsf_payload" in raw:
        span["ocsf_payload"] = raw["ocsf_payload"]
    return span


def load_spans(store: Path = SPAN_STORE) -> list[dict[str, Any]]:
    """Read the JSONL span log → list of normalised spans. Tolerates blank /
    malformed lines (skipped). Absent store → empty list (graceful)."""
    if not store.is_file():
        return []
    spans: list[dict[str, Any]] = []
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
                if isinstance(rec, dict) and rec.get("span_id") and rec.get("trace_id"):
                    spans.append(_normalise(rec))
    except OSError:
        return []
    # Most-recent-last in the file; keep the newest MAX_SPANS.
    return spans[-MAX_SPANS:]


def _matches(span: dict[str, Any], q: str) -> bool:
    """Case-insensitive substring match across trace_id / span_id / operation
    + every attribute key and value (the dashboard's documented search scope)."""
    if not q:
        return True
    ql = q.lower()
    for key in ("trace_id", "span_id", "operation", "actor", "profile"):
        v = span.get(key)
        if v and ql in str(v).lower():
            return True
    attrs = span.get("attributes") or {}
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            if ql in str(k).lower() or ql in str(v).lower():
                return True
    return False


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1))))
    return round(s[idx], 3)


def _summary(spans: list[dict[str, Any]]) -> dict[str, Any]:
    durs = [float(s["duration_ms"]) for s in spans
            if isinstance(s.get("duration_ms"), (int, float))]
    ocsf = {c: 0 for c in OCSF_CLASSES}
    errors = 0
    for s in spans:
        if str(s.get("severity") or "").lower() in ERROR_SEVERITIES:
            errors += 1
        c = s.get("ocsf_class")
        if c in ocsf:
            ocsf[c] += 1
    return {
        "total": len(spans),
        "errors": errors,
        "p95_ms": _percentile(durs, 95),
        "ocsf": ocsf,
    }


def query_spans(q: str = "", severity: str = "", ocsf_class: str = "",
                window_secs: int = 3600, limit: int = 500,
                store: Path = SPAN_STORE) -> dict[str, Any]:
    """The /api/traces/spans contract: filter by time window + text + severity
    + OCSF class, newest first, plus the summary aggregate the dashboard reads."""
    cutoff = _now_ms() - (window_secs * 1000.0)
    out: list[dict[str, Any]] = []
    for s in load_spans(store):
        start = _coerce_start_ms(s.get("start_ts"))
        if start is not None and start < cutoff:
            continue
        if severity and str(s.get("severity") or "").lower() != severity.lower():
            continue
        if ocsf_class and s.get("ocsf_class") != ocsf_class:
            continue
        if not _matches(s, q):
            continue
        out.append(s)
    out.sort(key=lambda s: _coerce_start_ms(s.get("start_ts")) or 0.0, reverse=True)
    summary = _summary(out)
    return {"spans": out[:limit], "summary": summary}


def get_trace(trace_id: str, store: Path = SPAN_STORE) -> dict[str, Any]:
    """The /api/traces/<trace_id> contract: every span in one trace, oldest
    first (so the dashboard span-tree builds parent→child top-down)."""
    spans = [s for s in load_spans(store) if s.get("trace_id") == trace_id]
    spans.sort(key=lambda s: _coerce_start_ms(s.get("start_ts")) or 0.0)
    return {"trace_id": trace_id, "spans": spans}


def store_signature() -> tuple[int, float]:
    """(size_bytes, mtime) of the span store, or (0, 0.0) when absent — used
    by the SSE stream to emit `span-added` only when the log actually grows."""
    try:
        st = SPAN_STORE.stat()
        return st.st_size, st.st_mtime
    except OSError:
        return 0, 0.0


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="M049 13-field span store + query core (M060 D-05)")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("spans")
    sp.add_argument("--q", default="")
    sp.add_argument("--severity", default="")
    sp.add_argument("--ocsf-class", default="")
    sp.add_argument("--window", type=int, default=3600)
    sp.add_argument("--json", action="store_true")
    tr = sub.add_parser("trace")
    tr.add_argument("trace_id")
    tr.add_argument("--json", action="store_true")
    sm = sub.add_parser("summary")
    sm.add_argument("--window", type=int, default=3600)
    sm.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "summary"
    if cmd == "spans":
        _print(query_spans(args.q, args.severity, args.ocsf_class, args.window))
    elif cmd == "trace":
        _print(get_trace(args.trace_id))
    else:
        window = getattr(args, "window", 3600)
        _print(query_spans("", "", "", window)["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
