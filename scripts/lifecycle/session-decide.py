#!/usr/bin/env python3
"""scripts/lifecycle/session-decide.py — the D-01 session-lifecycle WRITE surface (SDD-053).

The read side (`sovereign-osctl sessions active|summary|steps`) lives in
session-registry.py and stays PRISTINE (read-only, safe-empty). This is the
deliberately-separate write side — the M057 session-lifecycle authority:

  sessions hibernate <id> [--confirm]   active → hibernated
  sessions resume    <id> [--confirm]   hibernated → active
  sessions kill      <id> [--confirm]   non-terminal → archived (operator-terminated)
  sessions hibernate-all [--confirm]    every active session → hibernated (bulk)

Each verb transitions a session entry's `state` in the M057 session registry
(/run/sovereign-os/sessions.json). The actual M047 CRIU checkpoint + ZFS
warm-sandbox continuity (the real hibernate/resume effect) is the M057 engine's
job (Stage 4) — exactly as memory-decide records a decision without performing the
downstream M028 transition. `kill` → `archived` (Q-053-A); the 9-state M057
machine has no distinct `killed` state.

Safety (matches the sanctioned R10274 pattern used by adapter-decide /
memory-decide):
  - decisions are DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset; the
    cockpit path adds operator-key presence + type-to-confirm via the exec daemon.
  - state-machine guards: hibernate needs `active`, resume needs `hibernated`, kill
    is refused on an already-terminal session.
  - MS003 signing is DELEGATED to selfdef; records `signature:
    "unsigned-pending-MS003"` (Q-053-E). Never builds signing crypto in
    sovereign-os (R10212).
  - atomic single-flight write (temp + os.replace) so a partial registry file is
    never observed; every decision is durably logged to a JSONL ledger AND an
    OCSF-5001 span (surfaces in D-05 traces + D-16 audit via trace-store.py).

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id/guard-fail.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── import the read core's schema (hyphenated filename → importlib) ──────────
_CORE_PATH = Path(__file__).resolve().parent / "session-registry.py"
_spec = importlib.util.spec_from_file_location("_session_registry_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]

SESSION_REGISTRY = _core.SESSION_REGISTRY
TASK_STATES = _core.TASK_STATES
SCHEMA_VERSION = _core.SCHEMA_VERSION

# SDD-057 — the save-state orchestrator, loaded lazily (it imports rollback-points
# + session-registry at module load; lazy-load keeps this reader's import cheap).
_SAVE_STATE = None


def _save_state_engine():
    global _SAVE_STATE
    if _SAVE_STATE is None:
        p = Path(__file__).resolve().parent / "save-state.py"
        spec = importlib.util.spec_from_file_location("_save_state_for_session_decide", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SAVE_STATE = mod
    return _SAVE_STATE

# durable append-only decisions ledger (/run is tmpfs → ephemeral; this is not).
LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_SESSION_LEDGER",
    "/var/log/sovereign-os/session-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

# id safety — mirrors _action_exec._SAFE_VALUE (forbids '/', whitespace, shell
# metacharacters), so an id always survives the exec-daemon arg allowlist.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_VERBS = ("hibernate", "resume", "kill")
_UNSIGNED = "unsigned-pending-MS003"
# terminal M057 states — kill is refused on these (already ended).
_TERMINAL = frozenset({"completed", "failed", "rolled_back", "archived"})
# per-verb transition contract: (required current state or None-for-any, new state).
_TRANSITION = {
    "hibernate": ("active", "hibernated"),
    "resume": ("hibernated", "active"),
    "kill": (None, "archived"),
}
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
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".sessions-", suffix=".tmp")
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
        "trace_id": f"session-{decision['id']}-{ms:x}",
        "span_id": f"sd-{ms:x}",
        "parent_span_id": None,
        "operation": "session_decision",
        "start_ts": decision["decided_ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"session_id": decision["id"], "verb": decision["verb"],
                       "state": decision["state"]},
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


def _record(session_id: str, verb: str, new_state: str, actor: str,
            rationale: str, decided_ts: str) -> None:
    decision = _signed({"id": session_id, "verb": verb, "state": new_state,
                        "decided_by": actor, "decided_ts": decided_ts,
                        "rationale": rationale, "signature": _UNSIGNED})
    _append_ledger(decision)
    _emit_span(decision)


def decide(session_id: str, verb: str, *, actor: str = "operator",
           rationale: str = "", confirm: bool = False) -> dict[str, Any]:
    """Apply a hibernate/resume/kill transition to a session. DRY-RUN unless
    --confirm AND SOVEREIGN_OS_DRY_RUN is unset. Returns a structured result."""
    if verb not in _VERBS:
        return {"ok": False, "code": 2, "error": f"unknown verb {verb!r} (use {list(_VERBS)})"}
    if not _SAFE_ID.fullmatch(session_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe session id {session_id!r} (must match _SAFE_VALUE, no '/')"}
    required, new_state = _TRANSITION[verb]

    with _WRITE_LOCK:
        reg = _core._read_registry(SESSION_REGISTRY)
        sessions = reg.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        target = next((s for s in sessions
                       if isinstance(s, dict) and str(s.get("id")) == session_id), None)
        if target is None:
            return {"ok": False, "code": 2, "id": session_id,
                    "error": f"no session resolved for {session_id!r} "
                    f"({'empty registry' if not sessions else 'unknown session id'})"}
        cur = target.get("state", "active")

        # transition guards
        if verb == "kill":
            if cur in _TERMINAL:
                return {"ok": False, "code": 2, "id": session_id, "state": cur,
                        "error": f"cannot kill a session already in terminal state {cur!r}"}
        elif cur != required:
            return {"ok": False, "code": 2, "id": session_id, "state": cur,
                    "error": f"cannot {verb} session in state {cur!r} (must be {required!r})"}

        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": verb, "id": session_id,
                    "dry_run": True, "would": {"state_transition": f"{cur}→{new_state}"},
                    "note": f"DRY-RUN ({why}) — decision is operator-key + type-to-confirm "
                            "gated at the exec daemon; the real M047 CRIU+ZFS effect is "
                            "the M057 engine (signature deferred to selfdef MS003)"}

        decided_ts = _now()
        target["state"] = new_state
        reg["sessions"] = sessions
        try:
            _atomic_write(SESSION_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "id": session_id, "error": f"write failed: {e}"}
        _record(session_id, verb, new_state, actor, rationale, decided_ts)
        result = _signed({"ok": True, "code": 200, "verb": verb, "id": session_id,
                          "state": new_state, "signature": _UNSIGNED})
        # SDD-057 (M047 save-state) — hibernate captures the session's 5-layer
        # save-state; resume restores it. Best-effort: a save-state failure does
        # NOT undo the registry transition (the state change already committed);
        # the outcome is attached for observability.
        if verb in ("hibernate", "resume"):
            try:
                _ss = _save_state_engine()
                fn = _ss.capture if verb == "hibernate" else _ss.restore
                result["save_state"] = fn(session_id, actor=actor, confirm=True)
            except Exception as e:  # noqa: BLE001 — best-effort; never break the transition
                result["save_state"] = {"ok": False, "error": f"save-state {verb} failed: {e}"}
        return result


def hibernate_all(*, actor: str = "operator", rationale: str = "",
                  confirm: bool = False) -> dict[str, Any]:
    """Bulk: transition every `active` session → `hibernated` in one atomic write
    (Q-053-B). DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset."""
    with _WRITE_LOCK:
        reg = _core._read_registry(SESSION_REGISTRY)
        sessions = reg.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        actives = [str(s.get("id")) for s in sessions
                   if isinstance(s, dict) and s.get("state", "active") == "active"]
        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": "hibernate-all", "dry_run": True,
                    "would": {"hibernate": actives, "count": len(actives)},
                    "note": f"DRY-RUN ({why}) — would hibernate {len(actives)} active "
                            "session(s); the real M047 CRIU+ZFS effect is the M057 engine"}
        decided_ts = _now()
        for s in sessions:
            if isinstance(s, dict) and s.get("state", "active") == "active":
                s["state"] = "hibernated"
        reg["sessions"] = sessions
        try:
            _atomic_write(SESSION_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
        for sid in actives:
            _record(sid, "hibernate-all", "hibernated", actor, rationale, decided_ts)
        return _signed({"ok": True, "code": 200, "verb": "hibernate-all",
                        "hibernated": actives, "count": len(actives), "signature": _UNSIGNED})


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-01 session-lifecycle write surface (SDD-053)")
    sub = ap.add_subparsers(dest="cmd")
    for v in _VERBS:
        d = sub.add_parser(v)
        d.add_argument("id")
        d.add_argument("--actor", default="operator")
        d.add_argument("--rationale", default="")
        d.add_argument("--confirm", action="store_true")
    ha = sub.add_parser("hibernate-all")
    ha.add_argument("--actor", default="operator")
    ha.add_argument("--rationale", default="")
    ha.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd in _VERBS:
        r = decide(args.id, args.cmd, actor=args.actor, rationale=args.rationale,
                   confirm=args.confirm)
    elif args.cmd == "hibernate-all":
        r = hibernate_all(actor=args.actor, rationale=args.rationale, confirm=args.confirm)
    else:
        ap.error("a subverb is required: hibernate|resume|kill|hibernate-all")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
