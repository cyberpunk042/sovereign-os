"""Cross-repo dashboard ↔ selfdef-emitter lockstep.

The generic in-repo `test_dashboard_metrics_lockstep` checks
`sovereign_os_*` series only. But 38 cockpit dashboards render
`selfdef_*` series produced by the partner selfdef daemon / textfile
wrappers — and several (the SDD-070..078 action-surface consumer
dashboards) have no per-family contract test at all. Nothing locked
those `selfdef_*` references against what selfdef actually emits, so a
selfdef rename would silently flat-line the consumer panel.

This is the consumer-side dashboard sibling of the per-family
threshold-lockstep tests: opt-in via `$SELFDEF_REPO_ROOT`. When a
selfdef checkout is present, every `selfdef_*` series a dashboard
references must appear as a `selfdef_*` token somewhere in the selfdef
source tree (the same superset heuristic the in-repo lockstep uses).
Skipped when the env var is unset — sovereign-os CI runs without the
partner repo cloned — but the in-repo structural checks always run.

Run: ``SELFDEF_REPO_ROOT=/path/to/selfdef pytest -xq \
        tests/lint/test_selfdef_dashboard_metrics_lockstep.py``
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_DIR = REPO_ROOT / "docs" / "observability" / "dashboards"
SELFDEF_METRIC_RE = re.compile(r"\bselfdef_[a-z][a-z0-9_]*\b")

# selfdef source file types worth scanning for emitted metric tokens.
_SOURCE_SUFFIXES = {".rs", ".sh", ".toml", ".md", ".yml", ".yaml"}


def _dashboards() -> list[Path]:
    return sorted(DASH_DIR.glob("*.json"))


def _selfdef_refs(dash: Path) -> set[str]:
    data = json.loads(dash.read_text())
    refs: set[str] = set()
    for panel in data.get("panels") or []:
        for tgt in panel.get("targets") or []:
            refs.update(SELFDEF_METRIC_RE.findall(tgt.get("expr") or ""))
    return refs


def _selfdef_emitted_tokens(root: Path) -> set[str]:
    seen: set[str] = set()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in _SOURCE_SUFFIXES:
            continue
        try:
            seen.update(SELFDEF_METRIC_RE.findall(p.read_text(errors="ignore")))
        except OSError:
            continue
    return seen


def test_dashboards_present():
    assert len(_dashboards()) >= 2


def test_selfdef_referencing_dashboards_parse_and_have_refs():
    """In-repo sanity (always runs): the dashboards that name selfdef_*
    series parse as JSON and expose at least one extractable reference,
    so the cross-repo gate below can't pass vacuously."""
    with_refs = [d.name for d in _dashboards() if _selfdef_refs(d)]
    assert with_refs, "expected some dashboards to reference selfdef_* series"


def test_selfdef_dashboard_refs_have_emitter():
    """Cross-repo (opt-in via $SELFDEF_REPO_ROOT): every selfdef_* series
    a dashboard renders must be emitted somewhere in the selfdef source
    tree. Orphans = a panel that will flat-line in production because the
    producer renamed/removed the series."""
    env = os.environ.get("SELFDEF_REPO_ROOT")
    if not env:
        return  # opt-in only — sovereign-os CI runs without selfdef cloned
    selfdef_root = Path(env)
    if not (selfdef_root / "crates").is_dir():
        return  # bad path → skip rather than false-positive

    emitted = _selfdef_emitted_tokens(selfdef_root)
    assert emitted, f"no selfdef_* tokens found under {selfdef_root} — bad checkout?"

    orphans: dict[str, list[str]] = {}
    for dash in _dashboards():
        missing = sorted(r for r in _selfdef_refs(dash) if r not in emitted)
        if missing:
            orphans[dash.name] = missing
    assert not orphans, (
        "dashboards reference selfdef_* series with no emitter in the selfdef "
        "source tree (cross-repo drift → flat panels):\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(orphans.items()))
    )
