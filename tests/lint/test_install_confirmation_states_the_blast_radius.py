"""The confirmation must name every system it changes — not just the target.

2026-07-27. `sovereign-osctl install system --to <disk>` has strong gates: a
--plan preview, SOVEREIGN_OS_CONFIRM_DESTROY=YES, and typing the disk path back.
What it said was:

    This will PARTITION /dev/X and install sovereign-os.

On a fresh install, Phase 2 (migrate-home.sh) also copies /home onto the new
shared LV and registers it in **THIS HOST'S** /etc/fstab — so after the next
reboot the machine the operator is standing on mounts the shared /home. That is
a change to the running system, and confirming "partition that disk" is not
informed consent for it.

Typing a disk path back is a strong gate only if the prompt describes what is
actually about to happen.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
MIGRATE = REPO_ROOT / "scripts" / "install" / "migrate-home.sh"


def confirm_block() -> str:
    """The `install system` confirmation specifically.

    There are TWO "Gate 6 — interactive confirm" blocks — the first belongs to
    `install image`. Anchoring on the first read the wrong flow entirely
    (2026-07-27, my own lint, again). Anchor on text unique to this one.
    """
    body = OSCTL.read_text(encoding="utf-8")
    i = body.index("and install sovereign-os.")
    start = body.rindex("if [ -z", 0, i)
    block = body[start:body.index("device confirmation mismatch", i)]
    # CODE only. The comment above the disclosure explains it in the same words,
    # so a comment-inclusive check passed even after the disclosure itself was
    # deleted — proven by mutation, and the sixth lint this session to match its
    # own prose (2026-07-27).
    return "\n".join(l for l in block.splitlines() if not l.lstrip().startswith("#"))


def test_the_host_side_effect_is_disclosed():
    block = confirm_block()
    assert "THIS running host" in block or "THIS HOST" in block.upper(), (
        "the prompt must say that the running host's /home and fstab change; "
        "the operator is confirming a target disk, not their own machine"
    )
    assert "fstab" in block, "name the specific file that changes"


def test_the_disclosure_is_conditional_on_that_phase_running():
    """A reflash skips Phase 2 — claiming an fstab change there would be false."""
    block = confirm_block()
    assert 'reflash' in block, (
        "the host-change disclosure must be gated on reflash=0; on a reflash "
        "Phase 2 does not run and the claim would be untrue"
    )


def test_the_claim_matches_what_migrate_home_actually_does():
    """Guard against the prompt drifting from the behaviour it describes."""
    body = MIGRATE.read_text(encoding="utf-8")
    assert "/etc/fstab" in body, (
        "migrate-home.sh no longer touches fstab — the confirmation text now "
        "over-claims and should be revisited"
    )
    assert "already has a /home entry" in body, (
        "the prompt promises an existing /home line is left untouched; the "
        "script must still honour that"
    )


def test_the_strong_gates_are_still_present():
    body = OSCTL.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_CONFIRM_DESTROY" in body
    assert "Type the disk path" in body, (
        "typing the device back is the last gate before an irreversible write"
    )
