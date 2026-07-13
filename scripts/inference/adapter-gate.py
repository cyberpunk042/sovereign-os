#!/usr/bin/env python3
"""scripts/inference/adapter-gate.py — the M046 adapter GATE-PRODUCER (SDD-061).

SDD-051 built the promote/demote/rollback CONSUMER (adapter-decide.py) + the MS041
triple-gate check, but nothing advances a gate: `register()` mints all gates
`"pending"` and `decide()` never touches `gates`, so `promote` is unreachable except
by a manual registry edit. This module is the deliberately-separate PRODUCER that
advances the MS041 gates — snapshot + test/eval + (oracle OR human) — from REAL
evidence, mirroring the memory-store.py ↔ memory-decide.py split:

  adapters gate human    <id> [--confirm] [--rationale]   operator attestation
  adapters gate snapshot <id> [--confirm] [--dataset K]   a real ZFS rollback-point
  adapters gate eval     <id> [--confirm]                 a real passing eval record
  adapters gate oracle   <id> [--confirm]                 an oracle-backend judge

SB-077 (never fabricate): each gate's evidence-gatherer returns {ok, ...} or
{ok:False, reason}; on `ok:False` the gate STAYS `pending` and the verb honest-defers
with a CLI remediation — a gate is NEVER set to `"passed"` without proof. Grounded
reality: the eval harness is DRY-RUN-until-hardware and the oracle vLLM backend
(:8083) needs hardware, so eval-run + oracle honest-defer today; snapshot +
eval-record + human make a real promote reachable now.

Safety: DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset. Only the human gate
is a cockpit control (`adapter-gate-human`, exec-rail gated); eval/snapshot/oracle are
CLI-only producers (heavy / host-gated). R10212: sovereign-os-owned; the read core
adapter-foundry.py stays pure; adapters-api.py stays 405. MS003 deferred to selfdef.

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id/honest-defer.
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
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INFER = Path(__file__).resolve().parent
_REPO_ROOT = _INFER.parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# read core (registry schema + list_adapters) — the pure reader, never mutated here.
_af = _load(_INFER / "adapter-foundry.py", "_adapter_foundry_gate")
# evidence sources (reused, not reinvented).
_eval = _load(_REPO_ROOT / "scripts" / "observability" / "eval-tracker.py", "_eval_tracker_gate")
_rollback = _load(_REPO_ROOT / "scripts" / "lifecycle" / "rollback-points.py", "_rollback_points_gate")

ADAPTER_REGISTRY = _af.ADAPTER_REGISTRY
SCHEMA_VERSION = _af.SCHEMA_VERSION

LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_ADAPTER_LEDGER",
    "/var/log/sovereign-os/adapter-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))
ORACLE_URL = os.environ.get("SOVEREIGN_OS_ORACLE_URL", "http://127.0.0.1:8083")

# id safety — mirrors _action_exec._SAFE_VALUE (forbids '/', whitespace, shell meta).
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_UNSIGNED = "unsigned-pending-MS003"
_WRITE_LOCK = threading.Lock()

# verb → the registry gate field it advances (note: `eval` writes `test_eval`).
_GATE_FIELD = {"human": "human", "snapshot": "snapshot",
               "eval": "test_eval", "oracle": "oracle"}
_ALL_GATES = ("snapshot", "test_eval", "oracle", "human")


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


def _tag_safe(adapter_id: str) -> str:
    """Map an _SAFE_ID (which allows @ : = -) to a _SAFE_TAG-clean snapshot tag."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", adapter_id)


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".adapter-gate-", suffix=".tmp")
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
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _emit_span(record: dict[str, Any]) -> None:
    """Best-effort OCSF-5001 (Configuration Change) M049 span. Never raises."""
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = {
        "trace_id": f"adapter-gate-{record['id']}-{ms:x}",
        "span_id": f"agt-{ms:x}",
        "parent_span_id": None,
        "operation": "adapter_gate_advance",
        "start_ts": record["decided_ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"adapter_id": record["id"], "gate": record["gate"],
                       "verb": record["verb"]},
        "ocsf_class": "5001",
        "actor": record["decided_by"],
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "signature": record["signature"],
        "schema_version": SCHEMA_VERSION,
    }
    try:
        SPAN_STORE.parent.mkdir(parents=True, exist_ok=True)
        with SPAN_STORE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span) + "\n")
    except OSError:
        pass


# ── evidence gatherers (real evidence or a structured refusal) ────────────────

def _human_evidence(actor: str, rationale: str) -> dict[str, Any]:
    """The --confirm IS the operator's attestation — always producible."""
    return {"ok": True, "attested_by": actor, "rationale": rationale or ""}


