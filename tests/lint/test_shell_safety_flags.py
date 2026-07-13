"""Shell-safety-flags contract for entry-point scripts (F-2026-024 / SDD-968).

An executable shell script that ships with NO safety flags (`set -e` / `set -u` /
`set -o pipefail`) fails silently: an unset variable expands to empty, a failed
command in the middle keeps going, a broken pipe is swallowed. This lint requires
every executable ENTRY-POINT script under scripts/ to opt into shell safety — either
by sourcing scripts/build/lib/common.sh (which sets `set -euo pipefail` for the whole
run) or by setting a safety flag itself.

Deliberately scoped:

  * It requires safety flags to be PRESENT, but does NOT mandate `-e` specifically —
    two entry points intentionally use `set -uo pipefail` without `-e`:
    `scripts/build/provision-bake.sh` (documented "NON-FATAL BY DESIGN": every step
    handles its own errors) and `scripts/webapp/preflight.sh` (a fail-counter:
    `fails=$((fails+1))` … `exit "$fails"`, which `-e` would abort before reporting).
    Forcing `-e` on those would introduce bugs, so the invariant is "has safety flags",
    not "has errexit".
  * Sourced LIBRARIES (scripts/**/lib/**) are exempt — they run under the caller's
    options; setting `-e` in a sourced lib imposes errexit on every caller as a side
    effect (common.sh does this deliberately, the sibling libs deliberately don't).
  * TEMPLATES (scripts/**/templates/**) are exempt — they are staged/rendered
    elsewhere (e.g. the operator-neutralized stop-hook template re-staged from the
    read-only image each session), not run in place.

So a NEW entry-point script that ships with zero safety flags is caught in CI, while
the existing deliberate designs are respected.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"

_SAFETY_RE = re.compile(r"(?m)^\s*set\s+-[a-z]*e|^\s*set\s+-[a-z]*u|set\s+-o\s+pipefail")
_COMMON_RE = re.compile(r"lib/common\.sh")


def _entry_point_scripts() -> list[Path]:
    """Executable *.sh under scripts/, excluding sourced libs and templates."""
    out: list[Path] = []
    for p in SCRIPTS.rglob("*.sh"):
        parts = set(p.parts)
        if "lib" in parts or "templates" in parts:
            continue
        if not os.access(p, os.X_OK):
            continue
        out.append(p)
    return sorted(out)


def _has_safety(p: Path) -> bool:
    text = p.read_text(encoding="utf-8", errors="replace")
    return bool(_COMMON_RE.search(text) or _SAFETY_RE.search(text))


def test_entry_points_exist():
    assert _entry_point_scripts(), "no executable entry-point scripts found under scripts/"


def test_entry_points_opt_into_shell_safety():
    """Every executable entry-point either sources common.sh or sets a shell-safety
    flag — so a script can't ship with zero fail-fast protection."""
    missing = [
        str(p.relative_to(REPO_ROOT))
        for p in _entry_point_scripts()
        if not _has_safety(p)
    ]
    assert not missing, (
        "these executable entry-point scripts set no shell-safety flags "
        "(set -e / -u / -o pipefail) and do not source scripts/build/lib/common.sh — "
        f"add `set -euo pipefail` (or `set -uo pipefail` if errexit is unwanted): {missing}"
    )
