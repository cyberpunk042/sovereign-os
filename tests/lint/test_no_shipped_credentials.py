"""No installer artifact may carry a credential in cleartext.

2026-07-27. profiles/*.preseed contained:

    d-i passwd/root-password      password sovereign
    d-i passwd/user-password      password sovereign
    d-i user-setup/allow-password-weak boolean true

Those files are copied onto the ISO at /simple-cdd/*.preseed, world readable
inside the image. Every machine installed from any such build had root:sovereign,
and anyone holding the image knew it. The TUI installer had been fixed to refuse
this exact default earlier the same week; the debian-installer path had not.

d-i simply asks for both passwords, right after the disk pick the operator
already answers. Automating it later means preseeding
passwd/root-password-crypted with a HASH generated at build time — never a
plaintext value in a tracked file (SDD-015: secrets live in
/etc/sovereign-os/*.env).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")


def live_lines(name: str) -> list[str]:
    """Preseed directives only — a comment explaining the fix is not a leak."""
    return [l for l in (PROFILES / name).read_text(encoding="utf-8").splitlines()
            if l.startswith("d-i ")]


@pytest.mark.parametrize("name", PRESEEDS)
def test_no_plaintext_password_directive(name: str):
    bad = [l for l in live_lines(name)
           if re.match(r"d-i\s+\S*passwd/\S*password\S*\s+password\s+\S", l)]
    assert not bad, (
        f"{name} ships a cleartext password: {bad}. It lands on the ISO at "
        "/simple-cdd/ and becomes the root password of every machine installed "
        "from that image."
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_weak_passwords_are_not_pre_approved(name: str):
    bad = [l for l in live_lines(name) if "allow-password-weak" in l]
    assert not bad, (
        f"{name} pre-answers the weak-password warning: {bad}. That prompt is "
        "the last thing standing between a habit and a shipped credential."
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_a_crypted_password_would_be_acceptable(name: str):
    """Automation is fine — as a hash, generated at build time.

    Guard the shape so a future 'fix' does not reintroduce plaintext under a
    different key name.
    """
    for l in live_lines(name):
        if "password-crypted" in l:
            value = l.split(None, 3)[-1] if len(l.split(None, 3)) > 3 else ""
            assert value.startswith("$"), (
                f"{name}: password-crypted must hold a hash ($6$…), got {value!r}"
            )


def test_the_direct_path_refuses_its_own_default_password():
    """Both install paths, one rule.

    install-sovereign-root.sh has four chpasswd sites, each defaulting to the
    literal "sovereign" when SOVEREIGN_OS_ROOT_PASS / _USER_PASS are unset — so
    a plain run produced root:sovereign on a machine the operator believed was
    theirs alone. installer-tui.sh already refused that default; the preseeds
    carried the same credential in cleartext. Same gate everywhere (2026-07-27).
    """
    text = (REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh").read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD" in text, (
        "the direct installer must refuse the built-in default password unless "
        "the operator opts in, exactly as installer-tui.sh does"
    )
    guard = text[:text.index("sovereign_verify_install()")]
    assert "REFUSING" in guard, "the refusal must happen before any install work"


def test_the_opt_in_variable_is_spelled_the_same_everywhere():
    """A second spelling is a second bypass nobody knows about."""
    import subprocess
    out = subprocess.run(
        ["git", "grep", "-oh", "SOVEREIGN_OS_ALLOW_DEFAULT[A-Z_]*", "--", "scripts"],
        capture_output=True, text=True, cwd=REPO_ROOT).stdout.split()
    assert set(out) == {"SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD"}, (
        f"inconsistent opt-in variable names: {sorted(set(out))}"
    )
