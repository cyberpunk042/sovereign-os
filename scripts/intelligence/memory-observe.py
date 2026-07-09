#!/usr/bin/env python3
"""scripts/intelligence/memory-observe.py — the M028 observation event stream
(SDD-069) — auto-feed admission from the real OCSF span log.

Closes the recurring SB-077 "no real agent-memory source" gap. SDD-064 (admission) +
SDD-066 (janitor) + SDD-068 (navigator) built the write/enrich/query triad, but admission
observations were always CLI/fixture-fed. This engine tails the ONE real, append-only,
multi-producer event stream — `/var/log/sovereign-os/spans.jsonl` (the M049 OCSF-5001 span
log that 13 emitters already write) — maps each new span to a memory admission, and feeds
the existing `memory-admit.admit()` value-gate (R04672 — not every observation becomes
memory; the gate decides).

  memory-changes observe run [--confirm] [--limit N]   consume new spans → admissions
  memory-changes observe status                         cursor position + would-observe (read-only)

COMPREHENSIVE mapping (span operation/severity/attributes → trigger/type; summaries built
from REAL attributes only, never fabricated):
  session_reap→task-outcome/episodic · session_save_state→high-value-reuse/procedural ·
  cockpit_action exit0→tool-worked/procedural · cockpit_action fail/error→model-mistake/
  episodic · *_decision→preference/value · adapter_gate_advance→task-outcome/procedural ·
  dashboard_toggle→preference/value · any other error/critical→model-mistake/episodic.

FEEDBACK-LOOP EXCLUSION (critical): any span whose `operation` starts with `memory_` is
skipped — the engine's own admit/advance/forget/decision spans are NEVER re-observed.

IDEMPOTENCY: a persisted `observe.cursor` (`SOVEREIGN_OS_MEMORY_OBSERVE_CURSOR`) =
{"ts": <max start_ts processed>, "seen": [<span_ids at that exact ts>]}. A run processes
spans with start_ts > ts OR (== ts AND span_id ∉ seen), then advances the cursor. admit's
`_is_duplicate(type,summary)` is the content backstop.

R10212: mutates the store (via admit) → CLI/timer-only, never a web control. SB-077:
empty/absent log → 0 admitted (honest-defer, never fabricated). DRY-RUN default (--confirm
+ unset SOVEREIGN_OS_DRY_RUN to mint; the timer runs live). MS003 deferred to selfdef.

stdlib-only. Exit: 0 ok · 1 write · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

_INTEL = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# The admission engine (the sink) + its shared store (for the span-log path + helpers).
_admit = _load(_INTEL / "memory-admit.py", "_memory_admit_for_observe")
_store = _admit._store

CURSOR = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_OBSERVE_CURSOR", "/var/lib/sovereign-os/memory/observe.cursor"))
_ERROR_SEV = frozenset({"error", "critical"})
_ACTOR = "observer"


def _spans() -> list[dict[str, Any]]:
    """Read the OCSF span log (JSONL). Honest-defer: absent/unreadable → []."""
    path = _store.SPAN_STORE
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(d, dict):
                out.append(d)
    except OSError:
        return []
    return out


def _read_cursor() -> tuple[str | None, set[str]]:
    d = _store._read_json(CURSOR, {})
    if not isinstance(d, dict):
        return None, set()
    ts = d.get("ts")
    seen = d.get("seen")
    return (ts if isinstance(ts, str) else None,
            set(seen) if isinstance(seen, list) else set())


def _write_cursor(ts: str, seen: set[str]) -> None:
    _store._atomic_write(CURSOR, {"ts": ts, "seen": sorted(seen), "updated": _store._now()})


def _new_spans(cursor_ts: str | None, seen: set[str]) -> list[dict[str, Any]]:
    """Spans past the cursor high-water-mark, sorted (start_ts, span_id) ascending."""
    result = []
    for s in _spans():
        ts = s.get("start_ts")
        if not isinstance(ts, str):
            continue
        sid = s.get("span_id")
        if cursor_ts is None or ts > cursor_ts or (ts == cursor_ts and sid not in seen):
            result.append(s)
    result.sort(key=lambda s: (s.get("start_ts") or "", str(s.get("span_id") or "")))
    return result


def _compact_attrs(attrs: dict[str, Any]) -> str:
    return ", ".join(f"{k}={attrs[k]}" for k in sorted(attrs)
                     if attrs[k] is not None and k not in ("op",))


def _map_span(span: dict[str, Any]) -> tuple[int, str, str] | None:
    """Map an OCSF span → (memory_type, store-if trigger, summary), or None when the
    event is not memory-worthy. Feedback-loop guard: `^memory_` operations are skipped
    (the engine's own admit/advance/forget/decision spans). Summaries use REAL attribute
    values only (SB-077 — never fabricated)."""
    op = str(span.get("operation") or "")
    if op.startswith("memory_"):
        return None  # never re-observe our own admissions (no feedback loop)
    attrs = span.get("attributes") if isinstance(span.get("attributes"), dict) else {}
    sev = str(span.get("severity") or "info")
    kv = _compact_attrs(attrs)

    def summ(label: str) -> str:
        return f"{label}: {kv}" if kv else label

    if op == "session_reap":
        return 2, "task-outcome", summ("session reaped")
    if op == "session_save_state":
        return 4, "high-value-reuse", summ("session checkpoint saved")
    if op == "cockpit_action":
        ec = attrs.get("exit_code")
        if ec == 0:
            return 4, "tool-worked", summ("cockpit action ok")
        return 2, "model-mistake", summ("cockpit action failed")
    if op == "adapter_gate_advance":
        return 4, "task-outcome", summ("adapter gate advanced")
    if op == "dashboard_toggle":
        return 6, "preference", summ("dashboard toggled")
    if op.endswith("_decision"):   # approval/adapter/session (memory_* already excluded)
        return 6, "preference", summ(op)
    if sev in _ERROR_SEV:
        return 2, "model-mistake", summ(f"error: {op}")
    return None


def _is_dry(confirm: bool) -> bool:
    return (not confirm) or _store.os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"


def run(*, confirm: bool = False, limit: int | None = None,
        actor: str = _ACTOR) -> dict[str, Any]:
    """Consume new spans past the cursor, map each to an admission, and feed admit().
    DRY-RUN (no --confirm) previews without minting OR advancing the cursor."""
    cursor_ts, seen = _read_cursor()
    new = _new_spans(cursor_ts, seen)
    if limit is not None:
        try:
            new = new[:max(0, int(limit))]
        except (TypeError, ValueError):
            return {"ok": False, "code": 2, "error": f"invalid --limit {limit!r}"}
    dry = _is_dry(confirm)
    admitted: list[str] = []
    mapped = 0
    deduped = 0
    skipped = 0
    for s in new:
        m = _map_span(s)
        if m is None:
            skipped += 1
            continue
        mapped += 1
        mtype, trigger, summary = m
        r = _admit.admit(mtype, summary, trigger=trigger, actor=actor, confirm=confirm)
        if r.get("admitted") and r.get("id"):
            admitted.append(r["id"])
        elif r.get("admitted") is False and r.get("reason") == "duplicate":
            deduped += 1
    # advance the cursor ONLY on a live run (dry-run is a preview — never consumes).
    if not dry and new:
        new_ts = max(str(s.get("start_ts")) for s in new)
        new_seen = {str(s.get("span_id")) for s in new
                    if str(s.get("start_ts")) == new_ts and s.get("span_id")}
        if cursor_ts is not None and new_ts == cursor_ts:
            new_seen |= seen
        try:
            _write_cursor(new_ts, new_seen)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"cursor write failed: {e}"}
    return {"ok": True, "code": 200, "dry_run": dry, "observed": len(new),
            "mapped": mapped, "admitted": admitted, "admitted_count": len(admitted),
            "deduped": deduped, "skipped": skipped,
            "cursor_advanced": (not dry and bool(new))}


def status() -> dict[str, Any]:
    """Read-only — the cursor position + how many spans would be observed next."""
    cursor_ts, seen = _read_cursor()
    new = _new_spans(cursor_ts, seen)
    would = sum(1 for s in new if _map_span(s) is not None)
    return {"ok": True, "code": 200, "cursor_ts": cursor_ts, "seen_at_cursor": len(seen),
            "pending_spans": len(new), "would_admit": would,
            "span_log": str(_store.SPAN_STORE)}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M028 observation event stream (SDD-069)")
    sub = ap.add_subparsers(dest="cmd")
    rn = sub.add_parser("run")
    rn.add_argument("--confirm", action="store_true")
    rn.add_argument("--limit", type=int, default=None)
    rn.add_argument("--actor", default=_ACTOR)
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        r = run(confirm=args.confirm, limit=args.limit, actor=args.actor)
    elif args.cmd == "status":
        r = status()
    else:
        ap.error("a subverb is required: run|status")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
