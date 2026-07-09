#!/usr/bin/env python3
"""scripts/intelligence/memory-janitor.py — the M028 SLM memory janitor
(M00473, SDD-066) — the 7 cheap maintenance jobs.

SDD-064 built the admission engine + `advance(mem-id)`, but `advance()` is a PURE
stage-label bump with ZERO per-stage work. This is the M00473 SLM memory janitor: the
7 jobs (milestone R04709-R04715) that actually enrich a memory entry with the E0261
ground-truth-layer fields.

  memory-changes janitor dedup           [--confirm]   R04711  (global)
  memory-changes janitor edges           [--confirm]   R04713  (global)
  memory-changes janitor tag       [id|--all] [--confirm]  R04710
  memory-changes janitor extract-facts [id|--all] [--confirm]  R04709  (SLM)
  memory-changes janitor topic         [id|--all] [--confirm]  R04712  (SLM)
  memory-changes janitor summarize     [id|--all] [--confirm]  R04715  (SLM)
  memory-changes janitor classify      [id|--all] [--confirm]  R04714  (SLM)
  memory-changes janitor advance <id>    [--confirm]   (run the current stage's job,
                                                        then delegate the label bump)

Two job classes:
  DETERMINISTIC / always-real (no backend) — dedup / graph-edges / tag / advance-effects.
  SLM-routed (SDD-062 `scripts/inference/prompt.py` loopback engine) — extract-facts /
    topic-label / summarize / classify-failure. HONEST-DEFER (SB-077): an unreachable
    router leaves the field UNSET + reports `{deferred:True, reason}` — never fabricates.

All new entry fields are ADDITIVE (derived_facts / topic / summary_short / edges / tags /
failure_class / verified / promoted / freshness / dedup_of / state:"duplicate") — no
existing field (id/type/stage/summary/state/created/updated) changes shape. dedup MARKS
`state:"duplicate"` + `dedup_of` — it NEVER hard-deletes (reversible, like the SDD-065
reaper archive + the forget soft-delete). ONE owner of the `stage` field — advance-effects
delegates the label bump to `memory-admit.advance`. Every mutation atomic-writes +
`reconcile()`s the D-07 projection. R10212: CLI/timer-only (the store is mutated → never a
web control); `memory-changes.py` stays a pure reader (405 API). MS003 deferred to selfdef.

stdlib-only. DRY-RUN default (--confirm to apply). Exit: 0 ok/dry · 1 write · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

_INTEL = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Reuse the single store the D-07 forget/undo/purge/reconcile/admit already own.
_store = _load(_INTEL / "memory-store.py", "_memory_store_for_janitor")
# The admission engine owns `advance` (the sole `stage`-field mutator) — advance-effects
# delegates the label bump to it so there is no duplicate lifecycle-mutation logic.
_admit = _load(_INTEL / "memory-admit.py", "_memory_admit_for_janitor")
# Share the SINGLE store instance — `_admit.advance` must read/write the EXACT store
# module the janitor mutates (one store, one lock, one config path — so a monkeypatched
# or env-configured STORE reaches both). Without this, `_admit` holds a second, separately
# loaded memory-store whose default paths would diverge from the janitor's.
_admit._store = _store

# The SDD-062 loopback inference engine, reused as the "SLM". Best-effort — a load
# failure or an unreachable router → honest-defer (SB-077); the janitor never fabricates.
try:
    _prompt = _load(_INTEL.parent / "inference" / "prompt.py", "_prompt_for_janitor")
except Exception:  # noqa: BLE001 — SLM is optional; deterministic jobs never need it
    _prompt = None

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of to and or is was are were for in on at it this that with as by "
    "be been being from into over than then them they you your our".split())
_EDGE_FLOOR = 2   # min shared tokens (or a shared topic) to propose a `related` edge
_MAX_TAGS = 8


def _normalize(s: str) -> str:
    return " ".join((s or "").lower().split())


def _tokens(s: str) -> set[str]:
    return {w for w in _WORD.findall((s or "").lower()) if len(w) >= 3 and w not in _STOP}


def _dry(confirm: bool) -> tuple[bool, str]:
    """(is_dry_run, why) — DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    if not confirm:
        return True, "no --confirm"
    if _store.os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
        return True, "SOVEREIGN_OS_DRY_RUN=1"
    return False, ""


def _active(ents: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(mid, e) for mid, e in ents.items()
            if isinstance(e, dict) and e.get("state") == "active"]


