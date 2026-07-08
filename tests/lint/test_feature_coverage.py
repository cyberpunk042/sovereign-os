"""SDD-045 §7 — the completeness gate: every feature reaches a dashboard.

The operator asked "WHERE IS EVERYTHING… 1000+ features". This gate is the
mechanical proof: it enumerates every top-level `sovereign-osctl` verb family
from the dispatch, and fails if ANY verb is not accounted for in
config/feature-coverage.yaml — either mapped to a real dashboard (in
config/dashboard-catalog.yaml) or listed as an explicit, rationalised
CLI-only waiver. A NEW verb added without a coverage decision fails CI, so the
surface can never silently grow invisible.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
OSCTL = REPO / "scripts" / "sovereign-osctl"
COVERAGE = REPO / "config" / "feature-coverage.yaml"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"


def _dispatch_verbs() -> set[str]:
    """Every top-level verb family, extracted the robust way: the branch labels
    of the main `case "${cmd}" in` dispatch (depth-tracked so nested subcommand
    cases are excluded), unioned with the cmd_<name> handler functions."""
    lines = OSCTL.read_text(encoding="utf-8").splitlines()
    verbs: set[str] = set()
    # (a) cmd_<name> handlers → hyphenated CLI names
    for m in re.finditer(r"^cmd_([a-z0-9_]+)\(\)", "\n".join(lines), re.M):
        verbs.add(m.group(1).replace("_", "-"))
    # (b) main dispatch top-level branch labels
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == 'case "${cmd}" in')
    except StopIteration:  # pragma: no cover
        raise AssertionError('main dispatch `case "${cmd}" in` not found')
    depth = 0
    for l in lines[start:]:
        s = l.strip()
        if s.startswith("case ") and s.endswith(" in"):
            depth += 1
            continue
        if s == "esac":
            depth -= 1
            if depth == 0:
                break
            continue
        if depth == 1:
            m = re.match(r"^  ([a-z][a-z0-9|_-]*)\)", l)
            if m:
                for part in m.group(1).split("|"):
                    verbs.add(part)
    # exclude the wildcard/default + obvious non-verbs
    verbs.discard("*")
    return {v for v in verbs if v and not v.startswith("-")}


def _coverage() -> dict:
    return yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))


def _catalog_slugs() -> set[str]:
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    return {d["slug"] for d in cat["dashboards"]}


def _covered_verbs(cov: dict) -> set[str]:
    mapped = {v for verbs in cov.get("coverage", {}).values() for v in verbs}
    waived = {e["verb"] for e in cov.get("cli_only", [])}
    return mapped | waived


def test_coverage_ledger_present():
    assert COVERAGE.is_file(), f"missing {COVERAGE}"
    cov = _coverage()
    assert cov.get("coverage"), "ledger has no coverage map"


def test_every_verb_family_reaches_a_dashboard_or_is_waived():
    """THE gate: no verb is CLI-only-and-invisible. Every dispatch verb must be
    mapped to a dashboard or an explicit cli_only waiver."""
    dispatch = _dispatch_verbs()
    covered = _covered_verbs(_coverage())
    uncovered = sorted(dispatch - covered)
    assert not uncovered, (
        f"{len(uncovered)} verb families have NO dashboard home and NO cli_only "
        f"waiver — decide coverage for each in config/feature-coverage.yaml: "
        f"{uncovered}"
    )


def test_coverage_maps_to_real_dashboards():
    """Every dashboard a verb is mapped to must be a real catalog entry."""
    slugs = _catalog_slugs()
    bad = sorted(d for d in _coverage().get("coverage", {}) if d not in slugs)
    assert not bad, f"feature-coverage maps to non-existent dashboards: {bad}"


def test_cli_only_waivers_have_rationale():
    for e in _coverage().get("cli_only", []):
        assert e.get("verb") and (e.get("rationale") or "").strip(), (
            f"cli_only waiver needs verb + rationale: {e}"
        )


def test_coverage_endpoint_and_front_door():
    """The completeness proof is surfaced LIVE: build-configurator-api serves
    /feature-coverage, and the master-dashboard renders the coverage capstone
    (the visible 'nothing is invisible' answer)."""
    api = (REPO / "scripts" / "operator" / "build-configurator-api.py").read_text(encoding="utf-8")
    assert "/feature-coverage" in api and "_load_feature_coverage" in api, (
        "build-configurator-api must serve /feature-coverage"
    )
    md = (REPO / "webapp" / "master-dashboard" / "index.html").read_text(encoding="utf-8")
    assert "renderCoverage" in md and 'fetchJSON("/feature-coverage")' in md, (
        "master-dashboard must render the live coverage capstone"
    )


def test_no_stale_coverage_entries():
    """Every verb listed in the ledger must still exist in the dispatch (catches
    a mapping left behind after a verb was renamed/removed)."""
    dispatch = _dispatch_verbs()
    covered = _covered_verbs(_coverage())
    stale = sorted(covered - dispatch)
    assert not stale, (
        f"feature-coverage lists verbs no longer in sovereign-osctl (remove "
        f"or rename): {stale}"
    )
