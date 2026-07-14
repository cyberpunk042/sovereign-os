"""Contracts for the sovereign-osctl(1) manual-page suite."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "sovereign-osctl"
MAN_DIR = ROOT / "docs" / "man"
REGISTRY = MAN_DIR / "sovereign-osctl-command-topics.json"
GENERATOR = ROOT / "scripts" / "docs" / "build-sovereign-osctl-manpage.sh"
MAKEFILE = ROOT / "Makefile"
TOPICS = (
    "models",
    "agents",
    "hardware",
    "security",
    "operations",
    "governance",
    "install",
)
REQUIRED_SECTIONS = (
    "NAME",
    "SYNOPSIS",
    "DESCRIPTION",
    "SAFETY MODEL",
    "COMMON WORKFLOW",
    "EXAMPLES",
    "COMMAND REFERENCE",
    "FILES",
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
    assert marker in body
    dispatch = body.split(marker, 1)[1]
    commands = set(re.findall(r"^  ([a-z][a-z0-9-]*)\)", dispatch, re.MULTILINE))
    assert len(commands) >= 100
    return commands


def _registry() -> dict[str, list[str]]:
    data = json.loads(_read(REGISTRY))
    assert data["schema_version"] == 1
    assert tuple(data["pages"]) == TOPICS
    return data["pages"]


def test_every_dispatcher_command_has_exactly_one_manual_owner():
    pages = _registry()
    owned = [command for commands in pages.values() for command in commands]
    assert len(owned) == len(set(owned)), "a command is owned by multiple man pages"
    assert set(owned) == _dispatcher_commands(), (
        f"manual ownership drift: missing={sorted(_dispatcher_commands() - set(owned))}, "
        f"extra={sorted(set(owned) - _dispatcher_commands())}"
    )


def test_each_topic_has_editable_source_generated_roff_and_owned_commands():
    for topic, commands in _registry().items():
        source = _read(MAN_DIR / f"sovereign-osctl-{topic}.1.md")
        roff = _read(MAN_DIR / f"sovereign-osctl-{topic}.1")
        assert source.startswith(f"% SOVEREIGN-OSCTL-{topic.upper()}(1)")
        assert f'.TH "SOVEREIGN-OSCTL-{topic.upper()}" "1"' in roff
        for section in REQUIRED_SECTIONS:
            assert f"# {section}" in source
            assert f".SH {section}" in roff
        for command in commands:
            assert f"## {command}\n" in source, (
                f"{topic} Markdown missing owned command {command!r}"
            )
            assert f".SS {command}\n" in roff, (
                f"{topic} roff missing owned command {command!r}"
            )


def test_main_page_routes_operators_to_every_topic():
    source = _read(MAN_DIR / "sovereign-osctl.1.md")
    roff = _read(MAN_DIR / "sovereign-osctl.1")
    assert "# MANUAL SUITE" in source
    assert ".SH MANUAL SUITE" in roff
    for topic in TOPICS:
        name = f"sovereign-osctl-{topic}"
        assert f"**{name}**(1)" in source
        assert name in roff


def test_generation_and_installation_cover_the_whole_suite():
    generator = _read(GENERATOR)
    makefile = _read(MAKEFILE)
    assert 'docs/man/sovereign-osctl*.1.md' in generator
    assert "pandoc -s -t man" in generator
    assert "cmp -s" in generator
    assert "make man" in generator
    assert "man:" in makefile and "man-check:" in makefile
    assert "install -m 644 docs/man/sovereign-osctl*.1" in makefile
    assert "sovereign-osctl*.1" in makefile
    assert "Skipping manpage" not in makefile
