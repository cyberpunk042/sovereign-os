#!/usr/bin/env python3
"""scripts/lifecycle/approval-decide.py — the D-06 approval WRITE surface (SDD-048).

The read side (`sovereign-osctl approvals pending|gates|key`) lives in
approval-queue.py and stays PRISTINE (read-only, safe-empty). This is the
deliberately-separate write side:

  approvals approve <id> [--confirm]   record status=signed; sign the SGn gate
  approvals deny    <id> [--confirm]   record status=denied; gate stays pending
  approvals defer   <id> [--confirm]   re-queue; set defer_until (default +24h)
  approvals request …                  MINT an APR-<8hex> request (Stage-2 stand-in
                                        producer — real cloud/stage-gate producers
                                        are Stage 4)

Safety (matches the sanctioned R10274 pattern used by cost-policy / rollback):
  - decisions are DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset; the
    cockpit path adds operator-key presence + type-to-confirm via the exec daemon.
  - MS003 signing is DELEGATED to selfdef (a consumed service); this first cut
    records `signature: "unsigned-pending-MS003"` (Q-048-A). Never builds signing
    crypto in sovereign-os (R10212).
  - atomic single-flight write (temp + os.replace) so a partial /run file is never
    observed; every decision is durably logged to a JSONL ledger AND an OCSF-5001
    span (surfaces in D-05 traces + D-16 audit via trace-store.py).

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id.
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── import the read core's schema (hyphenated filename → importlib) ──────────
_CORE_PATH = Path(__file__).resolve().parent / "approval-queue.py"
_spec = importlib.util.spec_from_file_location("_approval_queue_core", _CORE_PATH)
_core = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_core)  # type: ignore[union-attr]

APPROVALS_QUEUE = _core.APPROVALS_QUEUE
STAGE_GATES = _core.STAGE_GATES
_VALID_SEVERITY = _core._VALID_SEVERITY
_SEVERITY_ORDER = _core._SEVERITY_ORDER
SCHEMA_VERSION = _core.SCHEMA_VERSION

# durable append-only decisions ledger (/run is tmpfs → ephemeral; this is not).
LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_APPROVAL_LEDGER",
    "/var/log/sovereign-os/approval-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

# id safety — mirrors _action_exec._SAFE_VALUE (forbids '/', whitespace, shell
# metacharacters), so an id always survives the exec-daemon arg allowlist.
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_VERBS = ("approve", "deny", "defer")
_UNSIGNED = "unsigned-pending-MS003"
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
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".approvals-", suffix=".tmp")
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


def _notify_gate(decision: dict[str, Any]) -> None:
    """2026-07-19 methodology-respect pass: every SG gate decision emits
    through the notifykit channel stack when a config exists — the
    `stage-gate` trigger, so the operator can set frontmatter props on it
    (e.g. `sovereign-osctl notifykit trigger stage-gate important true`).
    Notification must NEVER break the decision path (same contract as
    wikiops.notify_outcome)."""
    cfg_path = os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", "/etc/sovereign-os/notifykit.toml")
    if not os.path.isfile(cfg_path):
        return
    try:
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from tools.notifykit import ChannelRegistry, Event, NotifyConfig
        gate = decision.get("gate") or ""
        registry = ChannelRegistry(NotifyConfig.load(cfg_path))
        registry.dispatch(Event(
            title=(f"stage-gate {decision.get('verb')}: {decision.get('id')}"
                   + (f" — {gate}" if gate else "")),
            message=(f"status={decision.get('status')} "
                     f"by {decision.get('decided_by')}"),
            priority="high" if decision.get("verb") == "approve" else "normal",
            urgency="normal",
            source="stage-gate",
        ))
    except Exception as e:  # never mask the decision result
        print(f"WARN stage-gate notify failed: {e}", file=sys.stderr)


def _emit_span(decision: dict[str, Any]) -> None:
    """Best-effort OCSF-5001 (Configuration Change) M049 span so the decision
    surfaces in D-05 traces + D-16 audit (same store trace-store.py reads).
    13-field canonical schema. Never raises."""
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = {
        "trace_id": f"approval-{decision['id']}-{ms:x}",
        "span_id": f"ad-{ms:x}",
        "parent_span_id": decision.get("trace_id"),
        "operation": "approval_decision",
        "start_ts": decision["decided_ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"approval_id": decision["id"], "verb": decision["verb"],
                       "gate": decision.get("gate"), "status": decision["status"]},
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


def _resolve(records: list[dict[str, Any]], id_or_latest: str) -> dict[str, Any] | None:
    """Exact id, or 'latest' = the most urgent pending record (highest severity,
    then oldest ts) — mirrors rollback-apply's `latest` convenience."""
    pending = [r for r in records if str(r.get("status", "pending")) in ("pending", "deferred")]
    if id_or_latest == "latest":
        if not pending:
            return None
        pending.sort(key=lambda r: (_SEVERITY_ORDER.get(r.get("severity"), 9), r.get("ts") or ""))
        return pending[0]
    return next((r for r in records if str(r.get("id")) == id_or_latest), None)


