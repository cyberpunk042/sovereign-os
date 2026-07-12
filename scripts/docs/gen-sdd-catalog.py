#!/usr/bin/env python3
"""Generate the mdbook SDD catalog + standing-directives pages from the source
tree, so the published book can never freeze behind the design record again
(F-2026-033 / SDD-958).

`docs/src/SUMMARY.md` had hand-curated links to a handful of SDDs and stopped
being updated at SDD-067 — the published mdbook trailed the repo by ~90 SDDs
(the whole intelligence layer + the phase-1 audit arc) and had no page for the
July standing-directives. Hand-maintaining a 139-entry table of contents is
exactly the drift the audit warns about, so this generates two catalog pages
from the file tree instead:

  docs/src/sdd-catalog.md          — every docs/sdd/NNN-*.md, by number
  docs/src/standing-directives.md  — every docs/standing-directives/*.md, by date

Run it after adding an SDD or a standing-directive:

    python3 scripts/docs/gen-sdd-catalog.py

`tests/lint/test_mdbook_catalog_sync.py` re-runs this generator and fails CI if
either page differs — so a new SDD/directive that isn't reflected in the book is
caught, and the pages are always regenerated (never hand-edited).

Stdlib only (re + pathlib); no mdbook dependency (the pages are plain Markdown
that `mdbook build` renders as chapters).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_DIR = REPO_ROOT / "docs" / "sdd"
DIRECTIVES_DIR = REPO_ROOT / "docs" / "standing-directives"
SRC = REPO_ROOT / "docs" / "src"
SDD_CATALOG = SRC / "sdd-catalog.md"
DIRECTIVES_PAGE = SRC / "standing-directives.md"

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)


def _title(md_path: Path) -> str:
    """The page's H1, trimmed. Falls back to the filename stem."""
    m = _H1.search(md_path.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else md_path.stem


def _sdd_number(name: str) -> int | None:
    m = re.match(r"^(\d{3})-", name)
    return int(m.group(1)) if m else None


def render_sdd_catalog() -> str:
    rows = []
    for p in sorted(SDD_DIR.glob("[0-9][0-9][0-9]-*.md")):
        n = _sdd_number(p.name)
        if n is None:
            continue
        title = _title(p)
        # H1s are "SDD-NNN — <title>"; keep the H1 verbatim as the link text so
        # the catalog reads the same as the doc it points at.
        rows.append(f"- [{title}](../sdd/{p.name})")
    lines = [
        "# SDD catalog",
        "",
        "> **Generated — do not hand-edit.** Run `python3 scripts/docs/gen-sdd-catalog.py`",
        "> after adding an SDD. `tests/lint/test_mdbook_catalog_sync.py` fails CI if this",
        "> page drifts from `docs/sdd/`, so the published book can never freeze behind the",
        "> design record again (F-2026-033).",
        "",
        f"Every Spec-Driven-Development design doc in `docs/sdd/` ({len(rows)} total), by number.",
        "",
        *rows,
        "",
    ]
    return "\n".join(lines)


def render_directives() -> str:
    rows = []
    for p in sorted(DIRECTIVES_DIR.glob("*.md")):
        if p.name.upper() in {"INDEX.MD", "README.MD"}:
            continue
        rows.append(f"- [{_title(p)}](../standing-directives/{p.name})")
    lines = [
        "# Standing directives",
        "",
        "> **Generated — do not hand-edit.** Run `python3 scripts/docs/gen-sdd-catalog.py`",
        "> after adding a standing-directive. Enforced by",
        "> `tests/lint/test_mdbook_catalog_sync.py` (F-2026-033).",
        "",
        "Operator standing-directives (verbatim mandate records), newest by date last.",
        "",
        *rows,
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    check = "--check" in sys.argv[1:]
    targets = [(SDD_CATALOG, render_sdd_catalog()), (DIRECTIVES_PAGE, render_directives())]
    drift = False
    for path, content in targets:
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        drift = True
        if check:
            print(f"OUT OF DATE: {path.relative_to(REPO_ROOT)} — run scripts/docs/gen-sdd-catalog.py")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
    if check and drift:
        return 1
    if not check and not drift:
        print("catalogs already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