# ── SLM plumbing (SDD-062 loopback engine; honest-defer per SB-077) ────────────

def _slm(text: str) -> dict[str, Any]:
    """Collect `prompt.run()`'s token stream into a string. Honest-defer (never
    fabricates) when the engine is unavailable / the router is unreachable / the
    completion is empty."""
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


# The 4 SLM jobs: (field, prompt template, transform of the completion text).
def _facts(t: str) -> list[str]:
    return [ln.strip("-* \t") for ln in t.splitlines() if ln.strip("-* \t")] or [t]


_SLM_SPEC: dict[str, tuple[str, str, Callable[[str], Any]]] = {
    "extract-facts": ("derived_facts",
                      "Extract the key facts from this memory as short bullet lines:\n{s}",
                      _facts),
    "topic": ("topic", "Give one short topic label (2-4 words) for this memory:\n{s}",
              lambda t: t.splitlines()[0].strip()),
    "summarize": ("summary_short", "Summarize this memory in one short sentence:\n{s}",
                  lambda t: t.strip()),
    "classify": ("failure_class",
                 "Classify the failure mode of this memory in 1-3 words:\n{s}",
                 lambda t: t.splitlines()[0].strip()),
}


def _write_field(mem_id: str, field: str, value: Any, *, job: str,
                 actor: str) -> dict[str, Any]:
    """Additive per-entry field write (atomic + span + reconcile)."""
    return _write_fields(mem_id, {field: value}, job=job, actor=actor)


def _write_fields(mem_id: str, updates: dict[str, Any], *, job: str,
                  actor: str) -> dict[str, Any]:
    """Additive per-entry MULTI-field write (atomic + span + reconcile) — e.g. the
    `verify` effect writes `verified` + `verified_at` (SDD-101) in one write."""
    with _store._WRITE_LOCK:
        store = _store._read_json(_store.STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict) or mem_id not in ents:
            return {"ok": False, "code": 2, "id": mem_id,
                    "error": f"no memory entry resolved for {mem_id!r}"}
        for field, value in updates.items():
            ents[mem_id][field] = value
        ents[mem_id]["updated"] = _store._now()
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "id": mem_id, "error": f"write failed: {e}"}
    _store._emit_span(f"janitor-{job}", mem_id, actor, {"fields": list(updates)})
    _store._reconcile_safe()
    fields = list(updates)
    return {"ok": True, "code": 200, "id": mem_id, "job": job,
            "field": fields[0] if len(fields) == 1 else fields,
            "value": updates[fields[0]] if len(fields) == 1 else updates}


def _slm_one(job: str, mem_id: str, *, confirm: bool, actor: str = "operator") -> dict[str, Any]:
    field, tmpl, transform = _SLM_SPEC[job]
    if not _store._SAFE_ID.fullmatch(mem_id or ""):
        return {"ok": False, "code": 2, "error": f"unsafe memory id {mem_id!r} (no '/')"}
    entry = _store._entries().get(mem_id)
    if entry is None:
        return {"ok": False, "code": 2, "id": mem_id,
                "error": f"no memory entry resolved for {mem_id!r}"}
    dry, why = _dry(confirm)
    if dry:
        return {"ok": True, "code": 200, "id": mem_id, "job": job, "dry_run": True,
                "would": {"field": field, "via": "slm"},
                "note": f"DRY-RUN ({why}) — would route the summary through the SLM"}
    res = _slm(tmpl.format(s=entry.get("summary", "")))
    if not res.get("ok"):
        # honest-defer is a correct outcome (ok:True), not an error — SB-077.
        return {"ok": True, "code": 200, "id": mem_id, "job": job, "field": field,
                "deferred": True, "reason": res.get("reason"),
                "note": "honest-defer (SB-077) — SLM unreachable; field left unset"}
    return _write_field(mem_id, field, transform(res["text"]), job=job, actor=actor)


# ── deterministic jobs (always real — no backend) ──────────────────────────────

def tag(mem_id: str, *, confirm: bool, actor: str = "operator") -> dict[str, Any]:
    """R04710 — deterministic token tagging → additive `tags` (idempotent)."""
    if not _store._SAFE_ID.fullmatch(mem_id or ""):
        return {"ok": False, "code": 2, "error": f"unsafe memory id {mem_id!r} (no '/')"}
    entry = _store._entries().get(mem_id)
    if entry is None:
        return {"ok": False, "code": 2, "id": mem_id,
                "error": f"no memory entry resolved for {mem_id!r}"}
    tags = sorted(_tokens(entry.get("summary", "")))[:_MAX_TAGS]
    dry, why = _dry(confirm)
    if dry:
        return {"ok": True, "code": 200, "id": mem_id, "job": "tag", "dry_run": True,
                "would": {"tags": tags}, "note": f"DRY-RUN ({why}) — would set tags"}
    return _write_field(mem_id, "tags", tags, job="tag", actor=actor)


