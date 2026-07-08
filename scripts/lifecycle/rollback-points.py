#!/usr/bin/env python3
"""scripts/lifecycle/rollback-points.py — ZFS-snapshot + commit-history
rollback-points core (M060 D-08 / R10097-R10101).

The data model behind the D-08 rollback-points cockpit dashboard. Joins three
real sources — never fabricates a rollback target:

  - ZFS snapshots (M068)   `zfs list -t snapshot` — per-dataset snapshot
                           inventory (name / dataset / creation / used / refer),
                           kind classified from the snap-name prefix
                           (pre-commit / daily / manual / auto).
  - commit history (MS041) `git log` over the repo — durable changes in the
                           last 24h, the MS041 receipt analogue.
  - rollback log           OPTIONAL /var/log/sovereign-os/rollbacks.jsonl — past
                           rollback-apply events (for "last rollback").

Plus a READ-ONLY rollback PREVIEW (R10099 dry-run): given a target snapshot it
computes the `zfs rollback` plan + the git commits that sit between HEAD and the
snapshot's creation time (the changes a rollback WOULD revert) + a side-effect
shortstat. It NEVER mutates — rollback-apply (R10100) stays an MS003-signed CLI
verb (MS043 R10212).

Sovereignty: stdlib-only. Every probe degrades gracefully — absent zfs → empty
snapshot inventory; absent git → empty history; the dashboard still renders.
This is the `core` surface of the §1g 8-surface ladder for the rollback module;
`scripts/operator/rollback-api.py` serves it, `sovereign-osctl rollback` drives
it, the D-08 webapp renders it.

  rollback-points.py snapshot [--json]          full dashboard model
  rollback-points.py preview  --to <snap> [--json]   dry-run rollback plan
  rollback-points.py commits  [--json]          MS041 commit history only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
ROLLBACK_LOG = Path(os.environ.get(
    "SOVEREIGN_OS_ROLLBACK_LOG", "/var/log/sovereign-os/rollbacks.jsonl",
))
# git repo the commit history is read from (defaults to this checkout).
GIT_REPO = Path(os.environ.get("SOVEREIGN_OS_GIT_REPO", str(_REPO_ROOT)))

# SDD-050 snapshot write actuation.
# Dataset ENUM — the cockpit control passes a short key (`_SAFE_VALUE`-clean, no
# '/'); the '/'-bearing real dataset path is resolved HERE, never through the
# exec-daemon's arg allowlist (which forbids '/'). Same pattern as SDD-049's
# model id→path resolution. (Q-050-A — operator may extend.)
_DATASETS = {
    "os": "rpool/sovereign-os",
    "context": "tank/context",
    "models": "tank/models",
    "agents": "tank/agents",
}
# Snapshot tag: stricter than the exec rail's _SAFE_VALUE (which permits '@'/':'/
# '=') — a tag must never carry the '@' dataset separator or a path '/'.
_SAFE_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RECENT_RE = re.compile(r"^recent-(\d+)$")
# Prune floor: never destroy the newest N snapshots per dataset (nor the very
# latest, absolutely) without --force. (Q-050-B — operator may tune.)
_PRUNE_FLOOR = 3


def _run(cmd: list[str], timeout: float = 5.0, cwd: str | None = None) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def _fmt_age(epoch: float) -> str:
    secs = max(0, time.time() - epoch)
    d = int(secs // 86400)
    h = int((secs % 86400) // 3600)
    if d:
        return f"{d}d {h}h"
    m = int((secs % 3600) // 60)
    return f"{h}h {m}m" if h else f"{m}m"


def _snapshot_kind(snap: str) -> str:
    s = snap.lower()
    if s.startswith("pre-") or "pre-commit" in s:
        return "pre-commit"
    if s.startswith("manual") or "manual" in s:
        return "manual"
    if s.startswith("daily") or "daily" in s:
        return "daily"
    return "auto"


def _human_bytes(n: float | None) -> str:
    if n is None:
        return "—"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if n >= 10 or i == 0 else f"{n:.1f} {units[i]}"


def collect_snapshots() -> list[dict[str, Any]]:
    """ZFS snapshot inventory via `zfs list -t snapshot`. Absent zfs → []."""
    out = _run(["zfs", "list", "-t", "snapshot", "-H", "-p",
                "-o", "name,used,referenced,creation"])
    if out is None:
        return []
    snaps = []
    for line in out.strip().splitlines():
        cols = line.split("\t")
        if len(cols) < 4:
            continue
        name = cols[0]
        dataset, _, snapname = name.partition("@")

        def _num(v: str) -> float | None:
            try:
                return float(v)
            except ValueError:
                return None

        used = _num(cols[1])
        refer = _num(cols[2])
        creation = _num(cols[3])
        snaps.append({
            "id": name,
            "dataset": dataset,
            "snapname": snapname,
            "taken": datetime.fromtimestamp(creation, tz=timezone.utc).isoformat()
            if creation is not None else None,
            "_creation": creation,
            "kind": _snapshot_kind(snapname),
            "used": _human_bytes(used),
            "refer": _human_bytes(refer),
            "tag": snapname,
        })
    snaps.sort(key=lambda s: s.get("_creation") or 0, reverse=True)
    return snaps


def _git_log(since: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Recent commits as {hash, ts (epoch), iso, subject}. Absent git → []."""
    args = ["git", "-C", str(GIT_REPO), "log", f"-{limit}",
            "--pretty=format:%H%x09%ct%x09%s"]
    if since:
        args.insert(4, f"--since={since}")
    out = _run(args)
    if out is None:
        return []
    commits = []
    for line in out.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        try:
            ts = float(parts[1])
        except ValueError:
            continue
        commits.append({
            "hash": parts[0][:7],
            "full_hash": parts[0],
            "ts": ts,
            "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "subject": parts[2],
        })
    return commits


