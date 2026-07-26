"""A substrate the orchestrator can SELECT must be handled by every step.

2026-07-26. `SOVEREIGN_OS_ARTIFACT=installer` was repointed at the standard
debian-installer ISO (substrate `installer-cdd`). The handler was added to step
07 — and only step 07. The build then died immediately:

    ERROR [05-substrate-prepare] unknown substrate: installer-cdd
      (valid: mkosi, live-build, rpm-ostree, nixos)

…and step 06's renderer had the SAME gap one step further on, waiting.

Adding a substrate touches every stage that dispatches on it. This lint walks
the substrates the orchestrator can actually produce and asserts each one is
either handled or explicitly rejected — never silently unknown.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATE = REPO_ROOT / "scripts" / "build" / "orchestrate.sh"
PREPARE = REPO_ROOT / "scripts" / "build" / "05-substrate-prepare.sh"
RENDER = REPO_ROOT / "scripts" / "whitelabel" / "render.py"
BUILD = REPO_ROOT / "scripts" / "build" / "07-image-build.sh"


def selectable_substrates() -> set[str]:
    """Substrates the orchestrator can assign from an ARTIFACT value."""
    text = ORCHESTRATE.read_text(encoding="utf-8")
    subs = set(re.findall(r"SOVEREIGN_OS_SUBSTRATE=([a-z0-9-]+)", text))
    # the default, set via `: "${SOVEREIGN_OS_SUBSTRATE:=mkosi}"`
    m = re.search(r'SOVEREIGN_OS_SUBSTRATE:=([a-z0-9-]+)', text)
    if m:
        subs.add(m.group(1))
    return subs


def test_the_orchestrator_selects_at_least_the_known_set():
    subs = selectable_substrates()
    assert {"mkosi", "live-build", "installer-cdd"} <= subs, (
        f"expected the three real substrates to be selectable; got {sorted(subs)}"
    )


@pytest.mark.parametrize("substrate", sorted(selectable_substrates()))
def test_step_05_handles_it(substrate: str):
    """Step 05 rejects anything not in its case list — the exact failure."""
    text = PREPARE.read_text(encoding="utf-8")
    case_block = text[text.index('case "${SOVEREIGN_OS_SUBSTRATE}" in'):text.index("\nesac")]
    arms = re.findall(r"^\s{2}([a-z0-9|-]+)\)", case_block, re.M)
    handled = {a for arm in arms for a in arm.split("|")}
    assert substrate in handled, (
        f"step 05 has no case arm for {substrate!r}, so a build the orchestrator "
        f"can start dies at 'unknown substrate'. handled: {sorted(handled)}"
    )


@pytest.mark.parametrize("substrate", sorted(selectable_substrates()))
def test_the_whitelabel_renderer_accepts_it(substrate: str):
    """Step 06 passes --substrate straight through to render.py's choices=."""
    text = RENDER.read_text(encoding="utf-8")
    m = re.search(r'choices=\[([^\]]+)\]', text)
    assert m, "render.py must declare its substrate choices"
    choices = {c.strip().strip('"\'') for c in m.group(1).split(",")}
    assert substrate in choices, (
        f"render.py rejects --substrate {substrate!r}, so step 06 fails for a "
        f"build step 05 just let through. choices: {sorted(choices)}"
    )


@pytest.mark.parametrize("substrate", sorted(selectable_substrates()))
def test_step_07_builds_it(substrate: str):
    text = BUILD.read_text(encoding="utf-8")
    arms = re.findall(r"^\s{2}([a-z0-9|-]+)\)", text, re.M)
    handled = {a for arm in arms for a in arm.split("|")}
    assert substrate in handled, (
        f"step 07 has no build arm for {substrate!r}. handled: {sorted(handled)}"
    )


def test_the_unknown_substrate_message_lists_what_is_valid():
    """The error must name the real set, or it sends the reader down a hole."""
    text = PREPARE.read_text(encoding="utf-8")
    m = re.search(r"unknown substrate: \$\{SOVEREIGN_OS_SUBSTRATE\} \(valid: ([^)]+)\)", text)
    assert m, "the unknown-substrate error must enumerate the valid ones"
    listed = {s.strip() for s in m.group(1).split(",")}
    for s in selectable_substrates():
        assert s in listed, (
            f"{s!r} is selectable but missing from the 'valid:' list — the error "
            "message would deny a substrate the orchestrator itself produces"
        )


ARTIFACT_STEPS = ("05-substrate-prepare", "07-image-build",
                  "08-image-sign", "09-image-verify")


