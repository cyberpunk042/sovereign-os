#!/usr/bin/env python3
"""scripts/intelligence/memory-store.py — M028 memory-entry store + soft-delete
forget + undo (SDD-059 / SDD-052 Stage 3).

SDD-052 built the D-07 pending-change approve/reject sign-off but deliberately
deferred the destructive/reversal ops (SB-077 — no speculative store): the M028
projection (`/run/sovereign-os/memory.json`) is aggregate counts + a pending queue,
with NO addressable memory-entry store and NO change-ledger. This module builds
that minimal store + ledger and the two ops on top:

  memory-changes forget <mem-id> [--confirm] [--force]   R10184 — soft-delete a memory
  memory-changes undo   <chg-id> [--confirm]             R10185 — reverse a change
  memory-changes register --type N [--summary ...]       mint a memory entry (producer)
  memory-changes purge  [--older-than N] [--confirm]     retention sweep (SDD-060, CLI-only)

Model:
  - store  /var/lib/sovereign-os/memory/store.json  {entries:{<mem-id>:{id,type,
           stage,summary,state,created,updated}}} — the addressable M028 entries.
  - ledger /var/lib/sovereign-os/memory/changes.json {changes:[{id,op,mem_id,prev,
           ts,reversed}]} — the reversible change-ledger (undo reads/marks it).

`forget` is REFUSE-BY-DEFAULT: `--force` is a CLI-only escalation (SDD-052
Q-052-B); the cockpit `memory-forget` control (change_cli has no `--force`) always
refuses with a CLI remediation. `forget` SOFT-DELETES (tombstones `state:forgotten`
+ ledgers the prior state) — it NEVER hard-removes, so `undo` can always restore.
`undo` reverses a ledger change (restores a tombstoned entry). `purge` (SDD-060) is
the retention sweep that hard-removes `forgotten` tombstones past a window (marking
the ledger change `purged`; `undo` then refuses) — CLI-only, IRREVERSIBLE.

Safety: DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset; the real store
mutation runs live + operator-key + type-to-confirm gated. R10212: sovereign-os-
owned; the read core `memory-changes.py` stays a pure reader (405 API). MS003
signing deferred to selfdef.

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id/refused.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

STORE = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_STORE_DB", "/var/lib/sovereign-os/memory/store.json"))
CHANGES = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_CHANGE_LEDGER", "/var/lib/sovereign-os/memory/changes.json"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_UNSIGNED = "unsigned-pending-MS003"
_VALID_TYPE = frozenset(range(1, 9))  # M028 E0260 — 8 memory types
_WRITE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, type(default)) else default
    except (OSError, json.JSONDecodeError, ValueError):
        return default


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".memory-store-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _emit_span(op: str, mem_id: str, actor: str, extra: dict[str, Any]) -> None:
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = {
        "trace_id": f"memory-store-{mem_id}-{ms:x}",
        "span_id": f"ms-{ms:x}",
        "parent_span_id": None,
        "operation": f"memory_{op}",
        "start_ts": _now(),
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"mem_id": mem_id, "op": op, **extra},
        "ocsf_class": "5001",
        "actor": actor,
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "signature": _UNSIGNED,
        "schema_version": SCHEMA_VERSION,
    }
    try:
        SPAN_STORE.parent.mkdir(parents=True, exist_ok=True)
        with SPAN_STORE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span) + "\n")
    except OSError:
        pass


def _entries() -> dict[str, Any]:
    store = _read_json(STORE, {})
    ents = store.get("entries")
    return ents if isinstance(ents, dict) else {}


def _changes() -> list[dict[str, Any]]:
    led = _read_json(CHANGES, {})
    ch = led.get("changes")
    return ch if isinstance(ch, list) else []


def register(mtype: int, *, summary: str = "", actor: str = "operator") -> dict[str, Any]:
    """Stage-1 minimal producer — mint an active memory entry. The real M028
    admission-lifecycle producer is Stage N."""
    try:
        t = int(mtype)
    except (TypeError, ValueError):
        return {"ok": False, "code": 2, "error": f"invalid type {mtype!r}"}
    if t not in _VALID_TYPE:
        return {"ok": False, "code": 2, "error": f"type must be 1..8 (M028), got {t}"}
    mid = f"mem-{secrets.token_hex(4)}"
    entry = {"id": mid, "type": t, "stage": "store-raw", "summary": summary,
             "state": "active", "created": _now(), "updated": _now()}
    with _WRITE_LOCK:
        store = _read_json(STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict):
            ents = {}
        ents[mid] = entry
        store["entries"] = ents
        try:
            _atomic_write(STORE, store)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"store write failed: {e}"}
    return {"ok": True, "code": 200, "id": mid, "type": t, "state": "active"}


def forget(mem_id: str, *, actor: str = "operator", confirm: bool = False,
           force: bool = False) -> dict[str, Any]:
    """R10184 — SOFT-DELETE a memory (tombstone `state:forgotten` + ledger the prior
    state so undo can restore). REFUSE-by-default: `--force` is a CLI-only escalation
    (Q-052-B). DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    if not _SAFE_ID.fullmatch(mem_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe memory id {mem_id!r} (must match _SAFE_VALUE, no '/')"}
    with _WRITE_LOCK:
        ents = _entries()
        entry = ents.get(mem_id)
        if entry is None:
            return {"ok": False, "code": 2, "id": mem_id,
                    "error": f"no memory entry resolved for {mem_id!r}"}
        if entry.get("state") == "forgotten":
            return {"ok": False, "code": 2, "id": mem_id,
                    "error": f"memory {mem_id!r} is already forgotten (undo to restore)"}
        if not force:
            return {"ok": False, "code": 2, "id": mem_id,
                    "error": "forget refused — destructive (R10184). Override via the "
                    f"logged CLI: `sovereign-osctl memory-changes forget {mem_id} "
                    "--confirm --force`"}
        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": "forget", "id": mem_id,
                    "dry_run": True, "would": {"state_transition": "active→forgotten",
                                               "soft_delete": True, "reversible": True},
                    "note": f"DRY-RUN ({why}) — soft-delete (tombstone); undo restores it"}
        ts = _now()
        prev = {"state": entry.get("state", "active"), "stage": entry.get("stage")}
        entry["state"] = "forgotten"
        entry["updated"] = ts
        store = _read_json(STORE, {})
        store.setdefault("entries", {})[mem_id] = entry
        cid = f"chg-{secrets.token_hex(4)}"
        change = {"id": cid, "op": "forget", "mem_id": mem_id, "prev": prev,
                  "ts": ts, "actor": actor, "reversed": False, "signature": _UNSIGNED}
        led = _read_json(CHANGES, {})
        changes = led.get("changes")
        if not isinstance(changes, list):
            changes = []
        changes.append(change)
        led["changes"] = changes
        try:
            _atomic_write(STORE, store)
            _atomic_write(CHANGES, led)
        except OSError as e:
            return {"ok": False, "code": 1, "id": mem_id, "error": f"write failed: {e}"}
        _emit_span("forget", mem_id, actor, {"change_id": cid})
        return {"ok": True, "code": 200, "verb": "forget", "id": mem_id,
                "state": "forgotten", "change_id": cid, "signature": _UNSIGNED}


