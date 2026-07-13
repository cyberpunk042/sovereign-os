"""Exotic-tool-domains discoverability completeness (F-2026-027 / SDD-973).

Six `scripts/<domain>/` trees each hold a lone specialist entry point (science /
research / insights / history / weaver / pulse) — real operator capabilities that
had no doc, no index, no discoverability surface. SDD-973 added
`docs/src/exotic-tools.md` mapping each to its role + invocation. This lint keeps
that index complete: every top-level script in those domains must appear in the page,
and SUMMARY must link it — so a new exotic-domain capability can't ship undiscoverable.

Scope: top-level scripts only (a domain's `lib/` / `sample/` helpers are not entry
points and are excluded).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
DOC = REPO_ROOT / "docs" / "src" / "exotic-tools.md"
SUMMARY = REPO_ROOT / "docs" / "src" / "SUMMARY.md"

EXOTIC_DOMAINS = ("science", "research", "insights", "history", "weaver", "pulse")


def _domain_scripts() -> list[str]:
    """Top-level *.py / *.sh under each exotic domain, as repo-relative paths."""
    out: list[str] = []
    for domain in EXOTIC_DOMAINS:
        d = SCRIPTS / domain
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix in (".py", ".sh"):
                out.append(str(p.relative_to(REPO_ROOT)))
    return out


def test_doc_and_link_exist():
    assert DOC.is_file(), f"missing {DOC} (SDD-973)"
    assert "./exotic-tools.md" in SUMMARY.read_text(encoding="utf-8"), (
        "docs/src/SUMMARY.md does not link ./exotic-tools.md"
    )


def test_every_exotic_script_is_documented():
    body = DOC.read_text(encoding="utf-8")
    missing = [s for s in _domain_scripts() if s not in body]
    assert not missing, (
        "these exotic-domain scripts are not documented in docs/src/exotic-tools.md "
        f"(a lone-entry-point capability can't ship undiscoverable): {missing}"
    )


def test_no_ghost_scripts_documented():
    """The doc must not reference an exotic-domain script path that no longer exists."""
    import re

    body = DOC.read_text(encoding="utf-8")
    referenced = re.findall(r"scripts/(?:%s)/[A-Za-z0-9_./-]+\.(?:py|sh)" % "|".join(EXOTIC_DOMAINS), body)
    ghosts = sorted({r for r in referenced if not (REPO_ROOT / r).is_file()})
    assert not ghosts, f"exotic-tools.md references scripts that don't exist: {ghosts}"