def decide(id_or_latest: str, verb: str, *, actor: str = "operator",
           rationale: str = "", until: str | None = None,
           confirm: bool = False) -> dict[str, Any]:
    """Apply an approve/deny/defer decision to the queue. DRY-RUN unless --confirm
    AND SOVEREIGN_OS_DRY_RUN is unset. Returns a structured result."""
    if verb not in _VERBS:
        return {"ok": False, "code": 2, "error": f"unknown verb {verb!r} (use {list(_VERBS)})"}
    if id_or_latest != "latest" and not _SAFE_ID.fullmatch(id_or_latest):
        return {"ok": False, "code": 2,
                "error": f"unsafe approval id {id_or_latest!r} (must match APR-<hex> / _SAFE_VALUE, no '/')"}
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"

    with _WRITE_LOCK:
        reg = _core._read_json(APPROVALS_QUEUE)
        records = reg.get("approvals")
        if not isinstance(records, list):
            records = []
        target = _resolve(records, id_or_latest)
        if target is None:
            return {"ok": False, "code": 2, "id": id_or_latest,
                    "error": f"no approval resolved for {id_or_latest!r} "
                    f"({'empty queue' if not records else 'unknown id'})"}
        gate = target.get("gate")
        rid = str(target.get("id"))
        new_status = {"approve": "signed", "deny": "denied", "defer": "deferred"}[verb]
        gate_signs = verb == "approve" and gate in STAGE_GATES

        if dry:
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": verb, "id": rid, "dry_run": True,
                    "would": {"status": new_status,
                              "gate_transition": f"{gate}→signed" if gate_signs else None},
                    "note": f"DRY-RUN ({why}) — decision is operator-key + type-to-confirm "
                            "gated at the exec daemon; signature deferred to selfdef MS003"}

        decided_ts = _now()
        target["status"] = new_status
        target["decided_by"] = actor
        target["decided_ts"] = decided_ts
        target["signature"] = _UNSIGNED
        if rationale:
            target["rationale"] = rationale
        if verb == "defer":
            target["defer_until"] = until or (
                datetime.now(tz=timezone.utc) + timedelta(hours=24)).isoformat()
        _signed(target)  # sign after the approval record is fully assembled
        if gate_signs:
            gates = reg.get("gates")
            if not isinstance(gates, dict):
                gates = {}
            gates[gate] = "signed"
            reg["gates"] = gates
        reg["approvals"] = records
        try:
            _atomic_write(APPROVALS_QUEUE, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "id": rid, "error": f"write failed: {e}"}

        decision = _signed({"id": rid, "verb": verb, "status": new_status, "gate": gate,
                            "decided_by": actor, "decided_ts": decided_ts,
                            "rationale": rationale, "signature": _UNSIGNED,
                            "trace_id": target.get("trace_id")})
        _append_ledger(decision)
        _emit_span(decision)
        _notify_gate(decision)
        return _signed({"ok": True, "code": 200, "verb": verb, "id": rid, "status": new_status,
                        "gate_signed": gate if gate_signs else None, "signature": _UNSIGNED})


def request(*, title: str, severity: str = "medium", gate: str = "L4→L5",
            actor: str = "operator", summary: str = "") -> dict[str, Any]:
    """Stage-2 minimal producer — mint an APR-<8hex> pending request. NOT
    privileged. Web-exposed via the sanctioned R10274 exec-rail as the
    `approvals-request` control (SDD-104, dry-run default) — an unprivileged
    intent-enqueue, distinct from the privileged approve/deny that signs it; rich
    free-text titles stay CLI (the exec `_SAFE_VALUE` allowlist forbids free text).
    Real auto-producers are Stage 4."""
    if severity not in _VALID_SEVERITY:
        severity = "medium"
    rid = f"APR-{secrets.token_hex(4)}"
    rec = {"id": rid, "title": title, "severity": severity, "gate": gate,
           "actor": actor, "kind": "transition",
           "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
           "ts": _now(), "summary": summary, "status": "pending"}
    with _WRITE_LOCK:
        reg = _core._read_json(APPROVALS_QUEUE)
        records = reg.get("approvals")
        if not isinstance(records, list):
            records = []
        records.append(rec)
        reg["approvals"] = records
        reg.setdefault("profile", rec["profile"])
        try:
            _atomic_write(APPROVALS_QUEUE, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "error": f"write failed: {e}"}
    return {"ok": True, "code": 200, "id": rid, "status": "pending", "severity": severity}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-06 approval write surface (SDD-048)")
    sub = ap.add_subparsers(dest="cmd")
    for v in _VERBS:
        d = sub.add_parser(v)
        d.add_argument("id")
        d.add_argument("--actor", default="operator")
        d.add_argument("--rationale", default="")
        d.add_argument("--until", default=None)
        d.add_argument("--confirm", action="store_true")
    rq = sub.add_parser("request")
    rq.add_argument("--title", required=True)
    rq.add_argument("--severity", default="medium")
    rq.add_argument("--gate", default="L4→L5")
    rq.add_argument("--actor", default="operator")
    rq.add_argument("--summary", default="")
    args = ap.parse_args(argv)
    if args.cmd in _VERBS:
        r = decide(args.id, args.cmd, actor=args.actor, rationale=args.rationale,
                   until=args.until, confirm=args.confirm)
    elif args.cmd == "request":
        r = request(title=args.title, severity=args.severity, gate=args.gate,
                    actor=args.actor, summary=args.summary)
    else:
        ap.error("a subverb is required: approve|deny|defer|request")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