def undo(change_id: str, *, actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """R10185 — reverse a ledger change (restore a tombstoned entry). DRY-RUN
    unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    if not _SAFE_ID.fullmatch(change_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe change id {change_id!r} (must match _SAFE_VALUE, no '/')"}
    with _WRITE_LOCK:
        led = _read_json(CHANGES, {})
        changes = led.get("changes")
        if not isinstance(changes, list):
            changes = []
        change = next((c for c in changes
                       if isinstance(c, dict) and str(c.get("id")) == change_id), None)
        if change is None:
            return {"ok": False, "code": 2, "id": change_id,
                    "error": f"no change resolved for {change_id!r}"}
        if change.get("reversed"):
            return {"ok": False, "code": 2, "id": change_id,
                    "error": f"change {change_id!r} was already reversed"}
        if change.get("purged"):
            return {"ok": False, "code": 2, "id": change_id,
                    "error": f"change {change_id!r} was purged (retention); cannot restore"}
        mem_id = change.get("mem_id")
        prev_state = (change.get("prev") or {}).get("state", "active")
        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": "undo", "id": change_id,
                    "mem_id": mem_id, "dry_run": True,
                    "would": {"restore": mem_id, "to_state": prev_state},
                    "note": f"DRY-RUN ({why}) — reverses the {change.get('op')} change"}
        ts = _now()
        store = _read_json(STORE, {})
        ents = store.get("entries")
        if not isinstance(ents, dict) or mem_id not in ents:
            return {"ok": False, "code": 2, "id": change_id,
                    "error": f"the change's memory {mem_id!r} is no longer in the store"}
        ents[mem_id]["state"] = prev_state
        ents[mem_id]["updated"] = ts
        change["reversed"] = True
        change["reversed_ts"] = ts
        try:
            _atomic_write(STORE, store)
            _atomic_write(CHANGES, led)
        except OSError as e:
            return {"ok": False, "code": 1, "id": change_id, "error": f"write failed: {e}"}
        _emit_span("undo", str(mem_id), actor, {"change_id": change_id})
        return {"ok": True, "code": 200, "verb": "undo", "id": change_id,
                "mem_id": mem_id, "restored_state": prev_state, "signature": _UNSIGNED}


def purge(*, older_than_days: int = 30, confirm: bool = False,
          actor: str = "operator") -> dict[str, Any]:
    """Retention sweep — HARD-REMOVE `state:forgotten` tombstones whose `updated`
    is older than the window, marking each entry's non-reversed ledger forget-change
    `purged` (the ledger is the audit record — never a deleted row). IRREVERSIBLE:
    once purged, `undo` can no longer restore (SDD-060). Only touches `forgotten`
    entries past the window — `active` + within-window tombstones are never removed;
    an unparseable `updated` is treated as not-old (never purge on ambiguity).

    CLI-ONLY maintenance verb (NOT a cockpit control — the web can never reach it).
    DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    try:
        days = int(older_than_days)
    except (TypeError, ValueError):
        return {"ok": False, "code": 2, "error": f"invalid --older-than {older_than_days!r}"}
    if days < 0:
        return {"ok": False, "code": 2, "error": f"--older-than must be >= 0, got {days}"}
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    with _WRITE_LOCK:
        stale: list[str] = []
        for mid, entry in _entries().items():
            if entry.get("state") != "forgotten":
                continue
            upd = entry.get("updated")
            try:
                ts = datetime.fromisoformat(upd) if isinstance(upd, str) else None
            except ValueError:
                ts = None
            if ts is None:
                continue  # unparseable → treat as not-old (never purge on ambiguity)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts <= cutoff:
                stale.append(mid)
        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": "purge", "dry_run": True,
                    "older_than_days": days, "would_purge": stale, "count": len(stale),
                    "note": f"DRY-RUN ({why}) — would hard-remove {len(stale)} tombstone(s) "
                    "past retention (IRREVERSIBLE; undo cannot restore purged entries)"}
        if not stale:
            return {"ok": True, "code": 200, "verb": "purge", "dry_run": False,
                    "older_than_days": days, "purged": [], "count": 0,
                    "note": "no tombstones past retention"}
        ts_now = _now()
        store = _read_json(STORE, {})
        sents = store.get("entries")
        if not isinstance(sents, dict):
            sents = {}
        for mid in stale:
            sents.pop(mid, None)
        store["entries"] = sents
        led = _read_json(CHANGES, {})
        changes = led.get("changes")
        if not isinstance(changes, list):
            changes = []
        stale_set = set(stale)
        for c in changes:
            if (isinstance(c, dict) and c.get("op") == "forget"
                    and c.get("mem_id") in stale_set
                    and not c.get("reversed") and not c.get("purged")):
                c["purged"] = True
                c["purged_ts"] = ts_now
        led["changes"] = changes
        try:
            _atomic_write(STORE, store)
            _atomic_write(CHANGES, led)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
        for mid in stale:
            _emit_span("purge", mid, actor, {"older_than_days": days})
        return {"ok": True, "code": 200, "verb": "purge", "dry_run": False,
                "older_than_days": days, "purged": stale, "count": len(stale),
                "signature": _UNSIGNED}


