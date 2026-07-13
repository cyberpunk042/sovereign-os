#!/usr/bin/env python3
"""scripts/intelligence/memory-decide.py — the D-07 memory-change WRITE surface (SDD-052).

The read side (`sovereign-osctl memory-changes snapshot|types|lifecycle`) lives in
memory-changes.py and stays PRISTINE (read-only, safe-empty). This is the
deliberately-separate write side — the Memory-OS sign-off authority:

  memory-changes approve <change-id> [--confirm]   apply a pending change's op
                                                    (promote / pin); a pending
                                                    `forget` is REFUSED (Stage 3)
  memory-changes reject  <change-id> [--confirm]   discard a pending change
  memory-changes request …                         MINT an mc-<8hex> pending change
                                                    (Stage-1 stand-in producer — the
                                                    real M028 producers are Stage 4)

The M028 Memory OS's `pending` queue (in /run/sovereign-os/memory.json) is the
DESIGNED sign-off surface: promote/pin/forget operations are queued awaiting
operator sign-off. This writer transitions that queue; the actual memory-store
effect is the M028 producer's job (Stage 4) — exactly as approval-decide records a
decision without performing the downstream transition.

Safety (matches the sanctioned R10274 pattern used by approval-decide /
adapter-decide):
  - decisions are DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset; the
    cockpit path adds operator-key presence + type-to-confirm via the exec daemon.
  - a pending `forget` (R10184 — destructive memory deletion) is REFUSE-by-default
    (Stage 3); the remediation is the logged CLI `--force` (a manual escalation,
    like the d-08 prune floor).
  - MS003 signing is DELEGATED to selfdef; this first cut records
    `signature: "unsigned-pending-MS003"` (Q-052-E). Never builds signing crypto in
    sovereign-os (R10212).
  - atomic single-flight write (temp + os.replace) so a partial state file is never
    observed; every decision is durably logged to a JSONL ledger AND an OCSF-5001
    span (surfaces in D-05 traces + D-16 audit via trace-store.py).

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id/refused.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── import the read core's schema (hyphenated filename → importlib) ──────────
_CORE_PATH = Path(__file__).resolve().parent / "memory-changes.py"
_spec = importlib.util.spec_from_file_location("_memory_changes_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]

MEMORY_STATE = _core.MEMORY_STATE
_VALID_PENDING_OP = _core._VALID_PENDING_OP
SCHEMA_VERSION = _core.SCHEMA_VERSION

# durable append-only decisions ledger (/run is tmpfs → ephemeral; this is not).
LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_LEDGER",
    "/var/log/sovereign-os/memory-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

# id safety — mirrors _action_exec._SAFE_VALUE (forbids '/', whitespace, shell
# metacharacters), so an id always survives the exec-daemon arg allowlist.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_VERBS = ("approve", "reject")
_UNSIGNED = "unsigned-pending-MS003"
# ops that this engine can APPLY on approve (Stage 2 scope). `forget` is Stage 3
# (refuse-by-default + --force CLI, Q-052-B).
_APPLY_OPS = frozenset({"promote", "pin"})
_WRITE_LOCK = threading.Lock()


# MS003 (SDD-989) — sign records with the operator ed25519 key when present. The
# import is best-effort and `ms003.sign()` never raises + falls back to the
# `unsigned-pending-MS003` placeholder when no operator key is provisioned, so a
# keyless node's output is byte-identical to the pre-MS003 behaviour.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import ms003 as _ms003
except Exception:  # pragma: no cover - defensive import guard
    _ms003 = None


def _sign(record: dict[str, Any]) -> str:
    return _ms003.sign(record) if _ms003 is not None else _UNSIGNED


def _signed(record: dict[str, Any]) -> dict[str, Any]:
    """Set `record['signature']` via MS003 and return the record. Keyless → the
    `unsigned-pending-MS003` placeholder (identical to pre-MS003 output)."""
    record["signature"] = _sign(record)
    return record


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _atomic_write(path: Path, obj: Any) -> None:
    """Write JSON atomically (temp in the target dir + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".memory-", suffix=".tmp")
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


