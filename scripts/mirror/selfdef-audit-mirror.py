#!/usr/bin/env python3
"""scripts/mirror/selfdef-audit-mirror.py — READ-ONLY consumer of the
selfdef audit chain mirror (M060 D-16 / MS016 audit-chain integrity).

The data model behind the D-16 audit-chain cockpit dashboard. CROSS-REPO
MIRROR: the authoritative audit chain lives in selfdef (the IPS) — MS016
append-only audit log + MS049 13-field span entries + SHA-256 hash chain
+ OCSF taxonomy (process / file / network / host / authority), published
through the MS007 typed-mirror crate `selfdef-audit-mirror` (read-only)
and the daemon-resident `selfdef-audit-registry` (the resident-side
chain builder + integrity checker). sovereign-os renders it READ-ONLY.
Audit chain is APPEND-ONLY by MS016 R03567 doctrine — the operator has
NO mutation surface (no release, no replay, no edit); the chain IS the
IPS truth.

Mirror artifact (selfdef-audit-mirror::AuditMirrorSnapshot 1.0.0):
  schema_version · captured_at · summaries[{category,total,allow,deny,
  ask,sandbox}] · integrity{head_hash,total_entries,continuous,
  first_gap_at,verified_at} · spans[{trace_id,profile,model,provider,
  hardware,tokens_prompt,tokens_completion,latency_ms,cost_millicents,
  risk_score,memory_refs,tool_refs,policy_result,branch_id,ocsf_category,
  closed_at,prev_chain_hash,chain_hash,signature}] · signature

Sovereignty: stdlib-only. Absent artifact → empty spans + offline
mirror_status (graceful), NEVER a crash. The published spans list is
the bounded tail (most recent N) — the full historic chain lives in
the daemon's audit log; integrity continuity is verified at the daemon
side via `selfdef_audit_registry::verify_tail`.

  selfdef-audit-mirror.py snapshot [--json]   full dashboard model
  selfdef-audit-mirror.py integrity [--json]  chain integrity report only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

AUDIT_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_AUDIT_MIRROR",
    "/run/sovereign-os/selfdef-mirror/audit.json",
))

# MS026 OCSF taxonomy buckets per the audit-mirror crate.
OCSF_CATEGORIES = (
    "process_activity", "file_system_activity", "network_activity",
    "host_inventory", "authority_decision", "other",
)

# MS033 4-state policy outcome (per R07731-R07734).
POLICY_OUTCOMES = ("allow", "deny", "ask", "sandbox")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _summaries(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("summaries") or []
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        cat = s.get("category", "other")
        if cat not in OCSF_CATEGORIES:
            cat = "other"
        out.append({
            "category": cat,
            "total": int(s.get("total", 0)),
            "allow":   int(s.get("allow", 0)),
            "deny":    int(s.get("deny", 0)),
            "ask":     int(s.get("ask", 0)),
            "sandbox": int(s.get("sandbox", 0)),
        })
    return out


def _integrity(mirror: dict[str, Any]) -> dict[str, Any]:
    raw = mirror.get("integrity")
    if not isinstance(raw, dict):
        return {
            "head_hash": "",
            "total_entries": 0,
            "continuous": True,
            "first_gap_at": None,
            "verified_at": "",
        }
    return {
        "head_hash":     str(raw.get("head_hash", "")),
        "total_entries": int(raw.get("total_entries", 0)),
        "continuous":    bool(raw.get("continuous", True)),
        "first_gap_at":  raw.get("first_gap_at"),
        "verified_at":   str(raw.get("verified_at", "")),
    }


def _spans(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("spans")
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict) or not s.get("trace_id"):
            continue
        policy = s.get("policy_result", "allow")
        if policy not in POLICY_OUTCOMES:
            policy = "allow"
        cat = s.get("ocsf_category", "other")
        if cat not in OCSF_CATEGORIES:
            cat = "other"
        out.append({
            "trace_id": str(s["trace_id"]),
            "profile": s.get("profile", ""),
            "model": s.get("model", ""),
            "provider": s.get("provider", ""),
            "hardware": s.get("hardware", ""),
            "tokens_prompt": int(s.get("tokens_prompt", 0)),
            "tokens_completion": int(s.get("tokens_completion", 0)),
            "latency_ms": int(s.get("latency_ms", 0)),
            "cost_millicents": int(s.get("cost_millicents", 0)),
            "risk_score": int(s.get("risk_score", 0)),
            "memory_refs": s.get("memory_refs") or [],
            "tool_refs": s.get("tool_refs") or [],
            "policy_result": policy,
            "branch_id": s.get("branch_id", ""),
            "ocsf_category": cat,
            "closed_at": s.get("closed_at", ""),
            "prev_chain_hash": s.get("prev_chain_hash", ""),
            "chain_hash": s.get("chain_hash", ""),
            "signature": s.get("signature", ""),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-16 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(AUDIT_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-audit-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": _summaries(mirror),
        "integrity": _integrity(mirror),
        "spans": _spans(mirror),
        "signature": mirror.get("signature"),  # MS003 sig over canonical JSON
    }


def trace(trace_id: str) -> dict[str, Any]:
    """Return a single audit span by trace_id, or a not-found envelope.

    M013 E0112 — "tracing is crucial. trace_id / span_id / branch_id /
    commit_id". During incident response operators need to inspect ONE
    trace without grepping through the full snapshot — this is the
    surface that delivers it.

    The returned envelope carries the span if found, plus the
    `prev_chain_hash` of the previous span and the `chain_hash` of the
    next span — so an operator inspecting one trace can walk the chain
    backward + forward without re-reading the snapshot.
    """
    snap = snapshot()
    spans = snap.get("spans") or []
    idx = None
    for i, s in enumerate(spans):
        if s.get("trace_id") == trace_id:
            idx = i
            break
    if idx is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "found": False,
            "mirror_status": snap.get("mirror_status"),
            "_hint": (
                f"trace_id `{trace_id}` not in the bounded tail (most recent "
                f"{len(spans)} spans). The full historic chain lives in the "
                f"daemon's append-only audit log; query with "
                f"`selfdefctl audit show --trace-id {trace_id}` on the IPS host."
            ),
        }
    span = spans[idx]
    prev = spans[idx - 1] if idx > 0 else None
    nxt = spans[idx + 1] if idx + 1 < len(spans) else None
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "found": True,
        "mirror_status": snap.get("mirror_status"),
        "span": span,
        # Chain walkers — operator can `... trace <prev_trace_id>` /
        # `... trace <next_trace_id>` to walk the audit chain.
        "prev_trace_id": prev.get("trace_id") if prev else None,
        "next_trace_id": nxt.get("trace_id") if nxt else None,
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef audit-chain mirror consumer (M060 D-16)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "integrity"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    # M013 E0112: trace-id lookup. Distinct subparser because it takes
    # a positional argument the others don't.
    sp_trace = sub.add_parser("trace", help="lookup ONE span by trace_id (M013 E0112)")
    sp_trace.add_argument("trace_id", help="trace_id to lookup (matches against MS049 span.trace_id field)")
    sp_trace.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "integrity":
        _print(snapshot()["integrity"])
    elif cmd == "trace":
        result = trace(args.trace_id)
        _print(result)
        # Exit 1 if not found so scripts (e.g., m060-doctor follow-up
        # tooling) can branch on "is this trace_id in the published
        # tail?" without parsing JSON.
        return 0 if result["found"] else 1
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
