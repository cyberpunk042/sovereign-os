#!/usr/bin/env python3
"""scripts/lifecycle/session-runtime.py — M057 session-process runtime / producer
(SDD-058 / SDD-057 Stage 4).

The missing producer for the M057 session registry: it spawns a real operator task
command as a tracked process and REGISTERS it in /run/sovereign-os/sessions.json
with a real `pid` (+ cgroup + dataset). That real pid is what makes the SDD-057
save-state `criu-checkpoint` layer actually capturable — turning the 4/5 partial
save-state into a true 5/5.

  sessions start [--dataset <key>] -- <cmd> [args...]   spawn + register a session
  sessions stop <id> [--confirm]                          stop the scope + archive
  sessions list                                           the registered sessions

A session process = the operator's task command, spawned under a transient
`systemd-run --scope` (a real cgroup — the CRIU checkpoint target + resource
control). The session starts `active` at M057 step 1 (Intake); the full 12-step
lifecycle orchestration is the m009 deterministic-cortex deep work (Stage N).

SECURITY (R10212 + arbitrary-exec): `sessions start` runs an OPERATOR-SUPPLIED
command — arbitrary code execution. It is CLI-ONLY and is DELIBERATELY NOT a
cockpit control: no config/control-systems.yaml entry, no control-exec-api wiring,
no cockpit sudoers grant. The web can never reach it (`_action_exec` runs only
registered controls). The task argv is passed as a LIST to systemd-run (no shell,
no injection). Only the already-registered-session controls (hibernate / save-state)
stay web-triggerable.

Safety: DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset; the real
`systemd-run` spawn + `systemctl stop` run only live. Atomic single-flight writes.

stdlib-only. Exit: 0 ok/dry-run · 1 write/spawn error · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent


def _imp(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_sr = _imp("_session_registry_for_runtime", _HERE / "session-registry.py")
_rp = _imp("_rollback_points_for_runtime", _HERE / "rollback-points.py")

SESSION_REGISTRY = _sr.SESSION_REGISTRY
SCHEMA_VERSION = "1.0.0"
_UNSIGNED = "unsigned-pending-MS003"

LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_SESSION_LEDGER", "/var/log/sovereign-os/session-decisions.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_WRITE_LOCK = threading.Lock()
# per-session ZFS datasets are children of the shared `agents` dataset (SDD-065).
_AGENTS_DATASET = _rp._DATASETS.get("agents", "tank/agents")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id() -> str:
    return f"sess-{secrets.token_hex(4)}"


def _atomic_write(path: Path, obj: Any) -> None:
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


def _run(cmd: list[str], timeout: float = 30.0) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _spawn_scope(scope_cmd: list[str], unit: str) -> int | None:
    """Spawn the task under a transient systemd scope (detached) + return its
    MainPID. Best-effort — host-only (needs systemd)."""
    if shutil.which("systemd-run") is None:
        return None
    try:
        subprocess.Popen(scope_cmd, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    out = _run(["systemctl", "show", f"{unit}.scope", "-p", "MainPID", "--value"])
    if out:
        try:
            pid = int(out.strip())
            return pid if pid > 0 else None
        except ValueError:
            return None
    return None


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


def _append_ledger(record: dict[str, Any]) -> None:
    """Best-effort durable append to the session-decisions JSONL. Never raises."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass


def _emit_span(op: str, sid: str, extra: dict[str, Any]) -> None:
    """Best-effort OCSF-5001 (Configuration Change) M049 span. Never raises."""
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = _signed({
        "trace_id": f"session-{op}-{sid}-{ms:x}",
        "span_id": f"srt-{ms:x}",
        "parent_span_id": None,
        "operation": f"session_{op}",
        "start_ts": _now(),
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"session_id": sid, "op": op, **extra},
        "ocsf_class": "5001",
        "actor": "reaper",
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "signature": _UNSIGNED,
        "schema_version": SCHEMA_VERSION,
    })
    try:
        SPAN_STORE.parent.mkdir(parents=True, exist_ok=True)
        with SPAN_STORE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span) + "\n")
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    """Host-gated liveness — a session's tracked process. os.kill(pid, 0):
    ProcessLookupError → dead; PermissionError → alive (exists, not ours); anything
    we cannot determine → treat as alive (conservative — never reap on doubt)."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return True


def _zfs_create(dataset_path: str, *, confirm: bool = False) -> dict[str, Any]:
    """Host-gated `zfs create <dataset_path>` — the per-session child dataset
    (SDD-065). DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset; skips honestly
    when zfs is absent (SB-077 — never claims a dataset it did not create). Reuses the
    rollback-points host-gating idiom (shutil.which + _run + DRY-RUN)."""
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    if dry:
        return {"ok": True, "created": False, "dry_run": True, "path": dataset_path,
                "would_run": ["zfs", "create", dataset_path]}
    if shutil.which("zfs") is None:
        return {"ok": True, "created": False, "path": dataset_path,
                "reason": "zfs unavailable (host-only) — session uses the shared dataset"}
    out = _run(["zfs", "create", dataset_path])
    return {"ok": True, "created": out is not None, "path": dataset_path,
            "ran": ["zfs", "create", dataset_path]}


def _register(entry: dict[str, Any]) -> bool:
    """Append a session to the registry atomically (the producer write path)."""
    with _WRITE_LOCK:
        reg = _sr._read_registry(SESSION_REGISTRY)
        sessions = reg.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        sessions.append(entry)
        reg["sessions"] = sessions
        try:
            _atomic_write(SESSION_REGISTRY, reg)
        except OSError:
            return False
    return True


def start(task_argv: list[str], *, dataset_key: str = "agents",
          actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """Spawn an operator task command as a tracked session process + register it.
    CLI-only (never web-triggerable). DRY-RUN unless --confirm AND
    SOVEREIGN_OS_DRY_RUN unset."""
    if not task_argv:
        return {"ok": False, "code": 2, "error": "no task command (use: sessions start -- <cmd> [args...])"}
    if dataset_key not in _rp._DATASETS:
        return {"ok": False, "code": 2,
                "error": f"unknown dataset key {dataset_key!r} (known: {sorted(_rp._DATASETS)})"}
    sid = _new_id()
    unit = f"sovereign-session-{sid}"
    scope_cmd = ["systemd-run", "--scope", f"--unit={unit}", "--", *task_argv]
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"

    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"ok": True, "code": 200, "verb": "start", "id": sid, "unit": unit,
                "dataset": dataset_key, "task": task_argv, "dry_run": True,
                "would_run": scope_cmd,
                "note": f"DRY-RUN ({why}) — spawns nothing; live registers a real "
                        "pid-tracked session (systemd-run --scope) — the CRIU "
                        "save-state target"}

    pid = _spawn_scope(scope_cmd, unit)
    if pid is None:
        return {"ok": False, "code": 1, "id": sid,
                "error": "spawn failed — systemd-run unavailable or the scope did "
                         "not report a MainPID (host-only)"}
    # SDD-065 — best-effort per-session ZFS child dataset (tank/agents/<sid>). ADDITIVE:
    # the enum `dataset` key stays for save-state/exec-rail compatibility; `dataset_path`
    # is set ONLY when the child dataset was really created (honest — SB-077).
    entry = {
        "id": sid, "kind": "task", "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "state": "active", "step": 1, "srp_agent": "Conductor",
        "started_at": _now(), "eta_seconds": None, "branch_count": 0,
        "pid": pid, "cgroup": f"{unit}.scope", "dataset": dataset_key,
        "task": " ".join(task_argv), "started_by": actor,
    }
    zr = _zfs_create(f"{_AGENTS_DATASET}/{sid}", confirm=confirm)
    if zr.get("created"):
        entry["dataset_path"] = zr["path"]
    if not _register(entry):
        return {"ok": False, "code": 1, "id": sid, "pid": pid,
                "error": "session spawned but registry write failed"}
    res = {"ok": True, "code": 200, "verb": "start", "id": sid, "pid": pid,
           "cgroup": f"{unit}.scope", "dataset": dataset_key, "state": "active", "step": 1}
    if entry.get("dataset_path"):
        res["dataset_path"] = entry["dataset_path"]
    return res


def reap(*, actor: str = "operator") -> dict[str, Any]:
    """SDD-065 — the session reaper: archive `active` sessions whose tracked process is
    already dead (a state-reconciliation janitor, like the SDD-064 memory reconcile).
    Only `active` pid-bearing sessions are considered — `hibernated`/`paused`/terminal
    are skipped (their pid is intentionally gone). No `--confirm`: reconciling state to
    reality (the process is gone regardless) is safe bookkeeping, not a destructive act.
    CLI/timer-only — adds no web mutation path. Best-effort atomic write + ledger + span."""
    reaped: list[str] = []
    with _WRITE_LOCK:
        reg = _sr._read_registry(SESSION_REGISTRY)
        sessions = reg.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        changed = False
        for s in sessions:
            if not isinstance(s, dict) or s.get("state") != "active":
                continue
            pid = s.get("pid")
            if not isinstance(pid, int) or pid <= 0:
                continue  # no tracked pid to check
            if _pid_alive(pid):
                continue  # still running
            s["state"] = "archived"
            s["reaped_at"] = _now()
            reaped.append(str(s.get("id")))
            changed = True
        if changed:
            reg["sessions"] = sessions
            try:
                _atomic_write(SESSION_REGISTRY, reg)
            except OSError as e:
                return {"ok": False, "code": 1, "error": f"registry write failed: {e}"}
    for sid in reaped:
        _append_ledger(_signed({"verb": "reap", "id": sid, "ts": _now(), "actor": actor,
                                "reason": "process-exited", "signature": _UNSIGNED}))
        _emit_span("reap", sid, {"reason": "process-exited"})
    return {"ok": True, "code": 200, "verb": "reap", "reaped": reaped, "count": len(reaped)}


def stop(session_id: str, *, actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """Stop a session's scope + transition it to `archived`. DRY-RUN default."""
    if not _SAFE_ID.fullmatch(session_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe session id {session_id!r} (must match _SAFE_VALUE, no '/')"}
    with _WRITE_LOCK:
        reg = _sr._read_registry(SESSION_REGISTRY)
        sessions = reg.get("sessions")
        if not isinstance(sessions, list):
            sessions = []
        target = next((s for s in sessions
                       if isinstance(s, dict) and str(s.get("id")) == session_id), None)
        if target is None:
            return {"ok": False, "code": 2, "id": session_id,
                    "error": f"no session resolved for {session_id!r}"}
        cgroup = target.get("cgroup") or f"sovereign-session-{session_id}.scope"
        dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
        if dry:
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            return {"ok": True, "code": 200, "verb": "stop", "id": session_id,
                    "dry_run": True, "would_run": ["systemctl", "stop", cgroup],
                    "would": {"state_transition": f"{target.get('state')}→archived"},
                    "note": f"DRY-RUN ({why}) — stops the scope + archives the session"}
        _run(["systemctl", "stop", cgroup])
        target["state"] = "archived"
        reg["sessions"] = sessions
        try:
            _atomic_write(SESSION_REGISTRY, reg)
        except OSError as e:
            return {"ok": False, "code": 1, "id": session_id, "error": f"write failed: {e}"}
        return {"ok": True, "code": 200, "verb": "stop", "id": session_id, "state": "archived"}


def session_list() -> list[dict[str, Any]]:
    return _sr.list_sessions(SESSION_REGISTRY)


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M057 session-process runtime (SDD-058)")
    sub = ap.add_subparsers(dest="cmd")
    sp = sub.add_parser("start")
    sp.add_argument("--dataset", default="agents")
    sp.add_argument("--actor", default="operator")
    sp.add_argument("--confirm", action="store_true")
    sp.add_argument("task", nargs=argparse.REMAINDER,
                   help="the task command (after --): sessions start -- <cmd> [args...]")
    st = sub.add_parser("stop")
    st.add_argument("id")
    st.add_argument("--actor", default="operator")
    st.add_argument("--confirm", action="store_true")
    sub.add_parser("list")
    rp = sub.add_parser("reap")
    rp.add_argument("--actor", default="operator")
    args = ap.parse_args(argv)
    if args.cmd == "start":
        task = list(args.task)
        if task and task[0] == "--":
            task = task[1:]
        r = start(task, dataset_key=args.dataset, actor=args.actor, confirm=args.confirm)
    elif args.cmd == "stop":
        r = stop(args.id, actor=args.actor, confirm=args.confirm)
    elif args.cmd == "list":
        r = {"ok": True, "code": 200, "sessions": session_list()}
    elif args.cmd == "reap":
        r = reap(actor=args.actor)
    else:
        ap.error("a subverb is required: start|stop|list|reap")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
