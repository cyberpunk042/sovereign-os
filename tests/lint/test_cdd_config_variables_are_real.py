"""A misspelled simple-cdd variable is silently ignored, not an error.

2026-07-26. The builder exported `mirror_files_include="main contrib non-free
non-free-firmware"`. No such simple-cdd variable exists, so it did nothing and
the mirror kept its default of `main` alone. That only surfaced weeks later,
the moment the profile needed a non-free-firmware package:

    ERROR missing required packages from profile sovereign:
      amd64-microcode firmware-amd-graphics firmware-nvidia-graphics …

Every one of them non-free-firmware. The real name is `mirror_components`.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"


def test_the_mirror_carries_the_non_free_firmware_component():
    text = BUILD.read_text(encoding="utf-8")
    m = re.search(r'^export mirror_components="([^"]+)"', text, re.M)
    assert m, (
        "the builder must set mirror_components — simple-cdd defaults it to "
        '["main"], which cannot satisfy any firmware-* package'
    )
    comps = m.group(1).split()
    assert "non-free-firmware" in comps, (
        f"firmware-amd-graphics lives in non-free-firmware; components: {comps}"
    )


def test_the_dead_variable_is_gone():
    # Comments are allowed to NAME it — the fix's own explanation does, so that
    # nobody re-adds it. Only live code must be free of it.
    code = "\n".join(l for l in BUILD.read_text(encoding="utf-8").splitlines()
                      if not l.lstrip().startswith("#"))
    assert "mirror_files_include" not in code, (
        "mirror_files_include is not a simple-cdd variable; keeping it around "
        "invites someone to 'fix' the mirror by editing a name nothing reads"
    )


def test_no_command_substitution_in_the_generated_conf():
    """The sovereign.conf heredoc is UNQUOTED.

    Backticks inside it are command substitution — even in a comment. A comment
    explaining the mirror_components fix would have EXECUTED `mirror_components`
    while writing the config (caught before it shipped, 2026-07-26).
    """
    text = BUILD.read_text(encoding="utf-8")
    start = text.index("cat > ")
    body = text[start:text.index("\nCONF\n", start)]
    assert "`" not in body, (
        "backticks inside the unquoted sovereign.conf heredoc run as commands; "
        "use plain quotes in comments there"
    )