def _snapshot_evidence(adapter_id: str, dataset_key: str, confirm: bool) -> dict[str, Any]:
    """A real ZFS rollback-point (SDD-050). Confirm-gated: without --confirm the
    create is DRY-RUN (no real snapshot) → honest-defer."""
    tag = "gate-" + _tag_safe(adapter_id)
    r = _rollback.create(dataset_key, tag, confirm=confirm)
    if r.get("dry_run"):
        return {"ok": False, "reason":
                f"snapshot DRY-RUN ({r.get('would_run')}) — no real ZFS snapshot; "
                "re-run with --confirm on a ZFS host"}
    if r.get("ok"):
        return {"ok": True, "target": r.get("target"), "dataset": r.get("dataset")}
    return {"ok": False, "reason":
            f"ZFS snapshot not created ({r.get('error') or r.get('target')}) — "
            "is the dataset present on this host?"}


def _eval_evidence(adapter_id: str) -> dict[str, Any]:
    """A real passing record from the Eval-Value fabric log (evals.jsonl, D-10).
    Does NOT run the heavy benchmark — consumes existing evidence (Q-061-C)."""
    # pass the store explicitly (module attr, resolved at call-time) so it stays
    # the single monkeypatchable source rather than load_runs's def-time default.
    runs = [r for r in _eval.load_runs(_eval.EVAL_STORE)
            if str(r.get("adapter_id")) == adapter_id]
    if not runs:
        return {"ok": False, "reason":
                f"no eval record for {adapter_id!r} — run "
                f"`sovereign-osctl models eval run {adapter_id}` first"}
    runs.sort(key=lambda r: str(r.get("ts") or ""))
    latest = runs[-1]
    if not _eval._passed(latest):
        return {"ok": False, "reason":
                f"latest eval for {adapter_id!r} did not pass "
                f"(score={latest.get('score')!r}) — needs a passing run"}
    return {"ok": True, "score": latest.get("score"),
            "trace_id": latest.get("trace_id"), "eval_ts": latest.get("ts")}