def dedup(*, confirm: bool, actor: str = "operator") -> dict[str, Any]:
    """R04711 — collapse `active` entries with an identical (type, normalized-summary):
    keep the earliest by `created`, mark the rest `state:"duplicate"` + `dedup_of`.
    NEVER hard-deletes (reversible bookkeeping). Idempotent (a `duplicate` is not
    `active`, so it is never re-processed)."""
    groups: dict[tuple[Any, str], list[tuple[str, dict[str, Any]]]] = {}
    for mid, e in _active(_store._entries()):
        groups.setdefault((e.get("type"), _normalize(e.get("summary", ""))), []).append((mid, e))
    marks: list[tuple[str, str]] = []  # (duplicate_id, kept_id)
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda x: str(x[1].get("created", "")))
        kept = members[0][0]
        marks.extend((mid, kept) for mid, _ in members[1:])
    dry, why = _dry(confirm)
    if dry:
        return {"ok": True, "code": 200, "job": "dedup", "dry_run": True,
                "would_mark": [{"id": d, "dedup_of": k} for d, k in marks],
                "count": len(marks),
                "note": f"DRY-RUN ({why}) — would mark {len(marks)} duplicate(s) "
                "(reversible; never hard-deleted)"}
    if not marks:
        return {"ok": True, "code": 200, "job": "dedup", "marked": [], "count": 0,
                "note": "no duplicates"}
    with _store._WRITE_LOCK:
        store = _store._read_json(_store.STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict):
            ents = {}
        for dup_id, kept in marks:
            if dup_id in ents:
                ents[dup_id]["state"] = "duplicate"
                ents[dup_id]["dedup_of"] = kept
                ents[dup_id]["updated"] = _store._now()
        store["entries"] = ents
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    for dup_id, kept in marks:
        _store._emit_span("janitor-dedup", dup_id, actor, {"dedup_of": kept})
    _store._reconcile_safe()
    return {"ok": True, "code": 200, "job": "dedup",
            "marked": [{"id": d, "dedup_of": k} for d, k in marks], "count": len(marks)}


def _related_pairs() -> list[tuple[str, str]]:
    """Active entry pairs sharing a topic OR ≥ _EDGE_FLOOR summary tokens."""
    act = _active(_store._entries())
    toks = {mid: _tokens(e.get("summary", "")) for mid, e in act}
    tops = {mid: e.get("topic") for mid, e in act}
    pairs: list[tuple[str, str]] = []
    for i in range(len(act)):
        a = act[i][0]
        for j in range(i + 1, len(act)):
            b = act[j][0]
            shared_topic = tops[a] and tops[a] == tops[b]
            if shared_topic or len(toks[a] & toks[b]) >= _EDGE_FLOOR:
                pairs.append((a, b))
    return pairs


def _has_edge(entry: dict[str, Any], dst: str, kind: str) -> bool:
    edges = entry.get("edges")
    return isinstance(edges, list) and any(
        isinstance(x, dict) and x.get("to") == dst and x.get("kind") == kind for x in edges)


def _add_edge(ents: dict[str, Any], src: str, dst: str, kind: str = "related") -> bool:
    """Additive graph edge, deduped by (to, kind) — an entry can be BOTH `related` AND
    `contradicts` another (SDD-101)."""
    edges = ents[src].get("edges")
    if not isinstance(edges, list):
        edges = []
    if any(isinstance(x, dict) and x.get("to") == dst and x.get("kind") == kind
           for x in edges):
        return False
    edges.append({"to": dst, "kind": kind})
    ents[src]["edges"] = edges
    return True


