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

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "scripts" / "hooks" / "recurrent" / "backup-snapshot.sh"


def _body() -> str:
    return HOOK.read_text(encoding="utf-8")


def _run_dry(keep: str) -> str:
    """Run the hook in DRY-RUN with a given SOVEREIGN_OS_SNAPSHOT_KEEP and
    return combined stdout+stderr. DRY-RUN exits before any zfs/root path,
    so this exercises only the retention-value guard + the step header."""
    env = dict(os.environ)
    env["SOVEREIGN_OS_DRY_RUN"] = "1"
    env["SOVEREIGN_OS_SNAPSHOT_KEEP"] = keep
    r = subprocess.run(
        ["bash", str(HOOK)], capture_output=True, text=True, env=env, timeout=20
    )
    return r.stdout + r.stderr


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


def test_invalid_retention_clamps_to_default():
    """A NEGATIVE SOVEREIGN_OS_SNAPSHOT_KEEP would make `excess = total -
    KEEP` exceed total and destroy EVERY snapshot (incl. the just-created
    one) plus spurious empty destroys; a NON-NUMERIC value breaks the
    `[ total -gt KEEP ]` arithmetic test. Both must clamp to the default
    with a warning — the irreplaceable state-fabric (SDD-017) must never be
    destroyed on a typo'd retention value."""
    for bad in ("-5", "thirty", "-1", "3.5"):
        out = _run_dry(bad)
        assert "not a non-negative integer" in out, (bad, out)
        assert "keep latest 30" in out, (bad, out)


def test_valid_retention_passes_through():
    """A valid non-negative integer (incl. 0, the explicit 'retain none')
    is honored verbatim — the guard must not second-guess valid input."""
    out = _run_dry("20")
    assert "not a non-negative integer" not in out, out
    assert "keep latest 20" in out, out
    out0 = _run_dry("0")
    assert "not a non-negative integer" not in out0, out0
    assert "keep latest 0" in out0, out0


def test_retention_guard_precedes_destroy():
    """Static ordering guard: the retention validation must appear before
    the actual prune `zfs destroy` command, so an invalid value can never
    drive a destroy. Anchored on the guard's regex literal and the real
    destroy call (not bare phrases, which also occur in comments)."""
    body = _body()
    guard = body.find("^[0-9]+$")  # the validation regex, only in the guard
    destroy = body.find('zfs destroy "${all_snaps')  # the real prune call
    assert guard != -1, "retention-validation regex missing from backup-snapshot.sh"
    assert destroy != -1, "expected the prune `zfs destroy \"${all_snaps...}\"` call"
    assert guard < destroy, "retention guard must precede the prune `zfs destroy`"