def _append_ledger(record: dict[str, Any]) -> None:
    """Best-effort durable append to the decisions JSONL. Never raises."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _emit_span(decision: dict[str, Any]) -> None:
    """Best-effort OCSF-5001 (Configuration Change) M049 span so the decision
    surfaces in D-05 traces + D-16 audit (same store trace-store.py reads).
    13-field canonical schema. Never raises."""
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = {
        "trace_id": f"memory-{decision['id']}-{ms:x}",
        "span_id": f"md-{ms:x}",
        "parent_span_id": None,
        "operation": "memory_decision",
        "start_ts": decision["decided_ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"change_id": decision["id"], "verb": decision["verb"],
                       "op": decision.get("op")},
        "ocsf_class": "5001",
        "actor": decision["decided_by"],
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "signature": decision["signature"],
        "schema_version": SCHEMA_VERSION,
    }
    try:
        SPAN_STORE.parent.mkdir(parents=True, exist_ok=True)
        with SPAN_STORE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span) + "\n")
    except OSError:
        pass


def decide(change_id: str, verb: str, *, actor: str = "operator",
           rationale: str = "", confirm: bool = False) -> dict[str, Any]:
    """Apply an approve/reject sign-off to a pending memory change. approve
    applies the change's op (promote/pin) — a pending `forget` is REFUSED
    (Stage 3). reject discards the change. DRY-RUN unless --confirm AND
    SOVEREIGN_OS_DRY_RUN is unset. Returns a structured result."""
    if verb not in _VERBS:
        return {"ok": False, "code": 2, "error": f"unknown verb {verb!r} (use {list(_VERBS)})"}
    if not _SAFE_ID.fullmatch(change_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe change id {change_id!r} (must match _SAFE_VALUE, no '/')"}

    with _WRITE_LOCK:
        state = _core._read_state(MEMORY_STATE)
        pending = state.get("pending")
        if not isinstance(pending, list):
            pending = []
        target = next((p for p in pending
                       if isinstance(p, dict) and str(p.get("id")) == change_id), None)
        if target is None:
            return {"ok": False, "code": 2, "id": change_id,
                    "error": f"no pending change resolved for {change_id!r} "
                    f"({'empty queue' if not pending else 'unknown change id'})"}
        op = target.get("op", "promote")

        # forget is Stage 3 — refuse-by-default (Q-052-B); the operator override is
        # a logged CLI --force, not a panel affordance.
        if verb == "approve" and op not in _APPLY_OPS:
            return {"ok": False, "code": 2, "id": change_id, "op": op,
                    "error": f"cannot approve a pending {op!r} change — {op} is not "
                    f"wired yet (Stage 3; forget/undo are refuse-by-default, override "
                    f"via the logged CLI --force). Approvable ops: {sorted(_APPLY_OPS)}"}

        dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
        if dry:
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            action = f"apply {op}" if verb == "approve" else "discard"
            return {"ok": True, "code": 200, "verb": verb, "id": change_id, "op": op,
                    "dry_run": True, "would": {"action": action, "remove_from_pending": True},
                    "note": f"DRY-RUN ({why}) — decision is operator-key + type-to-confirm "
                            "gated at the exec daemon; signature deferred to selfdef MS003"}

        decided_ts = _now()
        state["pending"] = [p for p in pending
                            if not (isinstance(p, dict) and str(p.get("id")) == change_id)]
        hist = state.get("history")
        if not isinstance(hist, list):
            hist = []
        hist.insert(0, _signed({"ts": decided_ts, "action": verb, "change_id": change_id,
                                "op": op, "actor": actor, "rationale": rationale,
                                "signature": _UNSIGNED}))
        state["history"] = hist
        try:
            _atomic_write(MEMORY_STATE, state)
        except OSError as e:
            return {"ok": False, "code": 1, "id": change_id, "error": f"write failed: {e}"}

        decision = _signed({"id": change_id, "verb": verb, "op": op, "decided_by": actor,
                            "decided_ts": decided_ts, "rationale": rationale,
                            "signature": _UNSIGNED})
        _append_ledger(decision)
        _emit_span(decision)
        return _signed({"ok": True, "code": 200, "verb": verb, "id": change_id, "op": op,
                        "applied": verb == "approve", "signature": _UNSIGNED})


def request(op: str, *, mtype: str = "semantic", scope: str = "",
            requester: str = "operator") -> dict[str, Any]:
    """Stage-1 minimal producer — mint an mc-<8hex> pending change awaiting
    sign-off. NOT privileged. Web-exposed via the sanctioned R10274 exec-rail as
    the `memory-request` control (SDD-104, dry-run default) — an unprivileged
    intent-enqueue, distinct from the privileged sign-off (memory-decide) that
    applies it; a free-text scope stays CLI (the exec `_SAFE_VALUE` allowlist
    forbids free text). The real M028 producers (admission lifecycle / decay)
    are Stage 4."""
    if op not in _VALID_PENDING_OP:
        return {"ok": False, "code": 2,
                "error": f"unknown op {op!r} (use {sorted(_VALID_PENDING_OP)})"}
    cid = f"mc-{secrets.token_hex(4)}"
    rec = {"id": cid, "op": op, "mtype": mtype, "scope": scope,
           "delta": "", "requester": requester, "ts": _now()}
    with _WRITE_LOCK:
        state = _core._read_state(MEMORY_STATE)
        pending = state.get("pending")
        if not isinstance(pending, list):
            pending = []
        pending.append(rec)
        state["pending"] = pending
        try:
            _atomic_write(MEMORY_STATE, state)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    return {"ok": True, "code": 200, "id": cid, "op": op, "status": "pending"}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-07 memory-change write surface (SDD-052)")
    sub = ap.add_subparsers(dest="cmd")
    for v in _VERBS:
        d = sub.add_parser(v)
        d.add_argument("id")
        d.add_argument("--actor", default="operator")
        d.add_argument("--rationale", default="")
        d.add_argument("--confirm", action="store_true")
    rq = sub.add_parser("request")
    rq.add_argument("op")
    rq.add_argument("--mtype", default="semantic")
    rq.add_argument("--scope", default="")
    rq.add_argument("--requester", default="operator")
    args = ap.parse_args(argv)
    if args.cmd in _VERBS:
        r = decide(args.id, args.cmd, actor=args.actor, rationale=args.rationale,
                   confirm=args.confirm)
    elif args.cmd == "request":
        r = request(args.op, mtype=args.mtype, scope=args.scope, requester=args.requester)
    else:
        ap.error("a subverb is required: approve|reject|request")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
