"""sovereign-os reads of /var/lib/selfdef/*.json ⇄ selfdef writers (cross-repo).

Beyond the per-card cockpit queue snapshots (covered with card semantics in
test_cockpit_queue_selfdef_writer_binding), sovereign-os scripts read other
selfdef-produced state files from /var/lib/selfdef/ — notably
`hardware-capabilities.json` (consumed by ~11 scripts: onboard, selfdef-
models, posture, selfdef-tune, modules-gate, ...) and `flex-profile.json`.
If selfdef renames one of these, every sovereign-os consumer silently reads
a missing file (honest-offline empty) — a broad, invisible cross-repo
break.

This gate (opt-in via $SELFDEF_REPO_ROOT) is the general form: EVERY
`/var/lib/selfdef/<path>.json` literal read by any sovereign-os script must
be written by some non-test selfdef source. Skipped when the selfdef
checkout isn't adjacent.

KNOWN GAP (F-2026-087): blockset's `pending-extensions.json` is never
written in production (NftablesBackend.pending_extensions() returns the
trait default); tracked + waived here so the gate protects the rest and a
defence test fires when blockset starts being written.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"

_STATE_PATH = re.compile(r"/var/lib/selfdef/([a-z0-9/_-]+\.json)")

# F-2026-087: blockset pending snapshot never written in production.
KNOWN_UNWRITTEN_BASENAMES = {"pending-extensions.json"}


def _read_state_files() -> dict[str, list[str]]:
    """Map each /var/lib/selfdef/<path>.json read -> sovereign-os readers."""
    out: dict[str, list[str]] = {}
    for p in SCRIPTS.rglob("*"):
        if not p.is_file() or p.suffix not in (".py", ".sh"):
            continue
        if "__pycache__" in p.parts:
            continue
        for m in set(_STATE_PATH.findall(
                p.read_text(encoding="utf-8", errors="replace"))):
            out.setdefault(m, []).append(p.name)
    return out


def _selfdef_root() -> Path | None:
    env = os.environ.get("SELFDEF_REPO_ROOT")
    if not env:
        return None
    root = Path(env)
    return root if (root / "crates").is_dir() else None


def _written_by_selfdef(root: Path, basename: str) -> bool:
    for sub in ("crates", "modules", "scripts"):
        d = root / sub
        if not d.is_dir():
            continue
        for src in d.rglob("*"):
            if not src.is_file() or src.suffix not in (".rs", ".sh", ".py"):
                continue
            if "/tests/" in str(src) or src.name.endswith("_test.rs"):
                continue
            if basename in src.read_text(encoding="utf-8", errors="replace"):
                return True
    return False


def test_some_state_files_read():
    files = _read_state_files()
    assert len(files) >= 3, (
        f"only found {len(files)} /var/lib/selfdef/*.json reads — parse drift"
    )


def test_every_selfdef_state_file_read_is_written_by_selfdef():
    root = _selfdef_root()
    if root is None:
        return  # opt-in
    files = _read_state_files()
    dead: list[str] = []
    for relpath, readers in sorted(files.items()):
        basename = relpath.rsplit("/", 1)[-1]
        if basename in KNOWN_UNWRITTEN_BASENAMES:
            continue
        if not _written_by_selfdef(root, basename):
            dead.append(f"{relpath} (read by {sorted(set(readers))})")
    assert not dead, (
        "sovereign-os reads selfdef state file(s) NO selfdef source writes — "
        "every consumer silently reads a missing file (cross-repo break):\n"
        + "\n".join(f"  - {d}" for d in dead)
        + "\nFix the read path or add the selfdef-side writer."
    )
