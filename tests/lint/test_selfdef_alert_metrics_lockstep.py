"""Cross-repo alert-expression ↔ selfdef-emitter lockstep.

A Prometheus alert whose `expr` references a `selfdef_*` series that
selfdef never emits is a **dead alert** — it can never fire, so there is
no page during the real incident it was meant to catch. That is strictly
worse than a broken runbook link (which at least fires a useless page):
a dead alert is silent.

This is the alert-expression sibling of
`test_selfdef_dashboard_metrics_lockstep` and
`test_action_surface_alert_runbook_coverage`, completing the triad of
"every selfdef_* reference in a sovereign-os consumer artifact (runbook
anchor / dashboard panel / alert expr) must resolve to something selfdef
actually produces."

Opt-in via `$SELFDEF_REPO_ROOT` (sovereign-os CI runs without the partner
repo cloned); the in-repo structural checks always run.

Run: ``SELFDEF_REPO_ROOT=/path/to/selfdef pytest -xq \
        tests/lint/test_selfdef_alert_metrics_lockstep.py``
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_DIR = REPO_ROOT / "config" / "prometheus" / "alerts"
SELFDEF_METRIC_RE = re.compile(r"\bselfdef_[a-z][a-z0-9_]*\b")
_SOURCE_SUFFIXES = {".rs", ".sh", ".toml", ".md", ".yml", ".yaml"}


def _alert_exprs() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for f in sorted(ALERTS_DIR.glob("*.rules.yml")):
        doc = yaml.safe_load(f.read_text())
        for g in doc.get("groups", []):
            for r in g.get("rules", []):
                if "alert" in r:
                    out.append((f.name, r["alert"], r.get("expr", "")))
    return out


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


def test_alert_files_present():
    assert list(ALERTS_DIR.glob("*.rules.yml")), "no alert rule files found"


def test_selfdef_referencing_alerts_have_extractable_metrics():
    """In-repo sanity (always runs): some alert exprs reference selfdef_*
    series, so the cross-repo gate below can't pass vacuously."""
    refs = [a for _, a, e in _alert_exprs() if SELFDEF_METRIC_RE.search(e)]
    assert refs, "expected some alert exprs to reference selfdef_* series"


def test_no_dead_selfdef_alerts():
    """Cross-repo (opt-in): every selfdef_* series an alert expr depends
    on must be emitted somewhere in the selfdef source tree. An orphan =
    a dead alert that can never fire."""
    env = os.environ.get("SELFDEF_REPO_ROOT")
    if not env:
        return  # opt-in only
    selfdef_root = Path(env)
    if not (selfdef_root / "crates").is_dir():
        return  # bad path → skip rather than false-positive

    emitted = _selfdef_emitted_tokens(selfdef_root)
    assert emitted, f"no selfdef_* tokens found under {selfdef_root} — bad checkout?"

    dead: list[str] = []
    for fn, alert, expr in _alert_exprs():
        for metric in SELFDEF_METRIC_RE.findall(expr):
            if metric not in emitted:
                dead.append(f"{fn}:{alert} -> {metric}")
    assert not dead, (
        "DEAD ALERTS — expr references a selfdef_* series with no emitter in "
        "the selfdef source tree (alert can never fire):\n" + "\n".join(dead)
    )
