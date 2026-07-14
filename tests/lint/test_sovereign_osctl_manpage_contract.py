"""Contract for the sovereign-osctl(1) source and generated manual."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "sovereign-osctl"
SOURCE = ROOT / "docs" / "man" / "sovereign-osctl.1.md"
MANPAGE = ROOT / "docs" / "man" / "sovereign-osctl.1"
GENERATOR = ROOT / "scripts" / "docs" / "build-sovereign-osctl-manpage.sh"
MAKEFILE = ROOT / "Makefile"

REQUIRED_SECTIONS = (
    "NAME",
    "SYNOPSIS",
    "DESCRIPTION",
    "PRIMARY COMMAND FAMILIES",
    "COMPLETE TOP-LEVEL COMMAND INDEX",
    "ENVIRONMENT",
    "FILES",
    "EXAMPLES",
    "EXIT STATUS",
    "SEE ALSO",
    "REPORTING BUGS",
    "LICENSE",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _dispatcher_commands() -> set[str]:
    body = _read(CLI)
    marker = "# ------------------------------ dispatch"
    assert marker in body, "sovereign-osctl dispatch marker moved or disappeared"
    dispatch = body.split(marker, 1)[1]
    commands = set(re.findall(r"^  ([a-z][a-z0-9-]*)\)", dispatch, re.MULTILINE))
    assert len(commands) >= 100, (
        "dispatcher extraction unexpectedly found fewer than 100 top-level commands"
    )
    return commands


def test_markdown_remains_the_canonical_editable_source():
    body = _read(SOURCE)
    assert body.startswith("% SOVEREIGN-OSCTL(1)")
    for section in REQUIRED_SECTIONS:
        assert f"# {section}" in body, f"Markdown source missing {section!r}"


def test_generated_roff_is_a_valid_section_one_shape():
    body = _read(MANPAGE)
    assert '.TH "SOVEREIGN-OSCTL" "1"' in body
    for section in REQUIRED_SECTIONS:
        assert f".SH {section}" in body, f"generated roff missing {section!r}"


def test_every_dispatched_top_level_command_is_documented_in_both_forms():
    source = _read(SOURCE)
    roff = _read(MANPAGE)
    for command in sorted(_dispatcher_commands()):
        assert f"**{command}**" in source, (
            f"Markdown man source missing dispatched command {command!r}"
        )
        assert f"\\f[B]{command}\\f[R]" in roff, (
            f"generated roff missing dispatched command {command!r}"
        )


def test_generator_and_install_contract():
    generator = _read(GENERATOR)
    makefile = _read(MAKEFILE)
    assert "pandoc -s -t man" in generator
    assert "cmp -s" in generator
    assert "man:" in makefile and "man-check:" in makefile
    assert (
        'install -m 644 docs/man/sovereign-osctl.1 '
        '"$(DESTDIR)$(PREFIX)/share/man/man1/sovereign-osctl.1"'
    ) in makefile
    assert "Skipping manpage" not in makefile
