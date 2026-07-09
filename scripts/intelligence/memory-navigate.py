#!/usr/bin/env python3
"""scripts/intelligence/memory-navigate.py — the M028 RLM memory navigator
(M00472, SDD-068) + the M00469 temporal query verbs.

The QUERY side of the Memory OS. SDD-064 (admission) + SDD-066 (SLM janitor) built the
write/enrich side; nothing read the store back intelligently. This is the RLM navigator:
per R04700-R04704 it does NOT dump memory into the prompt — it gets the memory
ENVIRONMENT, SELECTS slices, spawns CHILD CALLS over the selected slices (via the SDD-062
loopback engine), and returns a COMPOSED answer.

  memory-changes navigate "<query>" [--type N] [--stage S] [--topic T]
                          [--verb <temporal>] [--at <ISO-T>] [--limit K] [--no-compose]

Pipeline (R04701-R04704):
  1. environment — active entries + slice axes (type/stage/topic/tags/edges/temporal).
  2. select     — rank by token-overlap of the query vs summary+tags+topic+derived_facts
                  + optional --type/--stage/--topic filters; cap top-K (only the SELECTED
                  slices ever reach the LM, one per child call — R04700, no dump).
  3. child calls — one bounded prompt.run() per selected slice → a per-slice finding.
  4. compose    — a final prompt.run() over the findings → the answer.

M00469 temporal verbs (`--verb`), mapped to REAL substrate, HONEST-DEFER where absent
(SB-077): changed (updated!=created) / true-then --at T (created<=T) / true-now
(state==active) / last-verified (the `verified` bool + `updated` caveat — no verified_at
timestamp exists) / contradicted-by (HONEST-DEFER empty — no contradiction edge-kind).

READ-COMPUTE: this NEVER mutates the store (no _atomic_write(STORE), no ledger, no
reconcile) — the store is byte-identical after a navigate. HONEST-DEFER (SB-077): an
unreachable LM → the selected slices WITHOUT a composed answer (never fabricated); an
empty store / no match → an empty result. R10212: read-only; the daemon exposes it as a
read-only GET. MS003 signing deferred to selfdef.

stdlib-only. Exit: 0 ok · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INTEL = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Reuse the single store the D-07 admit/janitor/store already own (read-only here).
_store = _load(_INTEL / "memory-store.py", "_memory_store_for_navigate")

# The SDD-062 loopback inference engine, reused as the child-call + compose LM.
try:
    _prompt = _load(_INTEL.parent / "inference" / "prompt.py", "_prompt_for_navigate")
except Exception:  # noqa: BLE001 — LM optional; --no-compose + honest-defer never need it
    _prompt = None

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of to and or is was are were for in on at it this that with as by "
    "be been being from into over than then them they you your our what which".split())
_TEMPORAL_VERBS = ("true-then", "true-now", "changed", "contradicted-by", "last-verified")
_DEFAULT_LIMIT = 5
_MAX_CHILD_CHARS = 2000  # bound each slice sent to a child call (R04700 — no dump)


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall((s or "").lower()) if len(w) >= 3 and w not in _STOP}


def _active() -> list[dict[str, Any]]:
    return [e for e in _store._entries().values()
            if isinstance(e, dict) and e.get("state") == "active"]


def _searchable(e: dict[str, Any]) -> str:
    parts = [str(e.get("summary", "")), str(e.get("topic", "") or "")]
    tags = e.get("tags")
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    facts = e.get("derived_facts")
    if isinstance(facts, list):
        parts.extend(str(f) for f in facts)
    return " ".join(parts)


def _slice_view(e: dict[str, Any]) -> dict[str, Any]:
    """A compact slice projection for the response — NOT the whole entry dump."""
    edges = e.get("edges")
    return {"id": e.get("id"), "type": e.get("type"), "stage": e.get("stage"),
            "summary": e.get("summary"), "topic": e.get("topic"),
            "tags": e.get("tags"), "derived_facts": e.get("derived_facts"),
            "edges": len(edges) if isinstance(edges, list) else 0,
            "created": e.get("created"), "updated": e.get("updated")}


def _slice_text(e: dict[str, Any]) -> str:
    """The bounded slice text sent to a child LM call (R04700 — one slice, not a dump)."""
    bits = [f"summary: {e.get('summary', '')}"]
    if e.get("topic"):
        bits.append(f"topic: {e['topic']}")
    facts = e.get("derived_facts")
    if isinstance(facts, list) and facts:
        bits.append("facts: " + "; ".join(str(f) for f in facts))
    return "\n".join(bits)[:_MAX_CHILD_CHARS]


def _rank(query: str, pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic relevance rank (R04701 — select, don't dump). With query tokens:
    keep entries with a non-zero overlap, score desc, newest first. Without a query:
    keep all, newest first."""
    qtok = _tokens(query)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for e in pool:
        score = len(qtok & _tokens(_searchable(e))) if qtok else 0
        if qtok and score == 0:
            continue
        scored.append((score, str(e.get("created", "")), e))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [e for _, _, e in scored]


