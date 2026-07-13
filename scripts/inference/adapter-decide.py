#!/usr/bin/env python3
"""scripts/inference/adapter-decide.py — the D-11 adapter WRITE surface (SDD-051).

The read side (`sovereign-osctl adapters inventory|list|history`) lives in
adapter-foundry.py and stays PRISTINE (read-only, safe-empty). This is the
deliberately-separate write side — the LoRA-Foundry promotion authority:

  adapters promote  <id> [--confirm]   pending → active; REQUIRES the MS041
                                        triple-gate (snapshot + test/eval +
                                        oracle-or-human) all `passed` — else refuse
  adapters demote   <id> [--confirm]   active → pending
  adapters rollback <id> [--confirm]   → rolled-back
  adapters register <id> …             MINT a pending adapter with empty gates
                                        (Stage-1 stand-in producer — the real
                                        M046 training pipeline is Stage 4)

Safety (matches the sanctioned R10274 pattern used by approval-decide /
rollback-points / cost-policy):
  - decisions are DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset; the
    cockpit path adds operator-key presence + type-to-confirm via the exec daemon.
  - promote is REFUSE-BY-DEFAULT unless the MS041 high-risk triple-gate is met
    (R09697-R09711); there is NO panel override — a forced promotion is a manual
    registry edit (documented). Honors the L6-Persist doctrine fully.
  - MS003 signing is DELEGATED to selfdef (a consumed service); this first cut
    records `signature: "unsigned-pending-MS003"` (Q-051-E). Never builds signing
    crypto in sovereign-os (R10212).
  - atomic single-flight write (temp + os.replace) so a partial registry file is
    never observed; every decision is durably logged to a JSONL ledger AND an
    OCSF-5001 span (surfaces in D-05 traces + D-16 audit via trace-store.py).

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id/gate-unmet.
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
_CORE_PATH = Path(__file__).resolve().parent / "adapter-foundry.py"
_spec = importlib.util.spec_from_file_location("_adapter_foundry_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]

ADAPTER_REGISTRY = _core.ADAPTER_REGISTRY
_VALID_STATUS = _core._VALID_STATUS
SCHEMA_VERSION = _core.SCHEMA_VERSION

# durable append-only decisions ledger (registry lives under /var/lib; the ledger
# is a separate audit trail alongside the M049 span store).
LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_ADAPTER_LEDGER",
    "/var/log/sovereign-os/adapter-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

# id safety — mirrors _action_exec._SAFE_VALUE (forbids '/', whitespace, shell
# metacharacters), so an id always survives the exec-daemon arg allowlist.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_VERBS = ("promote", "demote", "rollback")
_UNSIGNED = "unsigned-pending-MS003"
_WRITE_LOCK = threading.Lock()

# transition guards + target status per verb.
_REQUIRED_STATUS = {"promote": "pending", "demote": "active"}
_NEW_STATUS = {"promote": "active", "demote": "pending", "rollback": "rolled-back"}


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


def _gate_unmet(gates: dict[str, Any]) -> list[str]:
    """The MS041 triple-gate (R09697-R09711): snapshot + test/eval +
    (oracle OR human) all `passed`. Returns the list of unmet gate requirements
    (empty == all met)."""
    unmet = []
    if gates.get("snapshot") != "passed":
        unmet.append("snapshot")
    if gates.get("test_eval") != "passed":
        unmet.append("test_eval")
    if gates.get("oracle") != "passed" and gates.get("human") != "passed":
        unmet.append("oracle_or_human")
    return unmet


def _atomic_write(path: Path, obj: Any) -> None:
    """Write JSON atomically (temp in the target dir + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".adapters-", suffix=".tmp")
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
        "trace_id": f"adapter-{decision['id']}-{ms:x}",
        "span_id": f"ade-{ms:x}",
        "parent_span_id": None,
        "operation": "adapter_decision",
        "start_ts": decision["decided_ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"adapter_id": decision["id"], "verb": decision["verb"],
                       "status": decision["status"]},
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


