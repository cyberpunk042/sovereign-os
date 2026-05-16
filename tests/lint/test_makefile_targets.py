"""Layer 1 lint — Makefile presence + key target presence + help-text
shape. Catches a regression class: someone edits the Makefile and
accidentally drops the standard operator surface (setup / test /
lint / etc.).
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"

# Targets that the operator-side workflow depends on
REQUIRED_TARGETS = (
    "help",
    "setup",
    "validate",
    "lint",
    "unit",
    "l3",
    "l3-fast",
    "test",
    "ci",
    "dry-run",
    "preflight",
    "smoke",
    "clean",
)


def test_makefile_exists():
    assert MAKEFILE.is_file(), f"Makefile missing at {MAKEFILE}"


def test_makefile_has_shell_safety():
    """Makefile must declare a strict SHELL (/bin/bash) so recipes
    don't run under /bin/sh's looser POSIX semantics."""
    text = MAKEFILE.read_text()
    assert "SHELL := /bin/bash" in text or "SHELL = /bin/bash" in text, \
        "Makefile must declare 'SHELL := /bin/bash' for recipe safety"


def test_makefile_default_goal_is_help():
    """Operator typing 'make' should get help, not a destructive run."""
    text = MAKEFILE.read_text()
    assert ".DEFAULT_GOAL := help" in text or ".DEFAULT_GOAL = help" in text, \
        "Default goal must be 'help' so bare 'make' doesn't surprise the operator"


@pytest.mark.parametrize("target", REQUIRED_TARGETS, ids=lambda t: t)
def test_required_target_present(target: str):
    """Each required target appears as a Makefile rule head with ## comment."""
    text = MAKEFILE.read_text()
    # Match: "target:  ## help text" (with any number of deps between target: and ##)
    pat = re.compile(rf"^{re.escape(target)}:[^#\n]*##\s+\S", re.M)
    assert pat.search(text), f"Makefile missing target with help-comment: {target}"


def test_phony_declared():
    """Required targets should be in .PHONY (none of them produce files)."""
    text = MAKEFILE.read_text()
    phony_match = re.search(r"^\.PHONY:\s+(.+?)(?=\n\.\S|\n\n|\Z)", text, re.M | re.S)
    assert phony_match, ".PHONY declaration missing"
    phony_targets = set(phony_match.group(1).split())
    missing = [t for t in REQUIRED_TARGETS if t not in phony_targets]
    assert not missing, f".PHONY missing targets: {missing}"


def test_profile_default_is_sain_01():
    """Profile default = sain-01 keeps the SAIN-01 milestone visible."""
    text = MAKEFILE.read_text()
    assert "PROFILE ?= sain-01" in text or "PROFILE = sain-01" in text, \
        "Default PROFILE should be sain-01"
