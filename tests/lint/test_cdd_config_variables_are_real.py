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
    # Target THIS heredoc, not merely the first `cat >` in the file. build.sh
    # writes several; the postinst one is <<'POSTINST' (quoted) and is allowed
    # backticks. Anchoring on "cat > " alone made this test fail on an
    # unrelated, perfectly safe heredoc (2026-07-26).
    start = text.index("sovereign.conf")
    start = text.rindex("cat > ", 0, start)
    body = text[start:text.index("\nCONF\n", start)]
    assert "`" not in body, (
        "backticks inside the unquoted sovereign.conf heredoc run as commands; "
        "use plain quotes in comments there"
    )


def test_debian_cd_gets_the_env_it_needs_for_non_free_firmware():
    """Two vars are read by debian-cd, not simple-cdd, and both were unset.

    NONFREE_COMPONENTS: tools/which_deb splits it into the component list only
    when NONFREE is set. Unset, it split undef and silently DROPPED the non-free
    components, leaving just an "uninitialized value" warning.

    DEP11: make_disc_trees.pl defaults it to 1 and then runs
    generate_firmware_patterns against dep11/Components-<arch>.yml.gz. A
    reprepro-built offline mirror carries no DEP-11 metadata, so the build died
    with "generate_firmware_patterns failed: 512" (2026-07-26).
    """
    text = BUILD.read_text(encoding="utf-8")
    assert 'export NONFREE_COMPONENTS="non-free non-free-firmware"' in text, (
        "which_deb drops the non-free components without this"
    )
    assert "export DEP11=0" in text, (
        "debian-cd defaults DEP11=1 and needs AppStream metadata our reprepro "
        "mirror does not build; the firmware patterns only power d-i's "
        "detect-missing-firmware prompt, which this profile does not rely on"
    )


def test_the_generated_conf_survives_set_u():
    """build.sh runs under `set -euo pipefail` and the heredoc is UNQUOTED.

    Any $VAR in it — including inside a COMMENT — expands, and an unset one
    aborts the whole build. A comment quoting Perl's $ENV{NONFREE_COMPONENTS}
    would have killed the build before simple-cdd ever started (caught
    pre-flight, 2026-07-26).
    """
    text = BUILD.read_text(encoding="utf-8")
    # Anchor on the sovereign.conf heredoc specifically. `text.index("cat > ")`
    # finds the FIRST one in the file — which is the postinst, written with
    # <<'POSTINST' (QUOTED), where a `${VAR}` in a comment is literal and
    # harmless. Its sibling test was corrected the same way; this one was
    # missed, and it then failed on a perfectly safe comment (2026-07-27).
    start = text.rindex("cat > ", 0, text.index("sovereign.conf"))
    body = text[start:text.index("\nCONF\n", start)]
    bad = [l for l in body.splitlines()
           if l.lstrip().startswith("#") and "$" in l]
    assert not bad, (
        "comments inside the unquoted heredoc must contain no $ expansions; "
        f"offending line(s): {bad}"
    )