def _matches(e: dict[str, Any], mtype: int | None, stage: str | None,
             topic: str | None) -> bool:
    if mtype is not None and e.get("type") != mtype:
        return False
    if stage is not None and e.get("stage") != stage:
        return False
    if topic is not None and topic.lower() not in str(e.get("topic", "") or "").lower():
        return False
    return True


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t


def _temporal(verb: str, pool: list[dict[str, Any]], at: str | None) -> dict[str, Any]:
    """Apply an M00469 temporal verb over the active pool. Returns
    {entries:[...]} or, where the substrate is absent, {deferred, reason} (SB-077)."""
    if verb == "true-now":
        return {"entries": pool}  # already state==active
    if verb == "changed":
        return {"entries": [e for e in pool
                            if e.get("updated") and e.get("created")
                            and e["updated"] != e["created"]]}
    if verb == "true-then":
        t = _parse_ts(at)
        if t is None:
            return {"usage": "true-then requires --at <ISO-8601 timestamp>"}
        out = []
        for e in pool:
            c = _parse_ts(e.get("created"))
            if c is not None and c <= t:
                out.append(e)
        return {"entries": out,
                "note": "created<=T over active entries; point-in-time state is limited "
                "to the forget/undo ledger (partial substrate)"}
    if verb == "last-verified":
        return {"entries": [e for e in pool if e.get("verified") is True],
                "note": "the `verified` flag is a bool — no verified_at timestamp exists "
                "in the store, so this reports verified-ness, not a verification time "
                "(honest partial substrate, SB-077)"}
    if verb == "contradicted-by":
        # No `contradicts` edge-kind / contradiction substrate exists (edges are
        # kind:"related" only) — HONEST-DEFER, never fabricate a contradiction.
        return {"deferred": True, "entries": [],
                "reason": "no contradiction edges in store (edges are kind:'related' "
                "only); a `contradicts` edge-kind is Stage-N"}
    return {"usage": f"unknown temporal verb {verb!r} (use {list(_TEMPORAL_VERBS)})"}


# ── the SLM child-call plumbing (SDD-062 engine; honest-defer per SB-077) ───────

def _slm(text: str) -> dict[str, Any]:
    """Collect prompt.run()'s token stream into a string; honest-defer (never
    fabricates) when the engine is unavailable / the router errors / empty."""
    if _prompt is None:
        return {"ok": False, "deferred": True, "reason": "inference engine unavailable"}
    buf: list[str] = []
    err: str | None = None
    try:
        for ev in _prompt.run(text):
            k = ev.get("type")
            if k == "token":
                buf.append(str(ev.get("text", "")))
            elif k == "error":
                err = str(ev.get("error"))
    except Exception as e:  # noqa: BLE001 — any engine failure → honest-defer, never crash
        return {"ok": False, "deferred": True, "reason": f"slm invocation failed: {e}"}
    if err is not None:
        return {"ok": False, "deferred": True, "reason": err}
    out = "".join(buf).strip()
    if not out:
        return {"ok": False, "deferred": True, "reason": "empty completion"}
    return {"ok": True, "text": out}