def decide(adapter_id: str, verb: str, *, actor: str = "operator",
           rationale: str = "", confirm: bool = False) -> dict[str, Any]:
    """Apply a promote/demote/rollback decision to the promotion registry.
    DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset. promote refuses
    unless the MS041 triple-gate is met. Returns a structured result."""
    if verb not in _VERBS:
        return {"ok": False, "code": 2, "error": f"unknown verb {verb!r} (use {list(_VERBS)})"}
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe adapter id {adapter_id!r} (must match _SAFE_VALUE, no '/')"}
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"

    with _WRITE_LOCK:
        # current merged state via the read core (catalog ∪ registry overlay).
        # Pass ADAPTER_REGISTRY explicitly (module-level, single source) so the
        # reader honors the same registry path this writer reads/writes.
        rows = {r["id"]: r for r in _core.list_adapters(ADAPTER_REGISTRY)}
        target = rows.get(adapter_id)
        if target is None:
            return {"ok": False, "code": 2, "id": adapter_id,
                    "error": f"no adapter resolved for {adapter_id!r} "
                    f"({'empty inventory' if not rows else 'unknown adapter'})"}
        status = target["status"]
        gates = target.get("gates") or {}
        new_status = _NEW_STATUS[verb]

        # transition guards
        req = _REQUIRED_STATUS.get(verb)
        if req is not None and status != req:
            return {"ok": False, "code": 2, "id": adapter_id, "status": status,
                    "error": f"cannot {verb} adapter in status {status!r} (must be {req!r})"}
        if verb == "promote":
            unmet = _gate_unmet(gates)
            if unmet:
                return {"ok": False, "code": 2, "id": adapter_id, "gates": gates,
                        "error": f"MS041 triple-gate not satisfied — unmet: {unmet} "
                        "(promote requires snapshot + test_eval + oracle-or-human all "
                        "'passed'; a forced promotion is a manual registry edit)"}

        if dry:
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": verb, "id": adapter_id, "dry_run": True,
                    "would": {"status_transition": f"{status}→{new_status}"},
                    "note": f"DRY-RUN ({why}) — decision is operator-key + type-to-confirm "
                            "gated at the exec daemon; signature deferred to selfdef MS003"}

        decided_ts = _now()
        reg = _core._read_json(ADAPTER_REGISTRY)
        adapters = reg.get("adapters")
        if not isinstance(adapters, dict):
            adapters = {}
        entry = adapters.get(adapter_id)
        if not isinstance(entry, dict):
            entry = {}
        entry["status"] = new_status
        entry["decided_by"] = actor
        entry["decided_ts"] = decided_ts
        entry["signature"] = _UNSIGNED
        entry.setdefault("base_model", target.get("base_model"))
        if rationale:
            entry["rationale"] = rationale
        _signed(entry)  # sign after the registry entry is fully assembled
        adapters[adapter_id] = entry
        reg["adapters"] = adapters

        hist = reg.get("history")
        if not isinstance(hist, list):
            hist = []
        hist.insert(0, _signed({"ts": decided_ts, "action": verb, "adapter_id": adapter_id,
                                "actor": actor, "rationale": rationale, "signature": _UNSIGNED}))
        reg["history"] = hist
        try:
            _atomic_write(ADAPTER_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "id": adapter_id, "error": f"write failed: {e}"}

        decision = _signed({"id": adapter_id, "verb": verb, "status": new_status,
                            "decided_by": actor, "decided_ts": decided_ts,
                            "rationale": rationale, "signature": _UNSIGNED})
        _append_ledger(decision)
        _emit_span(decision)
        return _signed({"ok": True, "code": 200, "verb": verb, "id": adapter_id,
                        "status": new_status, "signature": _UNSIGNED})


def register(adapter_id: str, *, base_model: str = "?", training: str = "sft",
             actor: str = "operator") -> dict[str, Any]:
    """Stage-1 minimal producer — mint a `pending` adapter with empty MS041 gates.
    NOT privileged, NOT a control, NOT web-exposed. The real gate-advancing
    producer (M046 training + eval/oracle/human) is Stage 4."""
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2, "error": f"unsafe adapter id {adapter_id!r}"}
    with _WRITE_LOCK:
        reg = _core._read_json(ADAPTER_REGISTRY)
        adapters = reg.get("adapters")
        if not isinstance(adapters, dict):
            adapters = {}
        if adapter_id in adapters:
            return {"ok": False, "code": 2, "id": adapter_id,
                    "error": f"adapter {adapter_id!r} already in the registry"}
        adapters[adapter_id] = {
            "status": "pending", "base_model": base_model, "training": training,
            "registered_by": actor, "registered_ts": _now(),
            "gates": {"snapshot": "pending", "test_eval": "pending",
                      "oracle": "pending", "human": "pending"},
        }
        reg["adapters"] = adapters
        try:
            _atomic_write(ADAPTER_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    return {"ok": True, "code": 200, "id": adapter_id, "status": "pending"}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-11 adapter write surface (SDD-051)")
    sub = ap.add_subparsers(dest="cmd")
    for v in _VERBS:
        d = sub.add_parser(v)
        d.add_argument("id")
        d.add_argument("--actor", default="operator")
        d.add_argument("--rationale", default="")
        d.add_argument("--confirm", action="store_true")
    rg = sub.add_parser("register")
    rg.add_argument("id")
    rg.add_argument("--base-model", default="?")
    rg.add_argument("--training", default="sft")
    rg.add_argument("--actor", default="operator")
    args = ap.parse_args(argv)
    if args.cmd in _VERBS:
        r = decide(args.id, args.cmd, actor=args.actor, rationale=args.rationale,
                   confirm=args.confirm)
    elif args.cmd == "register":
        r = register(args.id, base_model=args.base_model, training=args.training,
                     actor=args.actor)
    else:
        ap.error("a subverb is required: promote|demote|rollback|register")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