def edges(*, confirm: bool, actor: str = "operator") -> dict[str, Any]:
    """R04713 — propose `related` graph edges between active entries sharing a topic
    or a token overlap → additive bidirectional `edges`. Idempotent (an existing edge
    is not re-added)."""
    pairs = _related_pairs()
    dry, why = _dry(confirm)
    if dry:
        return {"ok": True, "code": 200, "job": "edges", "dry_run": True,
                "would_link": [{"a": a, "b": b} for a, b in pairs], "count": len(pairs),
                "note": f"DRY-RUN ({why}) — would propose {len(pairs)} related edge(s)"}
    if not pairs:
        return {"ok": True, "code": 200, "job": "edges", "linked": [], "count": 0,
                "note": "no related pairs"}
    added = 0
    with _store._WRITE_LOCK:
        store = _store._read_json(_store.STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict):
            ents = {}
        for a, b in pairs:
            if a in ents and b in ents:
                added += _add_edge(ents, a, b)
                added += _add_edge(ents, b, a)
        store["entries"] = ents
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    for a, b in pairs:
        _store._emit_span("janitor-edges", a, actor, {"to": b})
    _store._reconcile_safe()
    return {"ok": True, "code": 200, "job": "edges",
            "linked": [{"a": a, "b": b} for a, b in pairs], "count": len(pairs),
            "edges_added": added}


def contradict(*, confirm: bool, actor: str = "janitor") -> dict[str, Any]:
    """SDD-101 — the substrate producer for the M00469 `contradicted-by` navigator verb.
    Deterministic candidate-pairing (active pairs sharing a topic / token-overlap — the
    same _related_pairs same-subject candidates) + SLM CONFIRMATION (honest-defer): one
    bounded `_slm` yes/no per candidate → on "yes" a bidirectional `contradicts` edge.
    HONEST-DEFER (SB-077) — an unreachable router writes NO edge (never fabricates a
    contradiction). Idempotent (an existing `contradicts` edge is not re-proposed)."""
    ents0 = _store._entries()
    # candidate pairs not already marked contradicts (idempotency pre-filter).
    pairs = [(a, b) for a, b in _related_pairs()
             if a in ents0 and b in ents0 and not _has_edge(ents0[a], b, "contradicts")]
    dry, why = _dry(confirm)
    if dry:
        return {"ok": True, "code": 200, "job": "contradict", "dry_run": True,
                "candidates": len(pairs),
                "note": f"DRY-RUN ({why}) — would SLM-judge {len(pairs)} candidate pair(s)"}
    confirmed: list[tuple[str, str]] = []
    deferred = 0
    for a, b in pairs:
        r = _slm("Do these two memories contradict each other? Answer only 'yes' or "
                 f"'no'.\nA: {ents0[a].get('summary', '')}\nB: {ents0[b].get('summary', '')}")
        if not r.get("ok"):
            deferred += 1  # honest-defer — no edge written
            continue
        if r["text"].strip().lower().startswith("yes"):
            confirmed.append((a, b))
    if not confirmed:
        return {"ok": True, "code": 200, "job": "contradict", "linked": [], "count": 0,
                "deferred": deferred,
                "note": "no confirmed contradictions"
                + (" (SLM honest-deferred)" if deferred else "")}
    added = 0
    with _store._WRITE_LOCK:
        store = _store._read_json(_store.STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict):
            ents = {}
        for a, b in confirmed:
            if a in ents and b in ents:
                added += _add_edge(ents, a, b, "contradicts")
                added += _add_edge(ents, b, a, "contradicts")
        store["entries"] = ents
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    for a, b in confirmed:
        _store._emit_span("janitor-contradict", a, actor, {"to": b})
    _store._reconcile_safe()
    return {"ok": True, "code": 200, "job": "contradict",
            "linked": [{"a": a, "b": b} for a, b in confirmed], "count": len(confirmed),
            "edges_added": added, "deferred": deferred}


# ── advance-effects — run the current stage's job, then delegate the label bump ─

def _edges_for(mem_id: str, *, confirm: bool, actor: str) -> dict[str, Any]:
    """The `link`-stage effect for one entry: (re)compute its related edges. Reuses
    the global edges() (idempotent) — narrow enough for the per-entry effect."""
    return edges(confirm=confirm, actor=actor)


_STAGE_EFFECT: dict[str, Callable[..., dict[str, Any]]] = {
    "classify": lambda mid, *, confirm, actor: tag(mid, confirm=confirm, actor=actor),
    "link": _edges_for,
    "extract-facts": lambda mid, *, confirm, actor: _slm_one(
        "extract-facts", mid, confirm=confirm, actor=actor),
    "verify": lambda mid, *, confirm, actor: _write_fields(
        mid, {"verified": True, "verified_at": _store._now()}, job="verify", actor=actor)
        if not _dry(confirm)[0]
        else {"ok": True, "code": 200, "id": mid, "job": "verify", "dry_run": True},
    "promote": lambda mid, *, confirm, actor: _write_field(
        mid, "promoted", True, job="promote", actor=actor) if not _dry(confirm)[0]
        else {"ok": True, "code": 200, "id": mid, "job": "promote", "dry_run": True},
    "decay": lambda mid, *, confirm, actor: _bump_freshness(
        mid, confirm=confirm, actor=actor),
}


