"""Cockpit queue read-path ⇄ selfdef writer binding (cross-repo).

Each `scripts/cockpit/*queue*.py` reads a pending-decision snapshot that
the SELFDEF side writes to `/var/lib/selfdef/<primitive>/pending-*.json`.
If the cockpit reads a filename no selfdef backend ever writes, the
dashboard card renders the empty honest-offline fallback forever — an
operator-invisible queue (the §1g minimization). This is exactly the
thermal-`.prom` / mirror-filename class: consumer reads X, producer writes
Y (or nothing).

This gate (opt-in via $SELFDEF_REPO_ROOT, like the alert-runbook cross-repo
lints) asserts every cockpit queue read-path FILENAME is written by some
selfdef backend's non-test source. It is skipped when the selfdef checkout
isn't adjacent (sovereign-os CI without it), so it lights up only where
both repos are present.

KNOWN GAP (F-2026-084): blockset's production NftablesBackend.
pending_extensions() returns the trait default Vec::new() and nothing
serializes pending-extensions.json, so card_blockset_queue is dead in
production while all ~12 sibling primitives persist + work. Tracked as a
design-tier finding; listed here as an explicit exception so the gate
protects the 13 working channels (a NEW dead queue card fails) and
surfaces blockset until the MS5 production-path is completed (or the card
is gated off).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COCKPIT = REPO_ROOT / "scripts" / "cockpit"

# pending-*.json filenames in a cockpit queue script's default read path.
_PENDING_FILE = re.compile(r"(pending-[a-z]+\.json)")

# F-2026-084: known-dead channel pending MS5 production-path completion.
KNOWN_UNWRITTEN = {"pending-extensions.json"}


def _cockpit_read_filenames() -> dict[str, str]:
    """Map each cockpit queue script -> the pending-*.json it reads."""
    out: dict[str, str] = {}
    for p in sorted(COCKPIT.glob("*queue*.py")):
        if "__pycache__" in p.parts:
            continue
        m = _PENDING_FILE.search(p.read_text(encoding="utf-8"))
        if m:
            out[p.name] = m.group(1)
    return out


def _selfdef_root() -> Path | None:
    env = os.environ.get("SELFDEF_REPO_ROOT")
    if not env:
        return None
    root = Path(env)
    return root if (root / "crates").is_dir() else None


def _filename_written_by_selfdef(root: Path, filename: str) -> bool:
    """True if any non-test selfdef Rust source writes this filename."""
    for rs in (root / "crates").rglob("*.rs"):
        name = rs.name
        if name.endswith("_test.rs") or "/tests/" in str(rs):
            continue
        text = rs.read_text(encoding="utf-8", errors="replace")
        # crude but effective: the literal filename appears in a write/
        # join/serialize context somewhere in the backend source.
        if filename in text:
            return True
    return False


def test_cockpit_queue_scripts_have_read_paths():
    files = _cockpit_read_filenames()
    assert len(files) >= 5, (
        f"only parsed {len(files)} cockpit queue read-paths — glob/parse drift"
    )


def test_every_cockpit_queue_filename_is_written_by_selfdef():
    root = _selfdef_root()
    if root is None:
        return  # opt-in: selfdef checkout not adjacent
    files = _cockpit_read_filenames()
    dead: list[str] = []
    for script, filename in files.items():
        if filename in KNOWN_UNWRITTEN:
            continue
        if not _filename_written_by_selfdef(root, filename):
            dead.append(f"{script} -> {filename}")
    assert not dead, (
        "cockpit queue script(s) read a pending snapshot NO selfdef backend "
        "writes — the dashboard card is silently dead (operator-invisible "
        "queue):\n" + "\n".join(f"  - {d}" for d in dead)
        + "\nAdd FS persistence on the selfdef producer side (mirror the "
        "mount-binding/process-tree backend pattern) or fix the read path."
    )


def test_known_gap_blockset_is_actually_still_unwritten():
    """Defence: if blockset's pending-extensions.json STARTS being written
    (the MS5 fix lands), this test fails so the KNOWN_UNWRITTEN waiver +
    F-2026-084 get retired instead of silently masking a now-working
    channel. Opt-in via $SELFDEF_REPO_ROOT."""
    root = _selfdef_root()
    if root is None:
        return
    still_unwritten = {
        fn for fn in KNOWN_UNWRITTEN
        if not _filename_written_by_selfdef(root, fn)
    }
    assert still_unwritten == KNOWN_UNWRITTEN, (
        "a KNOWN_UNWRITTEN cockpit channel is now written by selfdef — "
        f"retire it from KNOWN_UNWRITTEN + close F-2026-084: "
        f"{KNOWN_UNWRITTEN - still_unwritten}"
    )
