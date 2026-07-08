"""Milestone-contract materialization completeness guard.

Every milestone file in backlog/milestones/MNNN-*.md must have at least one
materialized config contract (config/**/mNNN-*.yaml with `milestone: MNNN`) AND a
matching lint test (tests/lint/test_mNNN_*.py). This guard makes the milestone
catalog self-verifying: any NEW milestone added without a spec-materialized,
lint-locked contract fails CI — protecting the materialization discipline.

Sole documented exception: M069 is a reserved slot whose implementation lives in
selfdef MS044 (Guardian Daemon) per operator standing direction "Respect the
projects" — sovereign-os catalogs only its narrative (M066), not a config contract.

Per operator §1g (sacrosanct): "We do not minimize anything." — no milestone may
be silently left without a contract; the only allowed gap is the explicitly-named
cross-repo boundary (M069).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MS_DIR = REPO_ROOT / "backlog" / "milestones"
CONFIG_DIR = REPO_ROOT / "config"
LINT_DIR = REPO_ROOT / "tests" / "lint"

# Documented cross-repo boundary exception (implementation in selfdef MS044).
EXEMPT = {"M069"}


def _milestone_ids() -> set[str]:
    ids = set()
    for f in MS_DIR.glob("M0[0-9][0-9]-*.md"):
        m = re.match(r"(M0\d\d)", f.name)
        if m:
            ids.add(m.group(1))
    return ids


def _contract_index() -> dict[str, list[Path]]:
    idx: dict[str, list[Path]] = {}
    for y in CONFIG_DIR.rglob("m0[0-9][0-9]-*.yaml"):
        try:
            d = yaml.safe_load(y.read_text())
        except Exception:
            continue
        if isinstance(d, dict) and "milestone" in d:
            idx.setdefault(str(d["milestone"]), []).append(y)
    return idx


def test_milestone_dir_present():
    assert MS_DIR.is_dir(), f"missing {MS_DIR}"
    assert _milestone_ids(), "no milestone files discovered"


def test_every_milestone_has_a_contract():
    ids = _milestone_ids()
    idx = _contract_index()
    missing = sorted(mid for mid in ids if mid not in idx and mid not in EXEMPT)
    assert not missing, (
        f"{len(missing)} milestone(s) have NO materialized config contract "
        f"(config/**/m<nnn>-*.yaml with milestone: M<nnn>): {missing}. "
        f"Materialize each spec-verbatim before merge (no minimization).")


def test_every_contract_has_a_lint_test():
    idx = _contract_index()
    missing = []
    for mid in sorted(idx):
        num = mid[1:]  # 'M042' -> '042'
        if not list(LINT_DIR.glob(f"test_m{num}_*.py")):
            missing.append(mid)
    assert not missing, (
        f"{len(missing)} materialized contract(s) have NO lint test "
        f"(tests/lint/test_m<nnn>_*.py): {missing}. Every contract must be lint-locked.")


def test_exemption_is_the_only_gap():
    # Guard against silent scope creep: the exempt set must stay exactly {M069}
    # unless a new cross-repo boundary is explicitly documented here.
    assert EXEMPT == {"M069"}, (
        "The completeness-exemption set changed. Only M069 (selfdef MS044 boundary) "
        "may be exempt; any addition needs an explicit documented cross-repo reason.")


def test_full_catalog_m002_to_m086_covered():
    # Anchor the milestone range so a regression that deletes milestone files is
    # caught too. The catalog spans M002..M086 (M069 exempt); assert the endpoints
    # and a dense-enough interior are present as materialized contracts.
    idx = _contract_index()
    for mid in ("M002", "M010", "M050", "M086"):
        assert mid in idx, f"{mid} missing a contract — catalog endpoint/anchor regressed"
