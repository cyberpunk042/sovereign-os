"""The runbook a first-time operator follows must describe what the code does.

2026-07-27. docs/src/install-runbook.md carried two claims that had gone false:

  * "Substrate-aware: uses mkosi ...; the live-build path swaps the 05/07 build
    steps" — no mention of `installer-cdd`, which is what
    SOVEREIGN_OS_ARTIFACT=installer now builds. A reader would conclude the
    installer is the live-build ISO, i.e. exactly the bespoke TUI the operator
    rejected.
  * "These run automatically once at first boot" (the post-install hooks) — on
    the debian-installer path they do not. The units ship installed and
    DISABLED on purpose. An operator waiting for them to fire waits forever.

Docs that describe an older design are worse than missing docs: they are
followed.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "src" / "install-runbook.md"
ORCHESTRATE = REPO_ROOT / "scripts" / "build" / "orchestrate.sh"


def selectable_artifacts() -> set[str]:
    """ARTIFACT values orchestrate.sh actually dispatches on."""
    text = ORCHESTRATE.read_text(encoding="utf-8")
    block = text[text.index("SOVEREIGN_OS_ARTIFACT"):]
    # The arms became `installer:<distro>)` on 2026-07-28 when the DISTRO axis
    # landed; the ARTIFACT name is the part before the colon.
    return set(re.findall(r"^\s{2,}(installer-live|installer|image)[:)]", block, re.M))


def test_every_selectable_artifact_is_documented():
    arts = selectable_artifacts()
    assert arts, "could not read the artifact dispatch from orchestrate.sh"
    body = RUNBOOK.read_text(encoding="utf-8")
    missing = [a for a in sorted(arts) if f"`{a}`" not in body]
    assert not missing, (
        f"the runbook does not document artifact(s) {missing} that the build "
        "can produce — a reader picks the wrong one"
    )


def test_the_installer_substrate_is_named():
    body = RUNBOOK.read_text(encoding="utf-8")
    assert "installer-cdd" in body, (
        "the runbook must name the substrate that builds the real Debian "
        "installer; without it, 'installer' reads as the live-build TUI"
    )


def test_first_boot_hooks_are_not_claimed_to_be_automatic():
    body = RUNBOOK.read_text(encoding="utf-8")
    i = body.index("POST-INSTALL — first-boot hooks")
    section = body[i:i + 1200]
    assert "do NOT run automatically" in section, (
        "the units ship DISABLED on the d-i path; claiming they fire at first "
        "boot leaves the operator waiting for something that never happens"
    )
    assert "install logs" in section, (
        "point the reader at the report that says what the install actually did"
    )