def _last_rollback() -> str:
    if not ROLLBACK_LOG.is_file():
        return "never"
    try:
        lines = [ln for ln in ROLLBACK_LOG.read_text().splitlines() if ln.strip()]
    except OSError:
        return "never"
    if not lines:
        return "never"
    try:
        rec = json.loads(lines[-1])
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            return f"{_fmt_age(float(ts))} ago"
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return f"{_fmt_age(dt.timestamp())} ago"
    except (json.JSONDecodeError, ValueError):
        pass
    return "unknown"


def snapshot() -> dict[str, Any]:
    """The full D-08 dashboard model (snapshots + commit/snapshot timeline)."""
    snaps = collect_snapshots()
    commits = _git_log(since="24 hours ago", limit=50)

    # disk used by snapshots (re-parse the raw numeric for the GiB stat)
    disk_bytes = 0.0
    raw = _run(["zfs", "list", "-t", "snapshot", "-H", "-p", "-o", "used"])
    if raw:
        for line in raw.strip().splitlines():
            try:
                disk_bytes += float(line.strip())
            except ValueError:
                pass

    oldest_age = "—"
    if snaps:
        oldest = min((s["_creation"] for s in snaps if s.get("_creation")), default=None)
        if oldest is not None:
            oldest_age = _fmt_age(oldest)

    # timeline: interleave snapshots + commits, newest first (HH:MM labels)
    events = []
    for s in snaps:
        if s.get("_creation"):
            events.append({"_t": s["_creation"], "type": "snapshot",
                           "text": f"{s['id']} — {s['kind']} snapshot"})
    for c in commits:
        events.append({"_t": c["ts"], "type": "commit",
                       "text": f"{c['hash']} — {c['subject']}"})
    events.sort(key=lambda e: e["_t"], reverse=True)
    timeline = [{
        "ts": datetime.fromtimestamp(e["_t"], tz=timezone.utc).strftime("%H:%M"),
        "type": e["type"], "text": e["text"],
    } for e in events[:40]]

    # strip private sort keys from the public snapshot rows
    pub_snaps = [{k: v for k, v in s.items() if not k.startswith("_")} for s in snaps]

    return {
        "schema_version": SCHEMA_VERSION,
        "snapshotTotal": len(snaps),
        "commits24h": len(commits),
        "diskGib": round(disk_bytes / (1024 ** 3), 1),
        "oldestAge": oldest_age,
        "lastRollback": _last_rollback(),
        "snapshots": pub_snaps,
        "timeline": timeline,
    }


