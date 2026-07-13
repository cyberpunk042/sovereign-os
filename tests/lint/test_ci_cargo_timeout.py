"""CI cargo-workspace timeout floor (F-2026-050 / SDD-970).

The `cargo-workspace` job in .github/workflows/test.yml runs fmt + clippy + test +
`cargo build --release --workspace` over the whole workspace (717+ crates) in a single
job. Warm Swatinem/rust-cache runs finish in ~6-7 min, but a cold-cache run (toolchain
bump, lockfile change, cache eviction) rebuilds everything and needs far more — the
original `timeout-minutes: 10` would fail the PR spuriously.

SDD-970 raised the budget to 30 min. This lint keeps a floor so the timeout can't be
quietly lowered back into the danger zone as the workspace keeps growing.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"

JOB = "cargo-workspace"
FLOOR_MINUTES = 20


def _jobs() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{WORKFLOW} did not parse to a mapping"
    jobs = data.get("jobs")
    assert isinstance(jobs, dict), f"{WORKFLOW} has no jobs mapping"
    return jobs


def test_cargo_workspace_job_exists():
    assert JOB in _jobs(), f"{WORKFLOW} has no `{JOB}` job"


def test_cargo_workspace_timeout_has_headroom():
    job = _jobs()[JOB]
    timeout = job.get("timeout-minutes")
    assert timeout is not None, (
        f"the `{JOB}` job has no timeout-minutes — an unbounded (6h default) job hides "
        "runaway builds; set an explicit budget with headroom"
    )
    assert isinstance(timeout, int) and timeout >= FLOOR_MINUTES, (
        f"the `{JOB}` job's timeout-minutes ({timeout}) is below the {FLOOR_MINUTES}-min "
        "floor — a cold-cache release build of the 717+ crate workspace needs headroom "
        "(F-2026-050); do not lower it back toward 10"
    )
