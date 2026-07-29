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
    # Match the ARM rather than one literal substrate name: the installer
    # substrates share a single arm (`installer-cdd|ubuntu-autoinstall)`) since
    # Ubuntu 26.04 was added, and pinning the old literal made this guard
    # disappear the moment the arm was renamed (2026-07-28).
    m = re.search(r"^  (installer-cdd[a-z0-9|-]*)\)", text, re.M)
    assert m, "step 05 must still have an installer arm that exits early"
    branch = text[m.start():text.index("\n  *)", m.start())]
    assert "env-substrate.sh" in branch, (
        "the installer branch exits early and MUST write the env handoff "
        "first, or step 07 inherits the previous run's substrate"
    )
    assert branch.index("env-substrate.sh") < branch.index("exit 0"), (
        "the handoff must be written BEFORE the early exit"
    )
    # The handoff must carry the DISTRO too. It exports over the orchestrator's
    # values in step 07, so a handoff naming only the substrate would let a
    # stale suite leak into the build — the same failure, one variable over.
    assert "SOVEREIGN_OS_DISTRO" in branch and "SOVEREIGN_OS_SUITE" in branch, (
        "the env handoff must export DISTRO and SUITE alongside SUBSTRATE"
    )


DISTRO_LIB = REPO_ROOT / "scripts" / "build" / "lib" / "distro.sh"


def test_the_orchestrator_and_the_distro_lib_agree_on_the_installer():
    """Two places name the per-distro installer; they must not drift.

    orchestrate.sh spells the substrates LITERALLY (selectable_substrates()
    regexes them out of that file, so routing them through a helper would hide
    them and silently shrink every parametrised test above). lib/distro.sh
    keeps the same mapping for other callers. Duplication is deliberate —
    this asserts the copies agree (2026-07-28).
    """
    orch = ORCHESTRATE.read_text(encoding="utf-8")
    lib = DISTRO_LIB.read_text(encoding="utf-8")
    for distro, substrate in (("ubuntu", "ubuntu-autoinstall"),
                              ("debian", "installer-cdd")):
        assert re.search(rf"installer:{distro}\)\s+SOVEREIGN_OS_SUBSTRATE={substrate}", orch) \
            or re.search(rf"installer:\*\)\s+SOVEREIGN_OS_SUBSTRATE={substrate}", orch), (
            f"orchestrate.sh must map ARTIFACT=installer + DISTRO={distro} to {substrate}"
        )
        assert substrate in lib, (
            f"lib/distro.sh's distro_installer_substrate() must still know {substrate}"
        )


MKOSI_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"


def test_the_mkosi_emitter_agrees_with_the_distro_lib():
    """mkosi-emit.sh re-encodes the distro map in Python; it must not drift.

    The emitter is a bash wrapper around an embedded Python heredoc, so it
    cannot source lib/distro.sh — it carries its own copy of the suite defaults
    and the component lists. That is a duplication, and this repo's recurring
    failure is a fix landing in one copy and not the other. Assert both copies
    still say the same thing (2026-07-28).
    """
    lib = DISTRO_LIB.read_text(encoding="utf-8")
    emit = MKOSI_EMIT.read_text(encoding="utf-8")
    for suite in ("trixie", "resolute"):
        assert suite in lib and suite in emit, (
            f"suite {suite!r} is missing from "
            f"{'lib/distro.sh' if suite not in lib else 'mkosi-emit.sh'}"
        )
    for components in ("main contrib non-free non-free-firmware",
                       "main restricted universe multiverse"):
        assert components in lib and components in emit, (
            f"apt components {components!r} differ between lib/distro.sh and "
            "mkosi-emit.sh — one distro would build against the wrong archive "
            "sections and lose the GPU/ZFS stack"
        )
    for host in ("snapshot.debian.org", "snapshot.ubuntu.com"):
        assert host in lib and host in emit, (
            f"snapshot host {host!r} differs between lib/distro.sh and mkosi-emit.sh"
        )


@pytest.mark.parametrize("step", ("05-substrate-prepare", "07-image-build",
                                  "08-image-sign", "09-image-verify"))
