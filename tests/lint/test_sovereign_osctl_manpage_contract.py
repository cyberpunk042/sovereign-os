"""Contract for the installed sovereign-osctl(1) manual page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANPAGE = ROOT / "docs" / "man" / "sovereign-osctl.1"
MAKEFILE = ROOT / "Makefile"

CORE_SECTIONS = (
    ".SH NAME",
    ".SH SYNOPSIS",
    ".SH DESCRIPTION",
    ".SH CORE COMMANDS",
    ".SH SECURITY AND AUDIT",
    ".SH ENVIRONMENT",
    ".SH FILES",
    ".SH EXAMPLES",
    ".SH EXIT STATUS",
    ".SH SEE ALSO",
)

CORE_COMMANDS = (
    "status",
    "doctor",
    "profiles",
    "models",
    "audit",
    "maintenance",
    "install",
    "decommission",
    "trinity",
    "env",
)


def _manpage() -> str:
    assert MANPAGE.is_file(), "missing docs/man/sovereign-osctl.1"
    return MANPAGE.read_text(encoding="utf-8")


def test_manpage_is_native_section_one_roff():
    body = _manpage()
    assert body.startswith(".TH SOVEREIGN-OSCTL 1 ")
    for section in CORE_SECTIONS:
        assert section in body, f"man page missing {section}"


def test_manpage_keeps_core_operator_commands_discoverable():
    body = _manpage()
    for command in CORE_COMMANDS:
        assert f".B {command}" in body or f".B sovereign-osctl {command}" in body, (
            f"man page missing core command {command!r}"
        )


def test_make_install_always_installs_committed_manpage():
    body = MAKEFILE.read_text(encoding="utf-8")
    expected = (
        'install -m 644 docs/man/sovereign-osctl.1 '
        '"$(DESTDIR)$(PREFIX)/share/man/man1/sovereign-osctl.1"'
    )
    assert expected in body
    assert "Skipping manpage" not in body
