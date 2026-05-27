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
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "preview":
        _print(preview(args.to))
    elif cmd == "commits":
        _print(_git_log(since="24 hours ago", limit=50))
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
