"""Island register lint (F-2026-093 / SDD-955).

The audit's dominant theme is *built-but-unwired islands*. The sharpest,
objective signal is a **pure-library `sovereign-*` crate** (`src/lib.rs`, no
`main.rs` / `src/bin/`) that appears in **no other crate's `Cargo.toml`** — it
is depended on by nothing, not even a demo or a test.

This lint computes that set from the workspace and asserts it matches the
enforced register in `docs/review/phase-1/island-register.md` — **both
directions**:

  - a NEW pure-library crate with zero consumers fails CI until it is registered
    (wire it, or record its disposition + trigger);
  - WIRING an island (giving it a real consumer) fails CI until its row is
    removed from the register.

So the "built-but-unwired surprise" becomes an owned register that can only
drift toward "everything is either wired or consciously parked". Same
counts-as-contract discipline as `test_context_md_counts.py`.

Scope excludes `sovereign-cockpit-*` (418 leaf UI widgets — a known family
consumed by the webapp, not by other crates) and binaries (a binary having no
reverse-dep is expected, not an island signal).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATES = REPO_ROOT / "crates"
REGISTER = REPO_ROOT / "docs" / "review" / "phase-1" / "island-register.md"

_VALID_DISPOSITIONS = {"wireable", "aspirational"}


def _crate_manifests() -> dict[str, Path]:
    """name -> crate directory, for every crate with a [package] name."""
    out: dict[str, Path] = {}
    for cargo in CRATES.glob("*/Cargo.toml"):
        m = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', cargo.read_text(encoding="utf-8"))
        if m:
            out[m.group(1)] = cargo.parent
    return out


def _computed_islands() -> set[str]:
    """Pure-library `sovereign-*` crates (not cockpit, not a binary) that no
    other crate's Cargo.toml references in any dependency section."""
    dirs = _crate_manifests()
    texts = {n: (d / "Cargo.toml").read_text(encoding="utf-8") for n, d in dirs.items()}

    def has_reverse_dep(target: str) -> bool:
        # a dependency entry begins the line with the crate name (`name = ...`
        # or `name.workspace = true` or `name = { path = ... }`)
        pat = re.compile(r"(?m)^\s*" + re.escape(target) + r"\b")
        return any(n != target and pat.search(t) for n, t in texts.items())

    def is_pure_lib(name: str) -> bool:
        d = dirs[name]
        return (
            (d / "src" / "lib.rs").exists()
            and not (d / "src" / "main.rs").exists()
            and not (d / "src" / "bin").exists()
        )

    return {
        n
        for n in dirs
        if n.startswith("sovereign-")
        and not n.startswith("sovereign-cockpit-")
        and is_pure_lib(n)
        and not has_reverse_dep(n)
    }


def _register_rows() -> list[tuple[str, str]]:
    """(crate, disposition) rows parsed from the ISLAND-REGISTER block."""
    body = REGISTER.read_text(encoding="utf-8")
    block = re.search(
        r"<!-- ISLAND-REGISTER:.*?-->(.*?)<!-- END ISLAND-REGISTER -->",
        body,
        re.S,
    )
    assert block, (
        f"{REGISTER} is missing its <!-- ISLAND-REGISTER ... --> ... "
        f"<!-- END ISLAND-REGISTER --> block"
    )
    rows: list[tuple[str, str]] = []
    for line in block.group(1).splitlines():
        m = re.match(r"^\|\s*(sovereign-[a-z0-9-]+)\s*\|\s*([a-z]+)\s*\|", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


def test_register_has_a_parseable_block():
    rows = _register_rows()
    assert rows, "the ISLAND-REGISTER block has no crate rows"


def test_every_register_row_declares_a_valid_disposition():
    for crate, disp in _register_rows():
        assert disp in _VALID_DISPOSITIONS, (
            f"{crate}: disposition {disp!r} must be one of {sorted(_VALID_DISPOSITIONS)}"
        )


def test_register_matches_the_computed_islands_both_directions():
    computed = _computed_islands()
    registered = {c for c, _ in _register_rows()}

    unregistered = sorted(computed - registered)
    assert not unregistered, (
        f"pure-library crates with ZERO reverse-dependencies that are NOT in the "
        f"island register: {unregistered}. Wire one (add a real consumer) or add a "
        f"row to docs/review/phase-1/island-register.md with a disposition "
        f"(wireable|aspirational) + a trigger."
    )

    stale = sorted(registered - computed)
    assert not stale, (
        f"island register rows for crates that now HAVE a consumer (or are no "
        f"longer a pure library): {stale}. If you wired them, delete their rows "
        f"from docs/review/phase-1/island-register.md."
    )


def test_no_duplicate_register_rows():
    crates = [c for c, _ in _register_rows()]
    dupes = sorted({c for c in crates if crates.count(c) > 1})
    assert not dupes, f"duplicate island-register rows: {dupes}"
