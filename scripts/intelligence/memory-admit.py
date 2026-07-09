#!/usr/bin/env python3
"""scripts/intelligence/memory-admit.py — the M028 admission-lifecycle ENGINE
(SDD-064 / SDD-059-060 Stage N).

SDD-059/060 built the D-07 memory store + forget/undo/purge, but the producer was a
minimal `register()` stand-in (mints one active entry, static `stage`), and nothing
advanced the 11-stage lifecycle or reconciled the D-07 projection. This is the real
admission ENGINE: value-driven admission gating + the 11-stage lifecycle progression.

  memory-changes admit --type N --summary "…" --trigger <store-if> [--trust 0-100] [--confirm]
  memory-changes admit --type N --summary "…" --ignore <ignore-if>          (decides NOT to store)
  memory-changes advance <mem-id> [--confirm]                               (walk the 11 stages)

GROUNDED (SB-077): there is NO real agent-memory SOURCE in sovereign-os today (no
graph / event stream / mirror). So OBSERVATIONS are CLI/fixture-supplied — the engine
does NOT fabricate a source; the auto-observation event-stream feed is a further
Stage-N (like the selfdef rules-mirror publisher crate). The ENGINE (value gating +
lifecycle + projection reconcile) is real.

Admission (config/agent/m028-memory-os.yaml `admission_rules`, milestone R04674-R04686):
  store-if (8 value triggers) → ADMIT; ignore-if (5) / low-trust / duplicate → NOT stored.
Lifecycle (M00471, verbatim): observe→classify→quarantine→link→score→store-raw→
  extract-facts→verify→promote→decay→archive.

Every admit/advance calls memory-store.reconcile() so the D-07 projection (memory.json
counts + lifecycle occupancy) reflects the real store (closes Q-059-D/Q-060-D). DRY-RUN
default; ids `_SAFE_ID`; OCSF-5001 span. stdlib-only. Exit: 0 ok/dry · 1 write · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import secrets
import sys
from pathlib import Path
from typing import Any

_INTEL = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Reuse the store the D-07 forget/undo/purge/reconcile already own (single store).
_store = _load(_INTEL / "memory-store.py", "_memory_store_for_admit")

# M028 admission — the 8 store-if value triggers (R04674-R04681) + 5 ignore-if
# (config/agent/m028-memory-os.yaml `admission_rules.ignore_if`).
_STORE_IF = ("user-corrected", "task-outcome", "repeated-pattern", "new-fact",
             "tool-worked", "model-mistake", "high-value-reuse", "preference")
_IGNORE_IF = ("transient", "low-trust", "duplicate", "noisy", "unverified")
_TRUST_FLOOR = 30  # 0-100; below → low-trust, not admitted
_LIFECYCLE = _store._LIFECYCLE_STAGES  # the 11-stage verbatim order


def _not_admitted(mtype: int, reason: str) -> dict[str, Any]:
    """A legitimate value-gated rejection — the engine ran correctly + decided NOT to
    store (ok:True, admitted:False). Distinct from a usage error (ok:False)."""
    return {"ok": True, "code": 200, "admitted": False, "type": mtype, "reason": reason}


def _is_duplicate(mtype: int, summary: str) -> bool:
    for e in _store._entries().values():
        if (isinstance(e, dict) and e.get("state") == "active"
                and e.get("type") == mtype and e.get("summary") == summary):
            return True
    return False


def admit(mtype: int, summary: str, *, trigger: str | None = None,
          ignore: str | None = None, trust: int = 100, actor: str = "operator",
          confirm: bool = False) -> dict[str, Any]:
    """Admit an observation through the M028 value gate. store-if trigger + trust ≥
    floor + not duplicate → mint an entry at stage `observe`; else NOT stored."""
    try:
        t = int(mtype)
    except (TypeError, ValueError):
        return {"ok": False, "code": 2, "error": f"invalid type {mtype!r}"}
    if t not in _store._VALID_TYPE:
        return {"ok": False, "code": 2, "error": f"type must be 1..8 (M028), got {t}"}
    # ── the value gate (M028 admission_rules) ──
    if ignore is not None:
        if ignore not in _IGNORE_IF:
            return {"ok": False, "code": 2,
                    "error": f"unknown ignore-if reason {ignore!r} (use {list(_IGNORE_IF)})"}
        return _not_admitted(t, f"ignored: {ignore}")
    if trigger not in _STORE_IF:
        return {"ok": False, "code": 2,
                "error": f"a store-if trigger is required to admit (one of {list(_STORE_IF)}) "
                f"or --ignore one of {list(_IGNORE_IF)}"}
    if int(trust) < _TRUST_FLOOR:
        return _not_admitted(t, f"low-trust ({trust} < {_TRUST_FLOOR})")
    if _is_duplicate(t, summary):
        return _not_admitted(t, "duplicate")
    if (not confirm) or _store.os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"ok": True, "code": 200, "admitted": True, "dry_run": True, "type": t,
                "trigger": trigger, "trust": int(trust), "would": {"stage": "observe"},
                "note": f"DRY-RUN ({why}) — would admit at stage observe"}
    mid = f"mem-{secrets.token_hex(4)}"
    entry = {"id": mid, "type": t, "stage": "observe", "summary": summary,
             "state": "active", "created": _store._now(), "updated": _store._now(),
             "admitted_via": trigger, "trust": int(trust), "value_score": int(trust)}
    with _store._WRITE_LOCK:
        store = _store._read_json(_store.STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict):
            ents = {}
        ents[mid] = entry
        store["entries"] = ents
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"store write failed: {e}"}
    _store._emit_span("admit", mid, actor, {"trigger": trigger, "trust": int(trust)})
    _store._reconcile_safe()
    return {"ok": True, "code": 200, "admitted": True, "id": mid, "type": t,
            "stage": "observe", "trigger": trigger, "trust": int(trust)}


def advance(mem_id: str, *, actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """Advance an entry to the next of the 11 lifecycle stages (idempotent at
    `archive`). DRY-RUN default."""
    if not _store._SAFE_ID.fullmatch(mem_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe memory id {mem_id!r} (must match _SAFE_VALUE, no '/')"}
    with _store._WRITE_LOCK:
        ents = _store._entries()
        entry = ents.get(mem_id)
        if entry is None:
            return {"ok": False, "code": 2, "id": mem_id,
                    "error": f"no memory entry resolved for {mem_id!r}"}
        cur = entry.get("stage")
        idx = _LIFECYCLE.index(cur) if cur in _LIFECYCLE else 0
        if idx >= len(_LIFECYCLE) - 1:
            return {"ok": True, "code": 200, "id": mem_id, "stage": "archive",
                    "idempotent": True, "note": "already at the final lifecycle stage (archive)"}
        nxt = _LIFECYCLE[idx + 1]
        if (not confirm) or _store.os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "id": mem_id, "dry_run": True,
                    "would": {"stage_transition": f"{cur}→{nxt}"},
                    "note": f"DRY-RUN ({why}) — would advance to {nxt}"}
        store = _store._read_json(_store.STORE, {})
        store.setdefault("entries", {})
        store["entries"].setdefault(mem_id, entry)
        store["entries"][mem_id]["stage"] = nxt
        store["entries"][mem_id]["updated"] = _store._now()
        try:
            _store._atomic_write(_store.STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "id": mem_id, "error": f"write failed: {e}"}
    _store._emit_span("advance", mem_id, actor, {"stage": nxt})
    _store._reconcile_safe()
    return {"ok": True, "code": 200, "id": mem_id, "stage": nxt, "from": cur}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M028 memory admission engine (SDD-064)")
    sub = ap.add_subparsers(dest="cmd")
    ad = sub.add_parser("admit")
    ad.add_argument("--type", type=int, required=True)
    ad.add_argument("--summary", default="")
    ad.add_argument("--trigger", default=None)
    ad.add_argument("--ignore", default=None)
    ad.add_argument("--trust", type=int, default=100)
    ad.add_argument("--actor", default="operator")
    ad.add_argument("--confirm", action="store_true")
    av = sub.add_parser("advance")
    av.add_argument("id")
    av.add_argument("--actor", default="operator")
    av.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "admit":
        r = admit(args.type, args.summary, trigger=args.trigger, ignore=args.ignore,
                  trust=args.trust, actor=args.actor, confirm=args.confirm)
    elif args.cmd == "advance":
        r = advance(args.id, actor=args.actor, confirm=args.confirm)
    else:
        ap.error("a subverb is required: admit|advance")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