def navigate(query: str, *, mtype: int | None = None, stage: str | None = None,
             topic: str | None = None, verb: str | None = None, at: str | None = None,
             limit: int = _DEFAULT_LIMIT, compose: bool = True) -> dict[str, Any]:
    """The RLM navigator (M00472): environment → select slices → child calls over slices
    → composed answer. READ-COMPUTE — never mutates the store. Honest-defer (SB-077) when
    the LM is unreachable or the store is empty."""
    query = query or ""
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        return {"ok": False, "code": 2, "error": f"invalid --limit {limit!r}"}
    pool = _active()
    tnote: str | None = None
    if verb is not None:
        if verb not in _TEMPORAL_VERBS:
            return {"ok": False, "code": 2,
                    "error": f"unknown --verb {verb!r} (use {list(_TEMPORAL_VERBS)})"}
        t = _temporal(verb, pool, at)
        if "usage" in t:
            return {"ok": False, "code": 2, "error": t["usage"]}
        if t.get("deferred"):
            return {"ok": True, "code": 200, "query": query, "verb": verb,
                    "entries": [], "count": 0, "answer": None, "deferred": True,
                    "reason": t.get("reason"),
                    "note": "honest-defer (SB-077) — temporal substrate absent"}
        pool = t.get("entries", [])
        tnote = t.get("note")
    pool = [e for e in pool if _matches(e, mtype, stage, topic)]
    ranked = _rank(query, pool)[:limit]
    slices = [_slice_view(e) for e in ranked]
    base: dict[str, Any] = {"ok": True, "code": 200, "query": query, "count": len(slices),
                            "slices": slices}
    if verb is not None:
        base["verb"] = verb
    if tnote:
        base["temporal_note"] = tnote
    # deterministic-only paths — no LM.
    if not compose or not query.strip():
        base["answer"] = None
        base["composed"] = False
        return base
    if not ranked:
        base["answer"] = None
        base["note"] = "no memory matched"
        return base
    # child calls over the selected slices (R04703) — one per slice, honest-defer per hop.
    findings: list[dict[str, Any]] = []
    for e in ranked:
        r = _slm(f"Relative to the query {query!r}, state in one sentence what this "
                 f"memory contributes (or 'nothing'):\n{_slice_text(e)}")
        if not r.get("ok"):
            return {**base, "answer": None, "findings": findings, "deferred": True,
                    "reason": r.get("reason"),
                    "note": "honest-defer (SB-077) — LM unreachable; slices returned "
                    "without a composed answer"}
        findings.append({"id": e.get("id"), "finding": r["text"]})
    # compose (R04704).
    findings_text = "\n".join(f"- ({f['id']}) {f['finding']}" for f in findings)
    comp = _slm(f"Compose a concise answer to the query {query!r} using only these "
                f"memory findings:\n{findings_text}")
    if not comp.get("ok"):
        return {**base, "answer": None, "findings": findings, "deferred": True,
                "reason": comp.get("reason"),
                "note": "honest-defer (SB-077) — compose LM unreachable"}
    return {**base, "findings": findings, "answer": comp["text"], "composed": True}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M028 RLM memory navigator (SDD-068)")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--type", type=int, default=None, dest="mtype")
    ap.add_argument("--stage", default=None)
    ap.add_argument("--topic", default=None)
    ap.add_argument("--verb", default=None, choices=list(_TEMPORAL_VERBS))
    ap.add_argument("--at", default=None, help="ISO-8601 timestamp for --verb true-then")
    ap.add_argument("--limit", type=int, default=_DEFAULT_LIMIT)
    ap.add_argument("--no-compose", action="store_true")
    args = ap.parse_args(argv)
    r = navigate(args.query, mtype=args.mtype, stage=args.stage, topic=args.topic,
                 verb=args.verb, at=args.at, limit=args.limit, compose=not args.no_compose)
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 2))


if __name__ == "__main__":
    sys.exit(main())