def _bump_freshness(mem_id: str, *, confirm: bool, actor: str) -> dict[str, Any]:
    entry = _store._entries().get(mem_id)
    if entry is None:
        return {"ok": False, "code": 2, "id": mem_id, "error": "no entry"}
    nxt = int(entry.get("freshness", 0) or 0) + 1
    if _dry(confirm)[0]:
        return {"ok": True, "code": 200, "id": mem_id, "job": "decay", "dry_run": True,
                "would": {"freshness": nxt}}
    return _write_field(mem_id, "freshness", nxt, job="decay", actor=actor)


def advance(mem_id: str, *, confirm: bool, actor: str = "operator") -> dict[str, Any]:
    """Run the CURRENT stage's janitor job (the per-stage effect), THEN delegate the
    label bump to `memory-admit.advance` (the sole `stage`-field owner). The stage
    effect is best-effort — an SLM honest-defer does NOT block the label progression
    (the field can be filled by a later re-run)."""
    if not _store._SAFE_ID.fullmatch(mem_id or ""):
        return {"ok": False, "code": 2, "error": f"unsafe memory id {mem_id!r} (no '/')"}
    entry = _store._entries().get(mem_id)
    if entry is None:
        return {"ok": False, "code": 2, "id": mem_id,
                "error": f"no memory entry resolved for {mem_id!r}"}
    cur = entry.get("stage")
    effect = _STAGE_EFFECT.get(cur)
    effect_result = effect(mem_id, confirm=confirm, actor=actor) if effect else None
    adv = _admit.advance(mem_id, actor=actor, confirm=confirm)
    ok = bool(adv.get("ok"))
    return {"ok": ok, "code": adv.get("code", 200 if ok else 1), "id": mem_id,
            "stage_from": cur, "effect": effect_result, "advance": adv}


# ── sweep — the recurrent maintenance pass (SDD-071) ───────────────────────────

_STOP_STAGE = _store.os.environ.get("SOVEREIGN_OS_MEMORY_JANITOR_STOP_STAGE", "verify")


def _stage_index(stage: Any) -> int:
    lc = _store._LIFECYCLE_STAGES
    return lc.index(stage) if stage in lc else -1


def sweep(*, confirm: bool, actor: str = "janitor", stop: str | None = None,
          limit: int | None = None) -> dict[str, Any]:
    """SDD-071 — one bounded maintenance pass (the recurrent-timer entry point):
    GLOBAL deterministic enrichment (dedup/tag-all/edges) + SLM enrichment
    (topic/summarize/classify, honest-defer) + a BOUNDED lifecycle advance toward
    STOP_STAGE (default `verify`), ONE step per entry per call. NEVER crosses into
    promote/decay/archive — those value/retention judgments stay operator-gated. The
    label bump is always delegated to `memory-admit.advance` (one owner of `stage`)."""
    stop = stop or _STOP_STAGE
    lc = _store._LIFECYCLE_STAGES
    if stop not in lc:
        return {"ok": False, "code": 2,
                "error": f"unknown --stop stage {stop!r} (use one of {list(lc)})"}
    stop_idx = lc.index(stop)
    # 1. global deterministic enrichment (idempotent).
    d = dedup(confirm=confirm, actor=actor)
    t = _run_per_entry("tag", None, all_=True, confirm=confirm, actor=actor)
    e = edges(confirm=confirm, actor=actor)
    c = contradict(confirm=confirm, actor=actor)  # SDD-101 — SLM-confirmed, honest-defer
    # 2 + 3. per-entry SLM enrichment + bounded lifecycle advance.
    ents = _active(_store._entries())
    if limit is not None:
        try:
            ents = ents[:max(0, int(limit))]
        except (TypeError, ValueError):
            return {"ok": False, "code": 2, "error": f"invalid --limit {limit!r}"}
    enriched = advanced = verified = deferred = 0
    for mid, entry in ents:
        # SLM topic + summarize on entries missing those fields (not stage effects).
        for job, field in (("topic", "topic"), ("summarize", "summary_short")):
            if not entry.get(field):
                r = _slm_one(job, mid, confirm=confirm, actor=actor)
                if r.get("deferred"):
                    deferred += 1
                elif r.get("ok") and not r.get("dry_run"):
                    enriched += 1
        # classify-failure on model-mistake-admitted entries missing it.
        if entry.get("admitted_via") == "model-mistake" and not entry.get("failure_class"):
            r = _slm_one("classify", mid, confirm=confirm, actor=actor)
            if r.get("deferred"):
                deferred += 1
            elif r.get("ok") and not r.get("dry_run"):
                enriched += 1
        # bounded advance (one step toward the stop-stage).
        idx = _stage_index(entry.get("stage"))
        if idx < 0:
            continue
        if idx < stop_idx:
            a = advance(mid, confirm=confirm, actor=actor)
            if a.get("ok") and not (a.get("advance") or {}).get("dry_run"):
                advanced += 1
        elif idx == stop_idx:
            # at the stop: apply the stop-stage effect DIRECTLY (e.g. verify→verified)
            # WITHOUT advancing — the entry is enriched-and-verified but NEVER auto-promoted.
            eff = _STAGE_EFFECT.get(entry.get("stage"))
            if eff is not None:
                r = eff(mid, confirm=confirm, actor=actor)
                if r.get("ok") and not r.get("dry_run"):
                    verified += 1
        # idx > stop_idx: operator-advanced past the auto zone — left untouched.
    return {"ok": True, "code": 200, "job": "sweep", "stop": stop,
            "swept": len(ents), "deduped": d.get("count", 0),
            "tagged": t.get("count", 0), "edged": e.get("count", 0),
            "contradicted": c.get("count", 0), "enriched": enriched,
            "advanced": advanced, "verified_at_stop": verified,
            "deferred": deferred + c.get("deferred", 0),
            "dry_run": _dry(confirm)[0]}


