"""Generic runbook-anchor coverage — EVERY Prometheus alert must link to
a real runbook section.

Per-family alert contract tests assert alert *structure* (required
alerts, label envelope) but historically did NOT check that each alert's
``runbook_url`` anchor actually resolves to a heading in the target doc.
That gap shipped 81 broken incident links: 64 across the SDD-070..078
action-surface families (no sections at all) + 17 more across
blockset/quarantine/revocations (missing sections) and
auth-events/disk-usage/kernel-modules/ms022 (typo'd anchors). An operator
paged mid-incident clicked the runbook link and landed on nothing.

This is the single generic gate over ALL alert rule files: every alert
whose ``runbook_url`` points into a doc in THIS repo must resolve to a
real heading (via GitHub's heading-slug rules). Cross-repo runbook links
(info-hub / selfdef) are out of scope here — they are checked by the
cross-repo reference lints.

Run: ``pytest -xq tests/lint/test_alert_runbook_anchor_coverage.py``
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ALERTS_DIR = REPO_ROOT / "config" / "prometheus" / "alerts"
REPO_BLOB_PREFIX = "github.com/cyberpunk042/sovereign-os/blob/main/"
SELFDEF_BLOB_PREFIX = "github.com/cyberpunk042/selfdef/blob/main/"

_doc_anchor_cache: dict[str, set[str] | None] = {}


def _github_anchor(heading: str) -> str:
    a = heading.strip().lower()
    a = re.sub(r"[^\w\s-]", "", a)
    a = re.sub(r"\s", "-", a)  # GitHub replaces each space; does NOT collapse
    return a


def _anchors_for(rel_path: str) -> set[str] | None:
    if rel_path not in _doc_anchor_cache:
        p = REPO_ROOT / rel_path
        _doc_anchor_cache[rel_path] = (
            {
                _github_anchor(m.group(1))
                for m in re.finditer(r"(?m)^#{1,6}\s+(.*)$", p.read_text())
            }
            if p.is_file()
            else None
        )
    return _doc_anchor_cache[rel_path]


def _all_alerts() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for f in sorted(ALERTS_DIR.glob("*.rules.yml")):
        doc = yaml.safe_load(f.read_text())
        for g in doc.get("groups", []):
            for r in g.get("rules", []):
                if "alert" in r:  # skip recording rules
                    out.append((f.name, r))
    return out


def test_alert_dir_present():
    assert ALERTS_DIR.is_dir(), f"missing {ALERTS_DIR}"
    assert list(ALERTS_DIR.glob("*.rules.yml")), "no alert rule files found"


def test_every_alert_has_a_runbook_url():
    missing = [
        f"{fn}:{r['alert']}"
        for fn, r in _all_alerts()
        if not r.get("annotations", {}).get("runbook_url")
    ]
    assert not missing, "alerts missing runbook_url:\n" + "\n".join(missing)


def test_every_in_repo_runbook_anchor_resolves():
    broken: list[str] = []
    checked = 0
    for fn, r in _all_alerts():
        url = r.get("annotations", {}).get("runbook_url", "")
        if REPO_BLOB_PREFIX not in url:
            continue  # cross-repo link — out of scope for this gate
        m = re.search(r"/blob/main/([^#]+)(?:#(.*))?$", url)
        assert m, f"{fn}:{r['alert']} has an unparseable in-repo runbook_url: {url}"
        rel_path, frag = m.group(1), m.group(2) or ""
        checked += 1
        anchors = _anchors_for(rel_path)
        if anchors is None:
            broken.append(f"{fn}:{r['alert']} -> MISSING DOC {rel_path}")
        elif frag and frag not in anchors:
            broken.append(f"{fn}:{r['alert']} -> #{frag} not in {Path(rel_path).name}")
    assert checked > 0, "no in-repo runbook links checked — prefix drift?"
    assert not broken, (
        f"{len(broken)}/{checked} in-repo alert runbook anchors do not resolve "
        f"(broken incident links):\n" + "\n".join(broken)
    )


def test_cross_repo_selfdef_runbook_anchors_resolve():
    """Cross-repo (opt-in via $SELFDEF_REPO_ROOT): alerts whose runbook_url
    points into a selfdef operator doc (e.g. the MS048 scheduler +
    m060-cockpit-mirror-producers runbooks) must resolve to a real heading
    there. A broken cross-repo anchor is a dead incident link just like an
    in-repo one — it's just owned by the partner repo. Skipped when the
    selfdef checkout isn't present (sovereign-os CI runs without it)."""
    env = os.environ.get("SELFDEF_REPO_ROOT")
    if not env:
        return  # opt-in only
    selfdef_root = Path(env)
    if not (selfdef_root / "docs").is_dir():
        return  # bad path → skip rather than false-positive

    cache: dict[str, set[str] | None] = {}

    def selfdef_anchors(rel_path: str) -> set[str] | None:
        if rel_path not in cache:
            p = selfdef_root / rel_path
            cache[rel_path] = (
                {
                    _github_anchor(m.group(1))
                    for m in re.finditer(r"(?m)^#{1,6}\s+(.*)$", p.read_text())
                }
                if p.is_file()
                else None
            )
        return cache[rel_path]

    broken: list[str] = []
    checked = 0
    for fn, r in _all_alerts():
        url = r.get("annotations", {}).get("runbook_url", "")
        if SELFDEF_BLOB_PREFIX not in url:
            continue
        m = re.search(r"/blob/main/([^#]+)(?:#(.*))?$", url)
        assert m, f"{fn}:{r['alert']} unparseable selfdef runbook_url: {url}"
        rel_path, frag = m.group(1), m.group(2) or ""
        checked += 1
        anchors = selfdef_anchors(rel_path)
        if anchors is None:
            broken.append(f"{fn}:{r['alert']} -> MISSING selfdef doc {rel_path}")
        elif frag and frag not in anchors:
            broken.append(f"{fn}:{r['alert']} -> #{frag} not in selfdef:{Path(rel_path).name}")
    assert checked > 0, "no cross-repo selfdef runbook links found — prefix drift?"
    assert not broken, (
        f"{len(broken)}/{checked} cross-repo selfdef runbook anchors do not "
        f"resolve (dead incident links):\n" + "\n".join(broken)
    )


def test_severity_vocabulary_is_bounded():
    """Defence-in-depth: keep the severity label vocabulary to the two
    operator-meaningful tiers so a typo'd severity can't slip a page into
    an unrouted bucket."""
    bad = [
        f"{fn}:{r['alert']}={r.get('labels', {}).get('severity')!r}"
        for fn, r in _all_alerts()
        if r.get("labels", {}).get("severity") not in ("warning", "critical")
    ]
    assert not bad, "alerts with out-of-vocab severity:\n" + "\n".join(bad)
