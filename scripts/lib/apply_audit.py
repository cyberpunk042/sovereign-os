"""scripts/lib/apply_audit.py — R327 (E9.M11) helper module.

Central audit-log primitive for sovereign-os apply verbs. Any
script that mutates state (triple-gate per SDD-031 §composition)
imports `record_apply()` to append one row to
/var/lib/sovereign-os/apply-audit.jsonl.

Row schema (operator-stable, JSONL-friendly):

  {
    "schema_version": "1.0.0",
    "round": "R327",
    "tick_at": "<ISO-8601 UTC>",
    "tick_at_epoch": <float>,
    "verb": "<sovereign-osctl verb name>",
    "round_origin": "<R<n>>",          # round that owns the verb
    "gates_satisfied": <bool>,
    "gates_detail": {<gate-name>: <bool>, ...},
    "what_was_written": {<key>: <value>},
    "target_path": "<path>",
    "wrote": <bool>,
    "op_user": "<getpass.getuser()>",
    "host": "<socket.gethostname()>",
    "rc": <int>,
  }

Read-side: `query()` returns list of rows, optionally filtered by
verb / time-window / wrote-only.

Operator-overlay (R283/SDD-030) NOT supported on this module
directly (it's a primitive) — the consumer script's overlay can
control whether the audit log is enabled via a `disable_apply_audit`
knob.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
ROUND = "R327"

DEFAULT_AUDIT_PATH = Path("/var/lib/sovereign-os/apply-audit.jsonl")


def _audit_path(override: Path | str | None = None) -> Path:
    """Resolve audit-log path; env > argument > default."""
    env = os.environ.get("SOVEREIGN_OS_APPLY_AUDIT_PATH")
    if env:
        return Path(env)
    if override is not None:
        return Path(override)
    return DEFAULT_AUDIT_PATH


def record_apply(
    *,
    verb: str,
    round_origin: str,
    gates_satisfied: bool,
    gates_detail: dict[str, bool],
    what_was_written: dict[str, Any] | None = None,
    target_path: str | None = None,
    wrote: bool = False,
    rc: int = 0,
    audit_path_override: Path | str | None = None,
) -> dict[str, Any]:
    """Append one row to the apply-audit log. Returns the row.

    NEVER raises — audit failure must not take down an apply verb.
    Returns the row dict even if the write failed (caller can log).
    """
    now = time.time()
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "tick_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "tick_at_epoch": now,
        "verb": verb,
        "round_origin": round_origin,
        "gates_satisfied": bool(gates_satisfied),
        "gates_detail": dict(gates_detail or {}),
        "what_was_written": dict(what_was_written or {}),
        "target_path": target_path,
        "wrote": bool(wrote),
        "rc": int(rc),
        "op_user": getpass.getuser() if hasattr(getpass, "getuser") else "?",
        "host": socket.gethostname(),
    }
    path = _audit_path(audit_path_override)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        row["_audit_log_path"] = str(path)
        row["_audit_log_wrote"] = True
    except OSError as e:
        row["_audit_log_path"] = str(path)
        row["_audit_log_wrote"] = False
        row["_audit_log_error"] = str(e)
    return row


def query(
    audit_path_override: Path | str | None = None,
    verb: str | None = None,
    wrote_only: bool = False,
    since_epoch: float | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read the audit log, filter, return list of rows (newest last)."""
    path = _audit_path(audit_path_override)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict):
            continue
        if verb is not None and r.get("verb") != verb:
            continue
        if wrote_only and not r.get("wrote"):
            continue
        if since_epoch is not None:
            ts = r.get("tick_at_epoch", 0)
            if not isinstance(ts, (int, float)) or ts < since_epoch:
                continue
        rows.append(r)
    if limit is not None and limit > 0:
        rows = rows[-limit:]
    return rows
