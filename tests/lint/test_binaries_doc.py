"""Runtime-binaries doc completeness lint (F-2026-005 / SDD-962).

The 9 Rust binary crates (`crates/*/src/main.rs`) are the executable runtime
surface. `docs/src/binaries.md` documents each — role, invocation, purpose. This
lint keeps that doc complete: every crate that produces a binary must appear, and
the doc must not name a binary that no longer exists. So a new binary can't ship
undocumented, and the runtime-surface map can't silently drift.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATES = REPO_ROOT / "crates"
BINARIES_DOC = REPO_ROOT / "docs" / "src" / "binaries.md"
SUMMARY = REPO_ROOT / "docs" / "src" / "SUMMARY.md"


def _binary_crates() -> set[str]:
    """Crates that produce a binary (have src/main.rs or a src/bin/ dir)."""
    out: set[str] = set()
    for cargo in CRATES.glob("*/Cargo.toml"):
        d = cargo.parent
        if (d / "src" / "main.rs").exists() or (d / "src" / "bin").is_dir():
            m = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', cargo.read_text(encoding="utf-8"))
            if m:
                out.add(m.group(1))
    return out


def _documented() -> set[str]:
    body = BINARIES_DOC.read_text(encoding="utf-8")
    return set(re.findall(r"`(sovereign-[a-z0-9-]+)`", body))


def test_binaries_doc_exists_and_is_linked():
    assert BINARIES_DOC.is_file(), f"missing {BINARIES_DOC}"
    assert "./binaries.md" in SUMMARY.read_text(encoding="utf-8"), (
        "docs/src/SUMMARY.md does not link ./binaries.md"
    )


def test_every_binary_crate_is_documented():
    missing = sorted(_binary_crates() - _documented())
    assert not missing, (
        f"binary crates (crates/*/src/main.rs) not documented in "
        f"docs/src/binaries.md: {missing}. Add a row for each — role, invocation, "
        f"purpose (the runtime surface must be complete: F-2026-005)."
    )


def test_binaries_doc_names_no_nonexistent_binary():
    # Any `sovereign-*` in a table row that looks like a binary but isn't one.
    bins = _binary_crates()
    # crates that exist at all (library or binary) — used to spot a truly-dead name
    all_crates = {
        m.group(1)
        for cargo in CRATES.glob("*/Cargo.toml")
        if (m := re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', cargo.read_text(encoding="utf-8")))
    }
    # A documented sovereign-* that is neither a binary nor even a crate is stale.
    ghosts = sorted(n for n in _documented() if n not in all_crates)
    assert not ghosts, (
        f"docs/src/binaries.md references crates that do not exist: {ghosts}"
    )
    # Sanity: the doc should center on the actual binaries (all present).
    assert bins <= _documented(), "not all binary crates are documented"