@pytest.mark.parametrize("step", ARTIFACT_STEPS)
def test_artifact_is_part_of_the_step_cache_key(step: str):
    """Switching the artifact MUST invalidate every step that produces it.

    Step 07's inputs_hash covered only (script, profile, repo_sig). Switching
    from the appliance to the installer changed neither the repo nor the
    profile, so 07 reported "already completed with matching inputs", SKIPPED,
    and the pipeline exited 0 having built nothing. The operator flashed a
    5-hour-old ISO twice believing it was fresh (2026-07-26).

    Step 05 folded in the artifact and therefore re-ran — which is exactly why
    the failure was so confusing: the pipeline looked busy and still produced
    nothing.
    """
    text = (REPO_ROOT / "scripts" / "build" / f"{step}.sh").read_text(encoding="utf-8")
    # Read the WHOLE assignment: step 05's key contains a nested $( … ) (the
    # root_pw term), so a non-greedy regex stops at the inner `)"` and misses
    # everything after it. Walk lines until the statement's own closing `)"`.
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if 'inputs_hash="$(state_inputs_hash' in l), None)
    assert start is not None, f"{step}: no inputs_hash found"
    key_lines = []
    for l in lines[start:]:
        key_lines.append(l)
        if l.rstrip().endswith(')"'):
            break
    key = "\n".join(key_lines)
    assert "artifact=" in key, (
        f"{step}: SOVEREIGN_OS_ARTIFACT is not part of the cache key, so "
        "changing the artifact cannot invalidate this step — it will skip and "
        "leave the previous artifact in place while reporting success"
    )


def test_the_di_build_proves_it_wrote_an_iso():
    """Exit status is not evidence of an artifact."""
    text = (REPO_ROOT / "scripts" / "build" / "07-image-build.sh").read_text(encoding="utf-8")
    blk = text[text.index("installer-cdd)"):text.index("  live-build)")]
    assert "_iso_before" in blk and "_iso_now" in blk, (
        "the d-i branch must fingerprint the ISO before and after, or a builder "
        "that exits 0 without writing anything reads as success"
    )
    assert "installer-cdd-no-artifact" in blk, "no-artifact must be a hard failure"
    assert "installer-cdd-stale-artifact" in blk, (
        "an UNCHANGED iso must be a hard failure — that is the exact case where "
        "the operator flashes yesterday's image"
    )
    assert "do NOT flash" in blk, "the error must tell the operator not to flash it"


def test_step_05_always_writes_the_env_handoff():
    """Every exit path must leave the handoff correct — step 07 SOURCES it.

    env-substrate.sh `export`s SOVEREIGN_OS_SUBSTRATE, so it OVERRIDES the
    orchestrator's choice in step 07. The installer-cdd branch exited early,
    before the handoff was written, leaving the PREVIOUS run's value: step 05
    ran installer-cdd, step 07 ran live-build, live-build said "Skipping
    binary_iso, already done", the 1-hour-old ISO was left in place, the build
    exited 0 and the operator flashed the stale image (2026-07-26).
    """
    text = PREPARE.read_text(encoding="utf-8")
    case_start = text.index("  installer-cdd)")
    branch = text[case_start:text.index("\n  *)", case_start)]
    assert "env-substrate.sh" in branch, (
        "the installer-cdd branch exits early and MUST write the env handoff "
        "first, or step 07 inherits the previous run's substrate"
    )
    assert branch.index("env-substrate.sh") < branch.index("exit 0"), (
        "the handoff must be written BEFORE the early exit"
    )


def test_step_07_prefers_the_requested_substrate_over_a_stale_handoff():
    """Defence in depth for the same class."""
    text = BUILD.read_text(encoding="utf-8")
    assert "_substrate_requested" in text, (
        "step 07 must remember what the orchestrator asked for before sourcing "
        "the handoff, which can be stale"
    )
    head = text[:text.index("log_step_header")]
    assert "STALE" in head or "stale" in head, (
        "a substrate mismatch must be reported, not silently resolved"
    )


def test_the_cdd_builder_gets_its_own_home_not_roots():
    """A pkexec build runs as root; the d-i builder must run as the operator.

    `runuser --preserve-environment` carried HOME=/root into a process running
    as the operator, so gpg tried to create /root/.gnupg and build-simple-cdd
    died in read_configuration() before downloading anything (2026-07-26).
    """
    text = BUILD.read_text(encoding="utf-8")
    blk = text[text.index("installer-cdd)"):text.index("  live-build)")]
    # Strip comments — the fix's own explanation NAMES the flag it removed.
    code = "\n".join(l for l in blk.splitlines() if not l.lstrip().startswith("#"))
    assert "--preserve-environment" not in code, (
        "preserving root's environment gives the dropped-privilege builder "
        "HOME=/root, which gpg cannot write to"
    )
    assert "runuser" in code and "HOME=" in code, (
        "runuser must hand the builder that user's OWN home explicitly"
    )
    assert "getent passwd" in code, "resolve the home dir, do not assume /home/<user>"


def test_the_cdd_builder_is_told_where_to_write():
    """It used to hardcode build/sain-01/output and ignore the pipeline."""
    src = (REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh").read_text(encoding="utf-8")
    assert 'OUT="${REPO}/build/sain-01/output"' not in src, (
        "the builder must not hardcode one profile's output directory"
    )
    assert "SOVEREIGN_OS_BUILD_OUT" in src, "honour the pipeline's output dir"