def preview(to: str) -> dict[str, Any]:
    """READ-ONLY dry-run rollback plan (R10099): the zfs rollback command + the
    git commits between HEAD and the snapshot's creation (would-be-reverted) +
    a side-effect shortstat. NEVER mutates."""
    snaps = {s["id"]: s for s in collect_snapshots()}
    target = snaps.get(to)
    dataset = to.partition("@")[0]
    lines: list[dict[str, str]] = [
        {"c": "diff-ctx", "t": f"== rollback-preview --to {to} (DRY-RUN, no mutations applied) =="},
        {"c": "diff-ctx", "t": ""},
        {"c": "diff-ctx", "t": "ZFS receive plan:"},
        {"c": "diff-del", "t": f"  - revert dataset state to {dataset}"},
        {"c": "diff-add", "t": f"  + zfs rollback -r {to}"},
        {"c": "diff-ctx", "t": ""},
    ]
    reverted: list[dict[str, Any]] = []
    if target and target.get("_creation"):
        since_iso = datetime.fromtimestamp(target["_creation"], tz=timezone.utc).isoformat()
        reverted = _git_log(since=since_iso, limit=100)
        lines.append({"c": "diff-ctx", "t": "MS041 commits between HEAD and snapshot (would be reverted):"})
        if reverted:
            for c in reverted:
                lines.append({"c": "diff-del", "t": f"  {c['hash']} {c['subject']}"})
            # side-effect shortstat oldest-reverted^..HEAD
            oldest_hash = reverted[-1]["full_hash"]
            stat = _run(["git", "-C", str(GIT_REPO), "diff", "--shortstat",
                         f"{oldest_hash}^..HEAD"])
            lines.append({"c": "diff-ctx", "t": ""})
            lines.append({"c": "diff-ctx", "t": "Side effects (committed, reverted on apply):"})
            lines.append({"c": "diff-del", "t": f"  {stat.strip() if stat else '(shortstat unavailable)'}"})
        else:
            lines.append({"c": "diff-ctx", "t": "  (no commits after this snapshot — nothing to revert)"})
    else:
        lines.append({"c": "diff-ctx", "t": "snapshot not found in live `zfs list` — plan shown without commit diff"})
        lines.append({"c": "diff-ctx", "t": "  (run on the workstation where the dataset is mounted)"})
    lines.append({"c": "diff-ctx", "t": ""})
    lines.append({"c": "diff-ctx", "t": "Apply requires: --confirm + MS003 operator signature"})
    return {
        "target": to,
        "found": target is not None,
        "reverted_commits": [{"hash": c["hash"], "subject": c["subject"]} for c in reverted],
        "apply_cmd": f"sovereign-osctl rollback apply --to {to} --confirm",
        "lines": lines,
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def apply(to: str, confirm: bool = False) -> dict[str, Any]:
    """R10100 — apply a ZFS rollback (DESTRUCTIVE: `zfs rollback -r <snap>`
    discards everything newer than the snapshot). DRY-RUN unless --confirm AND
    SOVEREIGN_OS_DRY_RUN is not set. `to=latest` resolves the most recent
    snapshot; any other value is resolved against the live `zfs list` inventory
    by full name OR tag — so the raw '/' snapshot path is expanded HERE, never
    passed through the exec-daemon's arg allowlist (which forbids '/'). The
    cockpit control offers `--to latest` (the common undo); arbitrary-snapshot
    rollback stays a manual CLI op."""
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    snaps = collect_snapshots()
    m = _RECENT_RE.match(to)
    if to == "latest":
        target = snaps[0]["id"] if snaps else None
    elif m:
        # SDD-050: `recent-N` is a stable positional token (the cockpit
        # `rollback-recent` control enum) — resolve to the Nth-newest live
        # snapshot HERE, so the '/'+'@' id never crosses the exec allowlist.
        n = int(m.group(1))
        target = snaps[n - 1]["id"] if 1 <= n <= len(snaps) else None
    else:
        target = next((s["id"] for s in snaps if to in (s["id"], s["tag"])), None)
    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"verb": "apply", "to": to, "resolved": target, "dry_run": True,
                "would_run": ["zfs", "rollback", "-r", target or f"<unresolved:{to}>"],
                "note": f"DRY-RUN ({why}) — DESTRUCTIVE; apply is --confirm + "
                        "MS003 operator-key + type-to-confirm gated"}
    if target is None:
        return {"verb": "apply", "to": to, "ok": False, "resolved": None,
                "error": f"no snapshot resolved for {to!r} "
                f"({'empty zfs inventory' if not snaps else 'unknown snapshot'})"}
    out = _run(["zfs", "rollback", "-r", target], timeout=120)
    return {"verb": "apply", "to": to, "resolved": target,
            "ok": out is not None, "ran": ["zfs", "rollback", "-r", target]}


def create(dataset_key: str, tag: str, confirm: bool = False) -> dict[str, Any]:
    """SDD-050 — create a ZFS snapshot `<dataset>@<tag>`. `dataset_key` is a
    short enum key (`_DATASETS`) resolved to the real '/'-bearing path HERE (never
    a '/'-arg through the exec allowlist); `tag` is validated `_SAFE_TAG`. DRY-RUN
    unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset. sovereign-os-owned ZFS
    storage op (R10212: not selfdef)."""
    dataset = _DATASETS.get(dataset_key)
    if dataset is None:
        return {"verb": "create", "ok": False, "dataset_key": dataset_key,
                "error": f"unknown dataset key {dataset_key!r} "
                         f"(known: {sorted(_DATASETS)})"}
    if not _SAFE_TAG.match(tag or ""):
        return {"verb": "create", "ok": False, "dataset": dataset, "tag": tag,
                "error": f"invalid tag {tag!r} — must match "
                         r"[A-Za-z0-9][A-Za-z0-9._-]* (no '/', '@', spaces)"}
    snap = f"{dataset}@{tag}"
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"verb": "create", "dataset": dataset, "tag": tag, "target": snap,
                "dry_run": True, "would_run": ["zfs", "snapshot", snap],
                "note": f"DRY-RUN ({why}) — creates a ZFS snapshot; "
                        "apply is --confirm + operator-key + type-to-confirm gated"}
    out = _run(["zfs", "snapshot", snap], timeout=60)
    return {"verb": "create", "dataset": dataset, "tag": tag, "target": snap,
            "ok": out is not None, "ran": ["zfs", "snapshot", snap]}


