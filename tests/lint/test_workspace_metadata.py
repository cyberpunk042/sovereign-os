"""Workspace metadata + dead-doc-link lint (F-2026-003 / SDD-960).

The root `Cargo.toml` `[workspace.package]` carried template placeholders —
`repository = "https://example.org/you/sovereign-os"` and
`authors = ["You <you@example.org>"]` — inherited by all 714 crates via
`repository.workspace = true` / `authors.workspace = true`. Separately, 23 crate
`lib.rs` headers linked `https://docs.rs/sovereign-*`, which can never resolve:
the workspace is `publish = false`, so nothing is on docs.rs.

This lint keeps both fixed:
  1. the root workspace metadata has no template-placeholder values;
  2. no crate `src/lib.rs` links `docs.rs/sovereign-*` (a dead link under
     `publish = false`) — the sweep repointed them to the GitHub source, and
     this stops a reintroduction.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_CARGO = REPO_ROOT / "Cargo.toml"
CRATES = REPO_ROOT / "crates"

_PLACEHOLDERS = ("example.org", "you@example", "You <you@", "<you@")


def _workspace_package() -> str:
    body = ROOT_CARGO.read_text(encoding="utf-8")
    m = re.search(r"\[workspace\.package\](.*?)(?:\n\[|\Z)", body, re.S)
    assert m, "root Cargo.toml has no [workspace.package] section"
    return m.group(1)


def test_root_cargo_has_no_placeholder_metadata():
    section = _workspace_package()
    hits = [p for p in _PLACEHOLDERS if p in section]
    assert not hits, (
        f"root Cargo.toml [workspace.package] still has template placeholders "
        f"{hits} — set the real repository / authors (inherited by all crates)"
    )


def test_root_repository_is_a_real_url():
    section = _workspace_package()
    m = re.search(r'(?m)^\s*repository\s*=\s*"([^"]+)"', section)
    assert m, "[workspace.package] has no repository field"
    url = m.group(1)
    assert url.startswith("https://") and "example.org" not in url, (
        f"workspace repository is not a real URL: {url!r}"
    )


def test_root_authors_are_not_placeholder():
    section = _workspace_package()
    m = re.search(r"(?m)^\s*authors\s*=\s*\[(.*?)\]", section, re.S)
    assert m, "[workspace.package] has no authors field"
    authors = m.group(1)
    assert "You <" not in authors and "you@example" not in authors, (
        f"workspace authors are still placeholder: {authors.strip()!r}"
    )


def test_no_crate_links_dead_docs_rs():
    offenders = []
    for lib in CRATES.glob("*/src/lib.rs"):
        if "docs.rs/sovereign" in lib.read_text(encoding="utf-8"):
            offenders.append(lib.relative_to(REPO_ROOT).as_posix())
    assert not offenders, (
        f"crate lib.rs files link docs.rs/sovereign-* — a dead link under "
        f"`publish = false` (nothing is published to docs.rs). Point to the "
        f"GitHub source instead. Offenders: {offenders}"
    )
