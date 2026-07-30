"""A step is only "done" if its output is still there.

2026-07-30. The operator booted the image they had just flashed, came back, and
re-ran the build. Every early step reported

    step 01-bootstrap-forge already completed with matching inputs — skipping
    step 02-kernel-fetch    already completed with matching inputs — skipping
    step 04-kernel-compile  already completed with matching inputs — skipping

and then step 07 — the first thing that actually LOOKED — died with

    ‼ custom kernel .debs not found in /mnt/kernel_forge/kernel-debs

`/mnt/kernel_forge` is a 64 GB **tmpfs**. It is RAM. A reboot empties it, while
the recorded "completed" in state.yaml survives on disk. Worse, step 01 is the
step that MOUNTS that tmpfs, so skipping it guaranteed nothing would remount it
and the following steps could not have recovered even if they had tried.

Recorded status is a claim about the past. Whether the artifact exists NOW is
the question that matters — the same "exit status is not evidence of an
artifact" lesson this pipeline already learned at the flash step, where a build
that produced nothing reported success and the operator flashed a five-hour-old
ISO twice.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_LIB = REPO_ROOT / "scripts/build/lib/state.sh"

# The steps whose outputs live in the volatile tmpfs forge.
VOLATILE_STEPS = {
    "01-bootstrap-forge": "${SOVEREIGN_OS_FORGE_DIR}",
    "02-kernel-fetch": "${SOVEREIGN_OS_FORGE_DIR}/linux-stable",
    "04-kernel-compile": "${SOVEREIGN_OS_FORGE_DIR}/kernel-debs",
}


def _run(script: str, state: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", textwrap.dedent(script)],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "SOVEREIGN_OS_STATE_FILE": str(state)},
    )


@pytest.fixture
def state(tmp_path) -> Path:
    f = tmp_path / "state.yaml"
    f.write_text('steps:\n  99-probe:\n    status: completed\n    inputs_hash: "abc123"\n')
    return f


def test_a_present_artifact_still_skips(state, tmp_path):
    """The optimisation must survive — this is not "always re-run"."""
    out = _run(f'''
        log_warn() {{ echo "WARN: $*"; }}
        . scripts/build/lib/state.sh
        state_step_should_run 99-probe abc123 "{state}" && echo RUNS || echo SKIPS
    ''', state)
    assert "SKIPS" in out.stdout, (
        f"a completed step whose artifact EXISTS must still skip.\n{out.stdout}{out.stderr}"
    )


def test_a_missing_artifact_forces_a_rerun(state, tmp_path):
    """The whole point. A tmpfs does not survive a reboot."""
    out = _run(f'''
        log_warn() {{ echo "WARN: $*"; }}
        . scripts/build/lib/state.sh
        state_step_should_run 99-probe abc123 "{tmp_path}/gone" && echo RUNS || echo SKIPS
    ''', state)
    assert "RUNS" in out.stdout, (
        "a completed step whose output no longer exists must RE-RUN. Otherwise "
        "the failure surfaces steps later, at whatever finally looks for the "
        f"artifact.\n{out.stdout}{out.stderr}"
    )
    assert "is GONE" in out.stdout, (
        "it must SAY the output is missing — 'already completed' followed by a "
        "failure four steps later is the confusing part"
    )


def test_no_artifact_named_behaves_exactly_as_before(state):
    """Every existing caller passes two arguments; none may change behaviour."""
    out = _run(f'''
        log_warn() {{ echo "WARN: $*"; }}
        . scripts/build/lib/state.sh
        state_step_should_run 99-probe abc123 && echo RUNS || echo SKIPS
        state_step_should_run 99-probe DIFFERENT && echo RUNS2 || echo SKIPS2
    ''', state)
    assert "SKIPS" in out.stdout, "matching hash + no artifacts named → skip"
    assert "RUNS2" in out.stdout, "changed inputs must still force a re-run"


@pytest.mark.parametrize("step,artifact", sorted(VOLATILE_STEPS.items()))
def test_each_volatile_step_declares_its_output(step, artifact):
    """A step writing into the tmpfs forge MUST name what it produces.

    Otherwise its "completed" outlives its output every single reboot.
    """
    src = (REPO_ROOT / "scripts/build" / f"{step}.sh").read_text(encoding="utf-8")
    call = next((l for l in src.splitlines()
                 if "state_step_should_run" in l and not l.lstrip().startswith("#")), None)
    assert call, f"{step}.sh does not call state_step_should_run"
    # the artifact may be on the same line or the continuation below it
    idx = src.index(call)
    window = src[idx: idx + 400]
    assert artifact in window, (
        f"{step}.sh must declare {artifact!r} as its output so a reboot that "
        "empties the tmpfs forces a re-run instead of a confusing failure at "
        "step 07"
    )


def test_the_helper_documents_why_it_checks():
    """The next reader will wonder why a skip check touches the filesystem."""
    body = STATE_LIB.read_text(encoding="utf-8")
    seg = body[body.index("state_step_should_run() {"):]
    seg = seg[: seg.index("\n}\n")]
    assert "tmpfs" in seg, (
        "state_step_should_run should say WHY it verifies outputs — a tmpfs "
        "forge that does not survive a reboot is the reason"
    )
