"""backup-snapshot.sh ZFS snapshot-count math (observability accuracy).

scripts/hooks/recurrent/backup-snapshot.sh emits
`sovereign_os_snapshot_count` — the operator's "how many retained snapshots
do I have" gauge. The count is derived AFTER the new snapshot is created:
`zfs snapshot` runs, THEN `zfs list -t snapshot | grep @<prefix>-` collects
`all_snaps` (which therefore already includes the new one) into `total`,
and `pruned` of the oldest are destroyed. So the retained count is exactly
`total - pruned`.

A previous version computed `total + 1 - pruned`, double-counting the new
snapshot, so the gauge read one too high on every real ZFS run. The nspawn
test only exercised the non-ZFS `count=0` path, so it never surfaced. This
lint locks the corrected math so the off-by-one can't creep back.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "recurrent" / "backup-snapshot.sh"


def _body() -> str:
    return HOOK.read_text(encoding="utf-8")


def test_hook_exists():
    assert HOOK.is_file(), f"missing {HOOK}"


def test_snapshot_count_is_total_minus_pruned():
    body = _body()
    assert re.search(r"final_count=\$\(\(\s*total\s*-\s*pruned\s*\)\)", body), (
        "backup-snapshot.sh must compute final_count as `total - pruned` "
        "(total is post-creation, so it already counts the new snapshot)."
    )


def test_snapshot_count_does_not_double_count_new_snapshot():
    body = _body()
    assert not re.search(r"final_count=\$\(\(\s*total\s*\+\s*1", body), (
        "backup-snapshot.sh final_count adds 1 to `total` — but `total` is "
        "computed AFTER `zfs snapshot` (the new snapshot is already in the "
        "list), so +1 double-counts it and sovereign_os_snapshot_count reads "
        "one too high. Use `total - pruned`."
    )


def test_count_is_listed_after_creation():
    """Guard the precondition the math relies on: the snapshot list (which
    populates `total`) is collected AFTER `zfs snapshot` creates the new
    one. If a refactor moved the list BEFORE creation, `total - pruned`
    would under-count and this whole contract would flip."""
    body = _body()
    create = body.find("zfs snapshot ")
    listing = body.find("zfs list -H -o name -t snapshot")
    assert create != -1 and listing != -1, "expected both zfs snapshot + list"
    assert create < listing, (
        "the snapshot list must run AFTER `zfs snapshot` so `total` includes "
        "the new snapshot (the `total - pruned` count depends on it)."
    )