def store_list() -> list[dict[str, Any]]:
    return list(_entries().values())


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M028 memory forget/undo store (SDD-059)")
    sub = ap.add_subparsers(dest="cmd")
    fg = sub.add_parser("forget")
    fg.add_argument("id")
    fg.add_argument("--actor", default="operator")
    fg.add_argument("--confirm", action="store_true")
    fg.add_argument("--force", action="store_true")
    ud = sub.add_parser("undo")
    ud.add_argument("id")
    ud.add_argument("--actor", default="operator")
    ud.add_argument("--confirm", action="store_true")
    rg = sub.add_parser("register")
    rg.add_argument("--type", type=int, required=True)
    rg.add_argument("--summary", default="")
    rg.add_argument("--actor", default="operator")
    pg = sub.add_parser("purge")
    pg.add_argument("--older-than", type=int, default=30, dest="older_than")
    pg.add_argument("--confirm", action="store_true")
    pg.add_argument("--actor", default="operator")
    sub.add_parser("list")
    args = ap.parse_args(argv)
    if args.cmd == "forget":
        r = forget(args.id, actor=args.actor, confirm=args.confirm, force=args.force)
    elif args.cmd == "undo":
        r = undo(args.id, actor=args.actor, confirm=args.confirm)
    elif args.cmd == "register":
        r = register(args.type, summary=args.summary, actor=args.actor)
    elif args.cmd == "purge":
        r = purge(older_than_days=args.older_than, confirm=args.confirm, actor=args.actor)
    elif args.cmd == "list":
        r = {"ok": True, "code": 200, "entries": store_list()}
    else:
        ap.error("a subverb is required: forget|undo|register|purge|list")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
