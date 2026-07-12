"""mdbook catalog sync lint (F-2026-033 / SDD-958).

The published mdbook (`docs/src/SUMMARY.md`) had hand-curated SDD links that
stopped at SDD-067 — the book trailed the repo by ~90 SDDs (the whole
intelligence layer + the phase-1 audit arc) and had no page for the July
standing-directives. Hand-maintaining a 139-entry table of contents *is* the
living-doc drift the audit warns about.

SDD-958 replaces that with two **generated** catalog pages
(`docs/src/sdd-catalog.md`, `docs/src/standing-directives.md`) produced by
`scripts/docs/gen-sdd-catalog.py` from the file tree. This lint runs that
generator in `--check` mode and fails if either page is stale — so a new SDD or
standing-directive that isn't reflected in the book is caught, and the pages can
only be regenerated, never hand-edited. Same regen-and-compare discipline as the
counts-contract (SDD-952) + island register (SDD-955), applied to the mdbook.

It also verifies every relative link in the catalogs resolves (a broken link
would ship a dead chapter) and that SUMMARY.md wires both catalog pages in.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN = REPO_ROOT / "scripts" / "docs" / "gen-sdd-catalog.py"
SRC = REPO_ROOT / "docs" / "src"
SDD_CATALOG = SRC / "sdd-catalog.md"
DIRECTIVES_PAGE = SRC / "standing-directives.md"
SUMMARY = SRC / "SUMMARY.md"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_gen_sdd_catalog", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generator_script_exists():
    assert GEN.is_file(), f"missing generator {GEN}"


def test_sdd_catalog_is_in_sync_with_the_tree():
    gen = _load_generator()
    expected = gen.render_sdd_catalog()
    actual = SDD_CATALOG.read_text(encoding="utf-8") if SDD_CATALOG.exists() else ""
    assert actual == expected, (
        "docs/src/sdd-catalog.md is out of date with docs/sdd/ — run "
        "`python3 scripts/docs/gen-sdd-catalog.py` (do not hand-edit it). The "
        "mdbook must not freeze behind the SDD record again (F-2026-033)."
    )


def test_standing_directives_page_is_in_sync():
    gen = _load_generator()
    expected = gen.render_directives()
    actual = DIRECTIVES_PAGE.read_text(encoding="utf-8") if DIRECTIVES_PAGE.exists() else ""
    assert actual == expected, (
        "docs/src/standing-directives.md is out of date — run "
        "`python3 scripts/docs/gen-sdd-catalog.py` (do not hand-edit it)."
    )


def test_catalog_covers_the_newest_sdd():
    """Guard: the catalog must reference the highest-numbered SDD in the tree —
    a direct check that it is not frozen (the F-2026-033 failure mode)."""
    nums = sorted(
        int(re.match(r"^(\d{3})-", p.name).group(1))
        for p in (REPO_ROOT / "docs" / "sdd").glob("[0-9][0-9][0-9]-*.md")
    )
    newest = f"{nums[-1]:03d}-"
    body = SDD_CATALOG.read_text(encoding="utf-8")
    assert f"../sdd/{newest}" in body, (
        f"sdd-catalog.md does not reference the newest SDD ({newest}*) — it is frozen"
    )


def test_all_catalog_links_resolve():
    for page in (SDD_CATALOG, DIRECTIVES_PAGE):
        body = page.read_text(encoding="utf-8")
        for rel in re.findall(r"\]\((\.\./[^)]+)\)", body):
            target = (SRC / rel).resolve()
            assert target.exists(), f"{page.name}: broken link → {rel}"


def test_summary_wires_the_catalog_pages():
    body = SUMMARY.read_text(encoding="utf-8")
    for page in ("./sdd-catalog.md", "./standing-directives.md"):
        assert page in body, f"docs/src/SUMMARY.md does not link {page}"
