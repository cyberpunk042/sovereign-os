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