def prune(retain_days: int, confirm: bool = False, force: bool = False,
          floor: int = _PRUNE_FLOOR) -> dict[str, Any]:
    """SDD-050 — destroy ZFS snapshots older than `retain_days`, per dataset,
    EXCEPT a hard floor: never the very latest (absolute), and never the newest
    `floor` per dataset unless --force. Old-but-floor-protected snapshots are
    WITHHELD (reported, `refused=True`) rather than destroyed — refuse-by-default
    (Q-050-C). DESTRUCTIVE (`zfs destroy`); DRY-RUN unless --confirm AND
    SOVEREIGN_OS_DRY_RUN unset."""
    try:
        days = int(retain_days)
    except (TypeError, ValueError):
        return {"verb": "prune", "ok": False,
                "error": f"invalid --retain-days {retain_days!r} (must be an int)"}
    if days < 0:
        return {"verb": "prune", "ok": False,
                "error": "--retain-days must be >= 0"}
    cutoff = time.time() - days * 86400
    by_ds: dict[str, list[dict[str, Any]]] = {}
    for s in collect_snapshots():  # newest-first
        by_ds.setdefault(s["dataset"], []).append(s)
    to_destroy: list[str] = []
    withheld: list[str] = []
    for rows in by_ds.values():
        for idx, s in enumerate(rows):
            creation = s.get("_creation")
            if creation is None or creation >= cutoff:
                continue  # not older than retain window
            if idx == 0:
                continue  # never the very latest (absolute floor)
            if idx < floor and not force:
                withheld.append(s["id"])  # floor-protected — needs --force
                continue
            to_destroy.append(s["id"])
    refused = bool(withheld)  # (only populated when not force)
    result: dict[str, Any] = {
        "verb": "prune", "retain_days": days, "floor": floor, "force": force,
        "to_destroy": to_destroy, "withheld_by_floor": withheld, "refused": refused,
    }
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        result["dry_run"] = True
        result["would_run"] = [["zfs", "destroy", t] for t in to_destroy]
        note = (f"DRY-RUN ({why}) — would destroy {len(to_destroy)} snapshot(s)"
                " older than the retain window; DESTRUCTIVE on --confirm")
        if withheld:
            note += (f"; {len(withheld)} old snapshot(s) WITHHELD by the "
                     f"newest-{floor} floor (use --force to prune them)")
        result["note"] = note
        return result
    ran: list[str] = []
    failed: list[str] = []
    for t in to_destroy:
        out = _run(["zfs", "destroy", t], timeout=60)
        (ran if out is not None else failed).append(t)
    result["ran"] = ran
    result["failed"] = failed
    result["ok"] = not failed
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="rollback-points core (M060 D-08)")
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("snapshot")
    sp.add_argument("--json", action="store_true")
    pv = sub.add_parser("preview")
    pv.add_argument("--to", required=True)
    pv.add_argument("--json", action="store_true")
    cm = sub.add_parser("commits")
    cm.add_argument("--json", action="store_true")
    ap = sub.add_parser("apply")
    ap.add_argument("--to", required=True)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--json", action="store_true")
    cr = sub.add_parser("create")
    cr.add_argument("--dataset", required=True)
    cr.add_argument("--tag", required=True)
    cr.add_argument("--confirm", action="store_true")
    cr.add_argument("--json", action="store_true")
    pr = sub.add_parser("prune")
    pr.add_argument("--retain-days", type=int, required=True)
    pr.add_argument("--confirm", action="store_true")
    pr.add_argument("--force", action="store_true")
    pr.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "preview":
        _print(preview(args.to))
    elif cmd == "commits":
        _print(_git_log(since="24 hours ago", limit=50))
    elif cmd == "apply":
        _print(apply(args.to, confirm=args.confirm))
    elif cmd == "create":
        _print(create(args.dataset, args.tag, confirm=args.confirm))
    elif cmd == "prune":
        _print(prune(args.retain_days, confirm=args.confirm, force=args.force))
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
