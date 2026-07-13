"""Hook hygiene contract (F-2026-023 + F-2026-021 / SDD-967).

Post-install / pre-install / recurrent hooks under scripts/hooks/ are dispatched two
ways, both of which fail SILENTLY on a hygiene slip:

  * `scripts/build/orchestrate.sh` runs pre-install hooks via
    `find … -type f -executable` — a hook that loses its +x bit is skipped with no
    error (F-2026-023);
  * the DISPATCH WIRING (config/bootstrap/phases.yaml + the systemd units) references
    specific hooks by PATH — a hook that is deleted or renamed (e.g. the legacy
    vfio-bind-3090 duplicate removed in SDD-967) leaves a dangling wiring reference
    that only surfaces at install/boot time on real hardware.

This lint closes both:

  * test_all_hooks_executable — every scripts/hooks/**/*.sh has its executable bit, so
    the glob-dispatch never silently drops one;
  * test_no_dangling_hook_path_references — every `scripts/hooks/**/<name>.sh` PATH in
    the dispatch wiring (phases.yaml + systemd units) resolves to a file that exists, so
    a hook can't be deleted/renamed while its wiring survives.

Scope note: prose docs legitimately mention hook paths illustratively (tutorial
`my-hook.sh`), as planned/future work, or as historical references (this repo's own
findings ledger names the deleted hook) — so the dangling check covers the WIRING
surfaces (where a dangling path is a real install/boot bug), not documentation.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "scripts" / "hooks"

# The DISPATCH WIRING files — where a dangling hook path is a real install/boot bug.
_WIRING_FILES = [
    REPO_ROOT / "config" / "bootstrap" / "phases.yaml",
    *sorted((REPO_ROOT / "systemd" / "system").glob("*.service")),
    *sorted((REPO_ROOT / "systemd" / "system").glob("*.timer")),
]
_HOOK_PATH_RE = re.compile(r"scripts/hooks/[A-Za-z0-9_./-]+\.sh")


def _hooks() -> list[Path]:
    return sorted(HOOKS_DIR.rglob("*.sh"))


def test_hooks_exist():
    assert _hooks(), "no hooks found under scripts/hooks/"


def test_all_hooks_executable():
    """orchestrate.sh dispatches via `find -executable`; a non-+x hook is silently
    skipped (F-2026-023)."""
    import os

    non_exec = [
        str(h.relative_to(REPO_ROOT))
        for h in _hooks()
        if not os.access(h, os.X_OK)
    ]
    assert not non_exec, (
        "these hooks are not executable — orchestrate.sh's `find -executable` dispatch "
        f"would silently skip them: {non_exec}"
    )


def _referenced_hook_paths() -> dict[str, list[str]]:
    """Map each hook path referenced in the DISPATCH WIRING -> the files referencing it."""
    refs: dict[str, list[str]] = {}
    for f in _WIRING_FILES:
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in _HOOK_PATH_RE.findall(text):
            refs.setdefault(m, []).append(str(f.relative_to(REPO_ROOT)))
    return refs


def test_no_dangling_hook_path_references():
    """Every scripts/hooks/*.sh path in the dispatch wiring (phases.yaml + systemd units)
    must resolve to a real file — so deleting/renaming a hook (e.g. the SDD-967
    vfio-bind-3090 removal) can't leave a dangling wiring reference behind."""
    dangling: list[str] = []
    for path, referrers in sorted(_referenced_hook_paths().items()):
        if not (REPO_ROOT / path).is_file():
            dangling.append(f"{path} (referenced by: {', '.join(sorted(set(referrers)))})")
    assert not dangling, (
        "these hook paths are referenced but do not exist (delete/rename left a dangling "
        f"reference): {dangling}"
    )