def _oracle_reachable(endpoint: str) -> bool:
    try:
        with urllib.request.urlopen(f"{endpoint}/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 — unreachable → not reachable, never raise
        return False


def _oracle_judge(adapter_id: str, endpoint: str) -> str | None:
    """A minimal PASS/FAIL judge on the oracle backend (OpenAI-compatible). A real
    inference call — hardware-gated, so untested against a live backend today
    (Q-061-D: full judge-prompt tuning is a follow-up). Returns 'pass'/'fail'/None."""
    prompt = (f"You are a promotion oracle. Reply with exactly PASS or FAIL: is the "
              f"LoRA adapter {adapter_id} safe to promote based on its evaluation? "
              "Answer PASS only if clearly safe.")
    body = json.dumps({"model": "oracle",
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 4, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(f"{endpoint}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
        text = (d.get("choices", [{}])[0].get("message", {}).get("content", "") or "").upper()
    except Exception:  # noqa: BLE001 — any transport error → no verdict
        return None
    if "PASS" in text:
        return "pass"
    if "FAIL" in text:
        return "fail"
    return None


def _oracle_evidence(adapter_id: str) -> dict[str, Any]:
    """Probe the oracle backend + judge. Unreachable (today's hardware-gated
    reality) → honest-defer; reachable + PASS verdict → evidence."""
    if not _oracle_reachable(ORACLE_URL):
        return {"ok": False, "reason":
                f"oracle backend unreachable at {ORACLE_URL} — start it "
                "(scripts/inference/start-oracle-core.sh); gate stays pending"}
    verdict = _oracle_judge(adapter_id, ORACLE_URL)
    if verdict == "pass":
        return {"ok": True, "judge": "oracle-core", "endpoint": ORACLE_URL,
                "verdict": "pass"}
    return {"ok": False, "reason":
            f"oracle judge did not return PASS (verdict={verdict!r})"}


# ── the shared gate-advance write path ────────────────────────────────────────

def _advance_gate(adapter_id: str, verb: str, *, evidence: dict[str, Any],
                  confirm: bool, actor: str) -> dict[str, Any]:
    """Set `gates[field]="passed"` + record `gate_evidence[field]` provenance.
    DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    field = _GATE_FIELD[verb]
    with _WRITE_LOCK:
        rows = {r["id"]: r for r in _af.list_adapters(ADAPTER_REGISTRY)}
        target = rows.get(adapter_id)
        if target is None:
            return {"ok": False, "code": 2, "id": adapter_id,
                    "error": f"no adapter resolved for {adapter_id!r} "
                    f"({'empty inventory' if not rows else 'unknown adapter'})"}
        gates = target.get("gates") or {}
        if gates.get(field) == "passed":
            return {"ok": True, "code": 200, "verb": verb, "id": adapter_id,
                    "gate": field, "idempotent": True,
                    "note": f"gate {field!r} already passed"}
        if (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1":
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": verb, "id": adapter_id,
                    "gate": field, "dry_run": True, "evidence": evidence,
                    "would": {"gate_transition": f"{gates.get(field, 'pending')}→passed"},
                    "note": f"DRY-RUN ({why}) — would advance {field} to passed"}
        ts = _now()
        reg = _af._read_json(ADAPTER_REGISTRY)
        adapters = reg.get("adapters")
        if not isinstance(adapters, dict):
            adapters = {}
        entry = adapters.get(adapter_id)
        if not isinstance(entry, dict):
            entry = {}
        g = entry.get("gates")
        if not isinstance(g, dict):
            g = {k: "pending" for k in _ALL_GATES}
        g[field] = "passed"
        entry["gates"] = g
        ge = entry.get("gate_evidence")
        if not isinstance(ge, dict):
            ge = {}
        ge[field] = {**evidence, "ts": ts, "by": actor}
        entry["gate_evidence"] = ge
        entry.setdefault("status", target.get("status", "pending"))
        entry.setdefault("base_model", target.get("base_model"))
        adapters[adapter_id] = entry
        reg["adapters"] = adapters
        try:
            _atomic_write(ADAPTER_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "id": adapter_id, "error": f"write failed: {e}"}
        rec = _signed({"id": adapter_id, "verb": f"gate-{verb}", "gate": field,
                       "decided_by": actor, "decided_ts": ts, "evidence": ge[field],
                       "signature": _UNSIGNED})
        _append_ledger(rec)
        _emit_span(rec)
        return _signed({"ok": True, "code": 200, "verb": verb, "id": adapter_id,
                        "gate": field, "state": "passed", "evidence": ge[field],
                        "signature": _UNSIGNED})


def _defer(verb: str, adapter_id: str, reason: str) -> dict[str, Any]:
    return {"ok": False, "code": 2, "verb": verb, "id": adapter_id,
            "gate": _GATE_FIELD[verb], "deferred": True,
            "error": f"{_GATE_FIELD[verb]} gate not advanced — {reason}"}


# ── the four gate verbs ───────────────────────────────────────────────────────

def gate_human(adapter_id: str, *, confirm: bool = False, actor: str = "operator",
               rationale: str = "") -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe adapter id {adapter_id!r} (must match _SAFE_VALUE, no '/')"}
    ev = _human_evidence(actor, rationale)
    return _advance_gate(adapter_id, "human", evidence=ev, confirm=confirm, actor=actor)


def gate_snapshot(adapter_id: str, *, dataset_key: str = "models", confirm: bool = False,
                  actor: str = "operator") -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe adapter id {adapter_id!r} (must match _SAFE_VALUE, no '/')"}
    ev = _snapshot_evidence(adapter_id, dataset_key, confirm)
    if not ev["ok"]:
        return _defer("snapshot", adapter_id, ev["reason"])
    return _advance_gate(adapter_id, "snapshot", evidence=ev, confirm=confirm, actor=actor)


def gate_eval(adapter_id: str, *, confirm: bool = False,
              actor: str = "operator") -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe adapter id {adapter_id!r} (must match _SAFE_VALUE, no '/')"}
    ev = _eval_evidence(adapter_id)
    if not ev["ok"]:
        return _defer("eval", adapter_id, ev["reason"])
    return _advance_gate(adapter_id, "eval", evidence=ev, confirm=confirm, actor=actor)


def gate_oracle(adapter_id: str, *, confirm: bool = False,
                actor: str = "operator") -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(adapter_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe adapter id {adapter_id!r} (must match _SAFE_VALUE, no '/')"}
    ev = _oracle_evidence(adapter_id)
    if not ev["ok"]:
        return _defer("oracle", adapter_id, ev["reason"])
    return _advance_gate(adapter_id, "oracle", evidence=ev, confirm=confirm, actor=actor)


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M046 adapter gate-producer (SDD-061)")
    sub = ap.add_subparsers(dest="cmd")
    for v in ("human", "snapshot", "eval", "oracle"):
        g = sub.add_parser(v)
        g.add_argument("id")
        g.add_argument("--actor", default="operator")
        g.add_argument("--confirm", action="store_true")
        if v == "human":
            g.add_argument("--rationale", default="")
        if v == "snapshot":
            g.add_argument("--dataset", default="models")
    args = ap.parse_args(argv)
    if args.cmd == "human":
        r = gate_human(args.id, confirm=args.confirm, actor=args.actor, rationale=args.rationale)
    elif args.cmd == "snapshot":
        r = gate_snapshot(args.id, dataset_key=args.dataset, confirm=args.confirm, actor=args.actor)
    elif args.cmd == "eval":
        r = gate_eval(args.id, confirm=args.confirm, actor=args.actor)
    elif args.cmd == "oracle":
        r = gate_oracle(args.id, confirm=args.confirm, actor=args.actor)
    else:
        ap.error("a gate is required: human|snapshot|eval|oracle")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
