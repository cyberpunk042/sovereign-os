"""Quoted `"scripts/<path>.py"` literal ⇄ file existence (cross-script P4).

Composition/probe/registry scripts reference *other* scripts by quoted
literal path — `state-snapshot.py`'s DEFAULT_PROBES catalog, `quarterly-
review.py`'s script_map, `wattage-heat-trend-watcher.py`'s heat probe,
`cot-registry.py`'s step lists. When a script is renamed or reorganized,
these literals dangle: the composer's subprocess silently fails (the probe
returns None / the step skips / the verb errors mid-task) and the operator
loses a surface they think is wired.

The per-file gates (test_cot_registry_script_refs) caught dangling refs in
ONE composer at a time. This is the catch-all: ANY quoted `"scripts/*.py"`
literal anywhere under scripts/ must resolve to a real file. It caught
three dangling refs left behind by hardware/power reorganization:
  - wattage-heat-trend-watcher → heat-integration.py (never existed)
  - state-snapshot gpu-wattage → gpu-wattage.py (renamed -catalog)
  - state-snapshot battery-ladder → hardware/battery-ladder.py
    (moved to power/battery-escalation-ladder.py)

A bare prose mention like `"scripts/foo.py present"` (text after `.py`
before the close-quote) is NOT matched — only a clean quoted path literal.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"

# A clean quoted path literal: opening quote, scripts/<path>.py, close quote.
_QUOTED_SCRIPT = re.compile(r'"(scripts/[a-z0-9/_-]+\.py)"')


def _referenced() -> dict[str, list[str]]:
    """Map each referenced literal path → the files that reference it."""
    refs: dict[str, list[str]] = {}
    for py in SCRIPTS.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="replace")
        for m in set(_QUOTED_SCRIPT.findall(text)):
            # A file referencing its own path (module docstring header) is
            # trivially valid; keep it — it still must exist.
            refs.setdefault(m, []).append(
                str(py.relative_to(REPO_ROOT)))
    return refs


def test_some_script_path_literals_are_referenced():
    refs = _referenced()
    assert len(refs) >= 30, (
        f"only parsed {len(refs)} quoted scripts/*.py literals — the "
        f"parser may be broken or the script tree shrank unexpectedly"
    )


def test_every_quoted_script_path_literal_resolves():
    refs = _referenced()
    dangling = {
        path: sorted(set(sources))
        for path, sources in refs.items()
        if not (REPO_ROOT / path).is_file()
    }
    assert not dangling, (
        "quoted `\"scripts/*.py\"` literal(s) reference files that do not "
        "exist — a composer/probe/registry points at a renamed/deleted "
        "script and will silently fail at invocation:\n"
        + "\n".join(
            f"  {path}  ←  {', '.join(srcs)}"
            for path, srcs in sorted(dangling.items())
        )
        + "\nUpdate the path (script moved/renamed) or remove the reference."
    )
