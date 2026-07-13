#!/usr/bin/env python3
"""scripts/lifecycle/save-state.py — M047 5-layer session save-state orchestrator
(SDD-057 / SDD-053 Stage 3).

A TRUE agent save-state is FIVE layers (E0451, per `crates/sovereign-save-state`):
ZFS snapshot + CRIU checkpoint + replay log + memory record + profile state.
"ZFS + CRIU alone is not a true save-state." This orchestrator composes the five
layers into a save-state manifest + a completeness gate, capturing the four layers
that are producible today and honestly flagging the CRIU checkpoint as missing
when there is no target process (there is no M057 session-process runtime yet, so
session entries carry no `pid` — the CRIU layer is captured only when a `pid` is
present, populated by the future runtime / a test fixture).

  save-state save-state <id> [--confirm]   capture a save-state for a session
  save-state restore    <id> [--confirm]   restore plan (criu restore + zfs rollback)

Layer capture sources (reuse existing engines — nothing invented):
  - zfs-snapshot   → rollback-points.create (SDD-050) on the session's dataset
  - criu-checkpoint→ `criu dump --tree <pid>` when the session carries a pid
  - replay-log     → an append to /var/log/sovereign-os/save-state.jsonl
  - memory-record  → snapshot + sha256 of /run/sovereign-os/memory.json (SDD-052)
  - profile-state  → the active profile (/etc/sovereign-os/active-profile.env)

Safety: DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset; the real host
mutations (zfs snapshot + criu dump) run only live + operator-key + type-to-confirm
gated at the exec daemon. The completeness gate honestly reports partial (4/5)
save-states until the M057 runtime lands. R10212: sovereign-os-owned; the session
read API stays read-only. MS003 signing deferred to selfdef.

stdlib-only. Exit: 0 ok/dry-run · 1 write error · 2 usage/unknown-id.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
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


# reuse the read core + the SDD-050 ZFS engine (hyphenated filenames → importlib).
_sr = _imp("_session_registry_for_savestate", _HERE / "session-registry.py")
_rp = _imp("_rollback_points_for_savestate", _HERE / "rollback-points.py")

SESSION_REGISTRY = _sr.SESSION_REGISTRY
SCHEMA_VERSION = "1.0.0"

# The FIVE save-state layers — MUST match crates/sovereign-save-state SaveLayer's
# serde kebab-case names (drift-guard: tests/lint/test_save_state_layers_match_crate.py).
_LAYERS = ("zfs-snapshot", "criu-checkpoint", "replay-log", "memory-record", "profile-state")

SAVE_ROOT = Path(os.environ.get(
    "SOVEREIGN_OS_SAVE_STATE_DIR", "/var/lib/sovereign-os/save-state"))
LEDGER = Path(os.environ.get(
    "SOVEREIGN_OS_SAVE_STATE_LEDGER", "/var/log/sovereign-os/save-state.jsonl"))
SPAN_STORE = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))
MEMORY_STATE = Path(os.environ.get(
    "SOVEREIGN_OS_MEMORY_STATE", "/run/sovereign-os/memory.json"))
ACTIVE_PROFILE_ENV = Path(os.environ.get(
    "SOVEREIGN_OS_ACTIVE_PROFILE_FILE", "/etc/sovereign-os/active-profile.env"))

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")
_UNSIGNED = "unsigned-pending-MS003"
_VERBS = ("save-state", "restore")
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


def _ts_compact() -> str:
    return re.sub(r"[^0-9]", "", _now())[:14]


def _tag_safe(s: str) -> str:
    """A ZFS tag must match rollback-points._SAFE_TAG ([A-Za-z0-9][A-Za-z0-9._-]*)."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", s)


