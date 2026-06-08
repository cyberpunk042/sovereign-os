"""Cockpit queue read-path ⇄ selfdef writer-filename binding (cross-repo).

Each `scripts/cockpit/*queue*.py` reads a pending-decision snapshot named
`/var/lib/selfdef/<primitive>/pending-*.json`. The selfdef side's FS
backend (the MS1b production adapter for that primitive) is the component
that will write it — and its source already pins that exact filename
(e.g. mount-binding's `FsBackend` writes `pending-rebinds.json`). If a
cockpit script reads a filename that has NO counterpart anywhere in the
selfdef source tree, the read path is fabricated/renamed — a guaranteed
dead card once the producer lands. This is the consumer-reads-X /
producer-names-Y filename class (cf. thermal-`.prom`, mirror artifacts).

NOTE ON SCOPE (don't overclaim — see F-2026-087): this gate verifies the
filename has a selfdef-source *counterpart*, NOT that production currently
WRITES it. The enforcement layer is at MS1 (in-memory substrate, per the
in-memory-backend-as-ms1-substrate decision); the FS backends are defined
but unwired (`FsBackend::open` is test-only), so ALL these queues are
empty-by-design until MS1b. ~12 primitives already pin their pending-*.json
in an (unwired) FsBackend; blockset does not even have that scaffold.

Opt-in via $SELFDEF_REPO_ROOT (like the alert-runbook cross-repo lints);
skipped when the selfdef checkout isn't adjacent.

KNOWN GAP (F-2026-087): blockset's read-path `pending-extensions.json` has
no selfdef-source counterpart at all (no FsBackend scaffold), so MS1b must
author it to sibling parity. Listed as the explicit exception so the gate
protects the other channels' filename binding + the defence test fires
when blockset gains a writer.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COCKPIT = REPO_ROOT / "scripts" / "cockpit"

# pending-*.json filenames in a cockpit queue script's default read path.
_PENDING_FILE = re.compile(r"(pending-[a-z]+\.json)")

# F-2026-087: blockset read-path has no selfdef FsBackend scaffold (the
# filename pins nowhere in selfdef source); MS1b must author it to parity.
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
    F-2026-087 get retired instead of silently masking a now-working
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
        f"retire it from KNOWN_UNWRITTEN + close F-2026-087: "
        f"{KNOWN_UNWRITTEN - still_unwritten}"
    )
