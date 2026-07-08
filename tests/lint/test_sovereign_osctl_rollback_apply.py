"""Contract: `sovereign-osctl rollback apply` is DRY-RUN by default and never
mutates without --confirm (R10100 — the destructive `zfs rollback -r`).

This is the CLI-side half of the rollback-apply double gate; the exec-daemon
half (operator-key + type-to-confirm + SOVEREIGN_OS_ACTION_EXEC_LIVE) is covered
by tests/unit/test_action_exec.py. Together they ensure the cockpit's one-click
"Rollback (latest)" can never silently discard host state.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "scripts" / "lifecycle" / "rollback-points.py"


def _apply(*args: str, dry_env: bool = False) -> dict:
    env = {"SOVEREIGN_OS_DRY_RUN": "1"} if dry_env else {}
    import os
    r = subprocess.run(
        [sys.executable, str(CORE), "apply", *args],
        capture_output=True, text=True, env={**os.environ, **env})
    return json.loads(r.stdout)


def test_apply_without_confirm_is_dry_run():
    """No --confirm → a dry-run plan, would_run shown, nothing executed."""
    d = _apply("--to", "latest")
    assert d["dry_run"] is True
    assert d["would_run"][:3] == ["zfs", "rollback", "-r"]
    assert "DESTRUCTIVE" in d["note"]
    assert "ran" not in d  # nothing was actually executed


def test_apply_confirm_forced_dry_by_env():
    """--confirm still yields dry-run when SOVEREIGN_OS_DRY_RUN=1 (belt + braces)."""
    d = _apply("--to", "latest", "--confirm", dry_env=True)
    assert d["dry_run"] is True
    assert "ran" not in d


def test_apply_confirm_without_zfs_does_not_claim_success():
    """--confirm with no resolvable snapshot (no zfs in CI) must NOT rollback —
    it reports an honest failure, never a silent no-op success."""
    d = _apply("--to", "latest", "--confirm")
    # CI has no zfs → empty inventory → cannot resolve `latest`
    assert d.get("dry_run") is not True
    assert d["ok"] is False
    assert "no snapshot resolved" in d["error"]


def test_change_cli_matches_control_registry():
    """The registered control's change_cli must be the exact --to latest --confirm
    form this contract guards (so the cockpit path and this test agree)."""
    import yaml
    reg = yaml.safe_load((REPO / "config" / "control-systems.yaml").read_text())
    ctl = next(s for s in reg["systems"] if s["id"] == "rollback-apply")
    assert ctl["change_cli"] == "sovereign-osctl rollback apply --to latest --confirm"
    assert ctl["privileged"] is True