def _run(cmd: list[str], timeout: float = 120.0) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".save-state-", suffix=".tmp")
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
    ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    span = _signed({
        "trace_id": f"save-state-{record['id']}-{ms:x}",
        "span_id": f"ss-{ms:x}",
        "parent_span_id": None,
        "operation": "session_save_state",
        "start_ts": record["ts"],
        "duration_ms": 0,
        "severity": "info",
        "attributes": {"session_id": record["id"], "verb": record["verb"],
                       "captured": record.get("captured"),
                       "is_true_save_state": record.get("is_true_save_state")},
        "ocsf_class": "5001",
        "actor": record.get("actor", "operator"),
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


def _resolve_session(session_id: str) -> dict[str, Any] | None:
    reg = _sr._read_registry(SESSION_REGISTRY)
    sessions = reg.get("sessions")
    if not isinstance(sessions, list):
        return None
    return next((s for s in sessions
                 if isinstance(s, dict) and str(s.get("id")) == session_id), None)


def _dataset_key(session: dict[str, Any]) -> str:
    dk = session.get("dataset", "agents")
    return dk if dk in _rp._DATASETS else "agents"


def _zfs_snapshot_path(dataset_path: str, tag: str, *, confirm: bool = False) -> dict[str, Any]:
    """SDD-065 — snapshot a per-session ZFS dataset (`tank/agents/<id>`) DIRECTLY by
    path (rollback-points.create only takes the fixed enum keys). Host-gated + DRY-RUN
    default, mirroring rollback-points.create's live/dry logic."""
    snap = f"{dataset_path}@{tag}"
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    if dry:
        return {"verb": "snapshot", "dataset_path": dataset_path, "tag": tag,
                "target": snap, "dry_run": True, "would_run": ["zfs", "snapshot", snap]}
    out = _rp._run(["zfs", "snapshot", snap], timeout=60)
    return {"verb": "snapshot", "dataset_path": dataset_path, "tag": tag, "target": snap,
            "ok": out is not None, "ran": ["zfs", "snapshot", snap]}


def _active_profile() -> str:
    env = os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE")
    if env:
        return env
    try:
        for line in ACTIVE_PROFILE_ENV.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?SOVEREIGN_OS_ACTIVE_PROFILE=(.+)", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    except OSError:
        pass
    return "private"


def capture(session_id: str, *, actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """Compose the 5-layer save-state for a session. DRY-RUN unless --confirm AND
    SOVEREIGN_OS_DRY_RUN unset. Returns the save-state record (captured/missing/
    is_true_save_state/layers)."""
    if not _SAFE_ID.fullmatch(session_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe session id {session_id!r} (must match _SAFE_VALUE, no '/')"}
    session = _resolve_session(session_id)
    if session is None:
        return {"ok": False, "code": 2, "id": session_id,
                "error": f"no session resolved for {session_id!r}"}
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    ts = _now()
    tsc = _ts_compact()
    layers: dict[str, Any] = {}
    captured: list[str] = []
    missing: list[str] = []

    with _WRITE_LOCK:
        # ── profile-state (always capturable) ───────────────────────────────
        layers["profile-state"] = {"profile": _active_profile(),
                                   "source": str(ACTIVE_PROFILE_ENV)}
        captured.append("profile-state")

        # ── memory-record (capturable when memory.json present) ─────────────
        if MEMORY_STATE.is_file():
            try:
                digest = hashlib.sha256(MEMORY_STATE.read_bytes()).hexdigest()
            except OSError:
                digest = None
            layers["memory-record"] = {"source": str(MEMORY_STATE), "sha256": digest}
            captured.append("memory-record")
        else:
            layers["memory-record"] = {"note": "no /run/sovereign-os/memory.json present"}
            missing.append("memory-record")

        # ── replay-log (always capturable — the durable save-state ledger) ──
        layers["replay-log"] = {"ledger": str(LEDGER),
                                "note": "save-state event appended to the durable ledger"}
        captured.append("replay-log")

        # ── zfs-snapshot ─────────────────────────────────────────────────────
        # SDD-065: prefer the session's per-session dataset (`dataset_path`,
        # tank/agents/<id>) when present → real per-session isolation; else the shared
        # enum dataset via rollback-points.create (fallback — the SDD-057 default).
        tag = _tag_safe(f"save-{session_id}-{tsc}")
        dpath = session.get("dataset_path")
        if dpath:
            zres = _zfs_snapshot_path(dpath, tag, confirm=confirm)
            layers["zfs-snapshot"] = {"dataset_path": dpath, "tag": tag, "result": zres}
        else:
            dk = _dataset_key(session)
            zres = _rp.create(dk, tag, confirm=confirm)
            layers["zfs-snapshot"] = {"dataset_key": dk, "tag": tag, "result": zres}
        if zres.get("ok") is False:
            missing.append("zfs-snapshot")
        else:
            captured.append("zfs-snapshot")

        # ── criu-checkpoint (the wrapper — only with a real target pid) ─────
        pid = session.get("pid")
        if isinstance(pid, int) and pid > 0:
            images_dir = str(SAVE_ROOT / session_id / tsc / "criu")
            cmd = ["criu", "dump", "--tree", str(pid), "--images-dir", images_dir,
                   "--shell-job", "--leave-running"]
            entry: dict[str, Any] = {"pid": pid, "images_dir": images_dir, "would_run": cmd}
            if not dry:
                Path(images_dir).mkdir(parents=True, exist_ok=True)
                out = _run(cmd)
                entry["ran"] = out is not None
                if out is None:
                    missing.append("criu-checkpoint")
                    entry["note"] = "criu dump failed or criu absent"
                else:
                    captured.append("criu-checkpoint")
            else:
                captured.append("criu-checkpoint")
            layers["criu-checkpoint"] = entry
        else:
            layers["criu-checkpoint"] = {
                "note": "no target pid — pending the M057 session-process runtime"}
            missing.append("criu-checkpoint")

        is_true = len(missing) == 0
        # sign the canonical save-state record; the manifest written below is the
        # durable signed artifact (the `manifest` pointer added afterward is a
        # storage locator, not part of the signed save-state content).
        record: dict[str, Any] = _signed({
            "schema_version": SCHEMA_VERSION, "verb": "save-state", "id": session_id,
            "ts": ts, "actor": actor, "captured": captured, "missing": missing,
            "is_true_save_state": is_true, "layers": layers, "signature": _UNSIGNED,
        })

        if dry:
            why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
            record["dry_run"] = True
            record["note"] = (f"DRY-RUN ({why}) — plan only; the real zfs snapshot + "
                              "criu dump run live + operator-key + type-to-confirm gated. "
                              + ("TRUE 5-layer save-state." if is_true
                                 else f"PARTIAL save-state — missing: {missing}"))
            return {"ok": True, "code": 200, **record}

        manifest = SAVE_ROOT / session_id / tsc / "manifest.json"
        try:
            _atomic_write(manifest, record)
        except OSError as e:
            return {"ok": False, "code": 1, "id": session_id, "error": f"manifest write failed: {e}"}
        record["manifest"] = str(manifest)
        _append_ledger(_signed({"ts": ts, "verb": "save-state", "id": session_id,
                                "captured": captured, "missing": missing,
                                "is_true_save_state": is_true, "manifest": str(manifest),
                                "signature": _UNSIGNED}))
        _emit_span(record)
        return {"ok": True, "code": 200, **record}


def _latest_manifest(session_id: str) -> Path | None:
    base = SAVE_ROOT / session_id
    if not base.is_dir():
        return None
    manifests = sorted(base.glob("*/manifest.json"))
    return manifests[-1] if manifests else None


def restore(session_id: str, *, actor: str = "operator", confirm: bool = False) -> dict[str, Any]:
    """Emit the inverse plan for the latest save-state: criu restore (if a
    checkpoint exists) + zfs rollback (rollback-points.apply) + memory/profile
    restore note. DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset."""
    if not _SAFE_ID.fullmatch(session_id or ""):
        return {"ok": False, "code": 2,
                "error": f"unsafe session id {session_id!r} (must match _SAFE_VALUE, no '/')"}
    man_path = _latest_manifest(session_id)
    if man_path is None:
        return {"ok": False, "code": 2, "id": session_id,
                "error": f"no save-state manifest found for {session_id!r} (capture one first)"}
    try:
        man = json.loads(man_path.read_text())
    except (OSError, json.JSONDecodeError, ValueError) as e:
        return {"ok": False, "code": 1, "id": session_id, "error": f"manifest unreadable: {e}"}
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    layers = man.get("layers", {})
    plan: dict[str, Any] = {}

    criu = layers.get("criu-checkpoint", {})
    if criu.get("images_dir"):
        plan["criu-checkpoint"] = {"would_run": ["criu", "restore", "--images-dir",
                                                  criu["images_dir"], "--shell-job"]}
    else:
        plan["criu-checkpoint"] = {"note": "no checkpoint in the save-state (no target pid at capture)"}

    zfs = layers.get("zfs-snapshot", {})
    if zfs.get("dataset_path") and zfs.get("tag"):  # SDD-065 per-session dataset
        target = f"{zfs['dataset_path']}@{zfs['tag']}"
        ares = _rp.apply(target, confirm=confirm)
        plan["zfs-snapshot"] = {"target": target, "result": ares}
    elif zfs.get("dataset_key") and zfs.get("tag"):
        target = f"{_rp._DATASETS.get(zfs['dataset_key'], zfs['dataset_key'])}@{zfs['tag']}"
        ares = _rp.apply(target, confirm=confirm)
        plan["zfs-snapshot"] = {"target": target, "result": ares}
    else:
        plan["zfs-snapshot"] = {"note": "no zfs snapshot in the save-state"}

    plan["memory-record"] = {"note": "memory restore is a Stage-4 follow-up (record is a reference)"}
    plan["profile-state"] = {"note": "profile restore is a Stage-4 follow-up"}

    record = _signed({"schema_version": SCHEMA_VERSION, "verb": "restore", "id": session_id,
                      "ts": _now(), "actor": actor, "from_manifest": str(man_path),
                      "plan": plan, "signature": _UNSIGNED})
    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        record["dry_run"] = True
        record["note"] = (f"DRY-RUN ({why}) — plan only; the real criu restore + zfs "
                          "rollback run live + operator-key + type-to-confirm gated")
        return {"ok": True, "code": 200, **record}
    _append_ledger(_signed({"ts": record["ts"], "verb": "restore", "id": session_id,
                            "from_manifest": str(man_path), "signature": _UNSIGNED}))
    _emit_span({**record, "captured": None, "is_true_save_state": None})
    return {"ok": True, "code": 200, **record}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M047 session save-state orchestrator (SDD-057)")
    sub = ap.add_subparsers(dest="cmd")
    for v in _VERBS:
        d = sub.add_parser(v)
        d.add_argument("id")
        d.add_argument("--actor", default="operator")
        d.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "save-state":
        r = capture(args.id, actor=args.actor, confirm=args.confirm)
    elif args.cmd == "restore":
        r = restore(args.id, actor=args.actor, confirm=args.confirm)
    else:
        ap.error("a subverb is required: save-state|restore")
        return 2
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