# ── dispatch ───────────────────────────────────────────────────────────────────

_PER_ENTRY = {"tag", "extract-facts", "topic", "summarize", "classify"}


def _run_per_entry(job: str, mem_id: str | None, *, all_: bool, confirm: bool,
                   actor: str) -> dict[str, Any]:
    fn = tag if job == "tag" else (lambda mid, *, confirm, actor:
                                   _slm_one(job, mid, confirm=confirm, actor=actor))
    if all_:
        results = [fn(mid, confirm=confirm, actor=actor)
                   for mid, _ in _active(_store._entries())]
        return {"ok": all(r.get("ok") for r in results), "code": 200, "job": job,
                "all": True, "count": len(results), "results": results}
    if not mem_id:
        return {"ok": False, "code": 2,
                "error": f"{job} requires a memory id or --all"}
    return fn(mem_id, confirm=confirm, actor=actor)


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M028 SLM memory janitor (SDD-066)")
    sub = ap.add_subparsers(dest="job")
    for j in ("dedup", "edges", "contradict"):
        p = sub.add_parser(j)
        p.add_argument("--confirm", action="store_true")
        p.add_argument("--actor", default="operator")
    for j in sorted(_PER_ENTRY):
        p = sub.add_parser(j)
        p.add_argument("id", nargs="?", default=None)
        p.add_argument("--all", action="store_true", dest="all_")
        p.add_argument("--confirm", action="store_true")
        p.add_argument("--actor", default="operator")
    av = sub.add_parser("advance")
    av.add_argument("id")
    av.add_argument("--confirm", action="store_true")
    av.add_argument("--actor", default="operator")
    sw = sub.add_parser("sweep")
    sw.add_argument("--confirm", action="store_true")
    sw.add_argument("--actor", default="janitor")
    sw.add_argument("--stop", default=None)
    sw.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    job = args.job
    if job == "dedup":
        r = dedup(confirm=args.confirm, actor=args.actor)
    elif job == "edges":
        r = edges(confirm=args.confirm, actor=args.actor)
    elif job == "contradict":
        r = contradict(confirm=args.confirm, actor=args.actor)
    elif job in _PER_ENTRY:
        r = _run_per_entry(job, args.id, all_=args.all_, confirm=args.confirm,
                           actor=args.actor)
    elif job == "advance":
        r = advance(args.id, confirm=args.confirm, actor=args.actor)
    elif job == "sweep":
        r = sweep(confirm=args.confirm, actor=args.actor, stop=args.stop, limit=args.limit)
    else:
        ap.error("a job is required: dedup|edges|contradict|tag|extract-facts|topic|"
                 "summarize|classify|advance|sweep")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
