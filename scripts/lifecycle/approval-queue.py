#!/usr/bin/env python3
"""scripts/lifecycle/approval-queue.py — operator approval-queue + stage-gate
core (M060 D-06 / R10088-R10092).

The data model behind the D-06 pending-approvals cockpit dashboard — the
operator-controlled axiom made legible. Reads the lifecycle/authority engine's
published approval queue + M065 stage-gate state, and reports whether the MS003
operator key is loaded.

  M065 Five Stage Gates (E0628-E0632, dump 79-326 verbatim):
    SG1 (after PR 3)  structural foundation review
    SG2 (after PR 4)  substrate decision (resolves Q-016 + Q-001)
    SG3 (after PR 6)  schema lock-in
    SG4 (after PR 8)  whitelabel mechanism + legal posture
    SG5 (after PR 10) foundation-complete (authorizes Stage 2)
  Hard rule (E0634, dump 330): "No PR opens past a gate without operator
  sign-off." Gate state ∈ {pending, signed, bypassed}.

  Approval severity (MS041 high-risk + MS042 4-severity): critical/high/medium/low.

Sovereignty: stdlib-only. The queue path follows the /run/sovereign-os/*.json
convention. Absent queue → empty list + all gates pending + profile=private
(the dashboard's offline default per MS040 R09535), NEVER a crash. The operator
key is reported by PRESENCE only — the key material is never read or exposed.
This is the `core` surface of the §1g 8-surface ladder for the approvals
module; `scripts/operator/approvals-api.py` serves it, `sovereign-osctl
approvals` drives it, the D-06 webapp renders it.

  approval-queue.py pending [--json]   full model (approvals/gates/profile/summary)
  approval-queue.py gates   [--json]   the M065 SG1-SG5 state only
  approval-queue.py key     [--json]   MS003 operator-key presence status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

APPROVALS_QUEUE = Path(os.environ.get(
    "SOVEREIGN_OS_APPROVALS", "/run/sovereign-os/approvals.json",
))
# MS003 operator key: presence-only status. An optional status JSON (with
# fingerprint/expiry/hardware_token) overrides; otherwise we report whether the
# key file itself is present — never reading its contents.
OPERATOR_KEY_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_OPERATOR_KEY", str(Path.home() / ".sovereign-os" / "operator.key"),
))
OPERATOR_KEY_STATUS = Path(os.environ.get(
    "SOVEREIGN_OS_OPERATOR_KEY_STATUS", "/run/sovereign-os/operator-key-status.json",
))

# M065 verbatim (E0628-E0632). gate → (after-PR, description).
STAGE_GATES = {
    "SG1": (3, "structural foundation review"),
    "SG2": (4, "substrate decision (Q-016 + Q-001)"),
    "SG3": (6, "schema lock-in"),
    "SG4": (8, "whitelabel mechanism + legal posture"),
    "SG5": (10, "foundation-complete (authorizes Stage 2)"),
}
_VALID_GATE_STATE = frozenset({"pending", "signed", "bypassed"})
_VALID_SEVERITY = frozenset({"critical", "high", "medium", "low"})
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _normalise(rec: dict[str, Any]) -> dict[str, Any]:
    sev = rec.get("severity")
    if sev not in _VALID_SEVERITY:
        sev = "medium"
    return {
        "id": str(rec.get("id", "?")),
        "title": rec.get("title", "(untitled approval)"),
        "severity": sev,
        "gate": rec.get("gate", "L4→L5"),
        "actor": rec.get("actor", "unknown"),
        "kind": rec.get("kind", "transition"),
        "profile": rec.get("profile", "private"),
        "ts": rec.get("ts"),
        "trace_id": rec.get("trace_id"),
        "summary": rec.get("summary", ""),
        "context": rec.get("context"),
        "diff_url": rec.get("diff_url"),
    }


def _gates(reg: dict[str, Any]) -> dict[str, str]:
    raw = reg.get("gates") or {}
    out = {}
    for g in STAGE_GATES:
        v = raw.get(g)
        out[g] = v if v in _VALID_GATE_STATE else "pending"
    return out


def list_approvals(queue: Path = APPROVALS_QUEUE) -> list[dict[str, Any]]:
    reg = _read_json(queue)
    raw = reg.get("approvals")
    if not isinstance(raw, list):
        return []
    rows = [_normalise(r) for r in raw if isinstance(r, dict) and r.get("id")]
    rows.sort(key=lambda a: (_SEVERITY_ORDER.get(a["severity"], 9), a["ts"] or ""))
    return rows


def pending(queue: Path = APPROVALS_QUEUE) -> dict[str, Any]:
    """The full D-06 dashboard model."""
    reg = _read_json(queue)
    approvals = list_approvals(queue)
    ts_values = [a["ts"] for a in approvals if a["ts"]]
    summary = {
        "pending": len(approvals),
        "critical": sum(1 for a in approvals if a["severity"] == "critical"),
        "high": sum(1 for a in approvals if a["severity"] == "high"),
        "oldest_ts": min(ts_values) if ts_values else None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "approvals": approvals,
        "gates": _gates(reg),
        "profile": reg.get("profile", "private"),
        "summary": summary,
    }


def gates_reference(queue: Path = APPROVALS_QUEUE) -> dict[str, Any]:
    reg = _read_json(queue)
    state = _gates(reg)
    return {g: {"after_pr": pr, "description": desc, "state": state[g]}
            for g, (pr, desc) in STAGE_GATES.items()}


def operator_key_status() -> dict[str, Any]:
    """MS003 operator-key PRESENCE status — never reads the key material.
    A status JSON (if published) provides fingerprint/expiry/hardware_token;
    otherwise we report whether the key file exists at all."""
    status = _read_json(OPERATOR_KEY_STATUS)
    if status:
        return {
            "fingerprint": status.get("fingerprint"),
            "source": status.get("source", str(OPERATOR_KEY_STATUS)),
            "expires_at": status.get("expires_at"),
            "hardware_token": bool(status.get("hardware_token")),
            "loaded": bool(status.get("fingerprint") or status.get("loaded")),
        }
    if OPERATOR_KEY_PATH.is_file():
        return {
            "fingerprint": None,  # presence only — material never read
            "source": str(OPERATOR_KEY_PATH),
            "expires_at": None,
            "hardware_token": False,
            "loaded": True,
        }
    return {
        "fingerprint": None, "source": None, "expires_at": None,
        "hardware_token": False, "loaded": False,
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="operator approval-queue + stage-gate core (M060 D-06)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("pending", "gates", "key"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "pending"
    if cmd == "gates":
        _print(gates_reference())
    elif cmd == "key":
        _print(operator_key_status())
    else:
        _print(pending())
    return 0


if __name__ == "__main__":
    sys.exit(main())
