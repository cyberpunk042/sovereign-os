"""Contracts for the sovereign-osctl(1) manual-page suite."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "sovereign-osctl"
VERSION_FILE = ROOT / "VERSION"
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
    assert 'VERSION_FILE="${ROOT}/VERSION"' in generator
    assert "make man" in generator
    assert "man:" in makefile and "man-check:" in makefile
    assert "install -m 644 docs/man/sovereign-osctl*.1" in makefile
    assert 'install -m 644 VERSION "$(DESTDIR)$(SOVEREIGN_OS_LIB)/VERSION"' in makefile
    assert "sovereign-osctl*.1" in makefile
    assert "Skipping manpage" not in makefile

def _canonical_version() -> str:
    version = _read(VERSION_FILE).strip()
    assert re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
        version,
    ), f"VERSION is not a supported SemVer value: {version!r}"
    return version


def test_operator_runtime_uses_the_canonical_version_file():
    body = _read(CLI)
    assert 'local sovereign_version="' not in body
    assert 'sovereign_version="$(_sovereign_os_version)"' in body
    assert '"${__REPO_ROOT}/VERSION"' in body
    assert "SOVEREIGN_OS_VERSION_FILE" in body


def test_manual_headers_match_the_canonical_version():
    version = _canonical_version()
    for source in sorted(MAN_DIR.glob("sovereign-osctl*.1.md")):
        first_line = _read(source).splitlines()[0]
        assert f"sovereign-os {version} |" in first_line, (
            f"{source.name} version drift: VERSION is {version!r}, header is {first_line!r}"
        )


def test_critical_runtime_facts_are_not_inherited_from_stale_help():
    cli = _read(CLI)
    install = _read(MAN_DIR / "sovereign-osctl-install.1.md")
    models = _read(MAN_DIR / "sovereign-osctl-models.1.md")

    help_text = cli.split("cmd_help() {", 1)[1].split("\nEOF", 1)[0]
    assert "walk through 6 decisions" in help_text
    assert "walk through 5 decisions" not in help_text
    assert "models list                  List resident models (/mnt/vault/models by default)" in help_text
    assert "decommission pool" in help_text
    assert "decommission wipe" in help_text

    init_handler = cli.split("cmd_init() {", 1)[1].split("\n}", 1)[0]
    assert "Walks you through 6 decisions" in init_handler
    assert "six decisions" in install
    assert "5 decisions" not in install

    decommission_handler = cli.split("cmd_decommission() {", 1)[1].split(
        "# ------------------------------ inference", 1
    )[0]
    expected_decommission = {
        "--plan|plan": "decommission {--plan|plan}",
        "start": "decommission start",
        "pool": "decommission pool",
        "wipe": "decommission wipe",
    }
    for handler_token, manual_form in expected_decommission.items():
        assert handler_token in decommission_handler
        assert manual_form in install

    assert 'SOVEREIGN_OS_MODELS_DIR:=/mnt/vault/models' in cli
    assert "The default resident-model directory is `/mnt/vault/models`" in models
    assert "tank/models" not in models


def test_manual_does_not_claim_top_level_help_is_exhaustive():
    forbidden = (
        "complete version-matched syntax of every subcommand",
        "help remains authoritative",
        "Run `sovereign-osctl help` for the complete version-matched grammar",
    )
    for source in sorted(MAN_DIR.glob("sovereign-osctl*.1.md")):
        body = _read(source)
        for phrase in forbidden:
            assert phrase not in body, f"{source.name} contains stale claim: {phrase}"