def test_distro_is_part_of_the_step_cache_key(step: str):
    """Switching DISTRO must invalidate every step that produces an artifact.

    Exactly the ARTIFACT hazard one axis over. Debian and Ubuntu builds share a
    profile and a repo, so without distro in the key, flipping the panel's
    distro selector would leave inputs_hash unchanged, every step would report
    "already completed with matching inputs", and the operator would flash a
    Debian ISO believing it was Ubuntu. That precise shape burned two days in
    2026-07-26 with ARTIFACT; it is not getting a second turn.
    """
    text = (REPO_ROOT / "scripts" / "build" / f"{step}.sh").read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines)
                  if 'inputs_hash="$(state_inputs_hash' in l), None)
    assert start is not None, f"{step} has no inputs_hash"
    # Walk to the statement's own closing `)"` — step 05's key nests `$( … )`,
    # so a regex that stops at the first `)"` reads only half the key.
    block, depth = [], 0
    for line in lines[start:]:
        block.append(line)
        depth += line.count("$(") - line.count(')"')
        if depth <= 0 and len(block) > 1:
            break
    joined = "\n".join(block)
    assert "distro=" in joined, (
        f"{step}'s inputs_hash omits the distro — switching debian↔ubuntu would "
        f"be a cache HIT and the step would skip, producing nothing"
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


def test_every_substrate_case_in_step_07_covers_every_substrate():
    """Step 07 dispatches on the substrate MORE THAN ONCE.

    The build arm was wired for installer-cdd, but a second `case` further down
    ("Discover output (per substrate)") was not. The d-i ISO built fine, then
    the step died on `output_dir: unbound variable` and the pipeline reported
    failure for an artifact that existed (2026-07-26). Checking only the first
    case block is how this survived three rounds of fixes.
    """
    text = BUILD.read_text(encoding="utf-8")
    blocks = []
    idx = 0
    while True:
        i = text.find('case "${SOVEREIGN_OS_SUBSTRATE}" in', idx)
        if i == -1:
            break
        end = text.index("\nesac", i) if "\nesac" in text[i:] else len(text)
        blocks.append(text[i:text.index("esac", i)])
        idx = i + 1
    assert len(blocks) >= 2, "expected step 07 to dispatch on substrate more than once"
    for n, blk in enumerate(blocks):
        arms = {a for arm in re.findall(r"^\s+([a-z0-9|*-]+)\)", blk, re.M)
                for a in arm.split("|")}
        if "*" in arms:
            continue  # a catch-all makes the block total
        for sub in selectable_substrates():
            assert sub in arms, (
                f"step 07 substrate case #{n + 1} has no arm for {sub!r} and no "
                f"catch-all; a selectable substrate falls through leaving its "
                f"variables unset. arms: {sorted(arms)}"
            )


def test_the_cdd_output_dir_matches_the_other_substrates():
    """_out must be the artifacts dir, not the build dir one level up."""
    text = BUILD.read_text(encoding="utf-8")
    blk = text[text.index("installer-cdd)"):text.index("  live-build)")]
    code = "\n".join(l for l in blk.splitlines() if not l.lstrip().startswith("#"))
    assert '_out="${SOVEREIGN_OS_BUILD_OUT}/output"' in code, (
        "BUILD_OUT is build/<profile>; writing the ISO there instead of its "
        "output/ subdir hides it from the flash panel"
    )


def test_the_dropped_privilege_builder_can_overwrite_an_existing_iso():
    """chown on the directory does not grant write on files inside it.

    cp opens an EXISTING target for writing. A root-owned mode-664 ISO from an
    earlier root-run build denied the operator write access, so the d-i build
    succeeded and the copy failed with "Permission denied" — twice, on two
    different paths (2026-07-26).
    """
    text = BUILD.read_text(encoding="utf-8")
    blk = text[text.index("installer-cdd)"):text.index("  live-build)")]
    code = "\n".join(l for l in blk.splitlines() if not l.lstrip().startswith("#"))
    assert "chown" in code, "the output dir must be handed to the build user"
    assert "*.iso" in code and "-exec chown" in code, (
        "existing artifacts must be chowned too, or the copy is denied by the "
        "file's own permissions regardless of who owns the directory"
    )
