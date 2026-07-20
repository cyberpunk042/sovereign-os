#!/usr/bin/env python3
"""sync-a11y.py — canonical a11y snippet distributor (sibling of sync-app-shell.py).

Injects the canonical a11y block (webapp/_shared/a11y-snippet.html, between the
A11Y:BEGIN / A11Y:END markers, inclusive) into each adopted panel's <head> so
a11y helpers are defined before any panel-specific <script> runs.

Idempotent: a panel that already carries a block gets it REPLACED, so re-running
is a no-op when nothing changed. Per the sovereignty-clean doctrine there is no
shared runtime asset — the block is DUPLICATED verbatim into every adopted panel
and enforced identical by tests/lint/test_a11y_contract.py.

Adoption is opt-in: only panels in ADOPTED_PANELS are touched — the rest stay
exactly as they are.

Mutation discipline (mirrors sync-app-shell.py):
  * DRY-RUN by default — prints WOULD; requires --apply to write.
  * Reports WOULD/DID/SKIP <path>: <reason> per panel.
  * --check verifies every adopted panel's block matches canonical
    (exit 1 on drift) and writes nothing.

Usage:
  python3 scripts/webapp/sync-a11y.py                 # dry-run over the adopted list
  python3 scripts/webapp/sync-a11y.py --apply         # write the adopted list
  python3 scripts/webapp/sync-a11y.py --panel brain --apply
  python3 scripts/webapp/sync-a11y.py --check         # CI-style drift check
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"
SNIPPET = WEBAPP / "_shared" / "a11y-snippet.html"

BEGIN = "<!-- A11Y:BEGIN M060 -->"
END = "<!-- A11Y:END M060 -->"

# Opt-in adoption list — grow this list one (or a few) at a time; only listed
# panels are touched. Each adopted panel MUST remove any local a11y definitions
# so the canonical block is the single source.
ADOPTED_PANELS: list[str] = [
    "anti-minimization-audit",
    "auditor",
    "auth-tier",
    "brain",
    "compliance",
]

_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
# Inject just before </head> so a11y is defined before any panel script runs.
_ENDHEAD_RE = re.compile(r"^[ \t]*</head\s*>", re.IGNORECASE | re.MULTILINE)


def canonical_block() -> str:
    src = SNIPPET.read_text(encoding="utf-8")
    i, j = src.find(BEGIN), src.find(END)
    if i < 0 or j < 0:
        sys.exit(f"FATAL: markers not found in {SNIPPET}")
    block = src[i : j + len(END)]
    # Strip a single trailing newline so insertion semantics are consistent
    # regardless of whether the canonical file ends with one.
    if block.endswith("\n"):
        block = block[:-1]
    return block


def _panel_path(slug: str) -> Path:
    return WEBAPP / slug / "index.html"


def render(html: str, block: str) -> tuple[str, str]:
    """Return (new_html, action). action ∈ replace|insert|unchanged|no-head."""
    if _BLOCK_RE.search(html):
        new = _BLOCK_RE.sub(lambda _m: block, html, count=1)
        return new, ("unchanged" if new == html else "replace")
    m = _ENDHEAD_RE.search(html)
    if not m:
        return html, "no-head"
    at = m.start()
    new = html[:at] + block + "\n" + html[at:]
    return new, "insert"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Canonical a11y snippet distributor")
    p.add_argument("--apply", action="store_true", help="write files (default: dry-run)")
    p.add_argument("--check", action="store_true", help="exit 1 on drift, write nothing")
    p.add_argument("--panel", help="target a single panel slug")
    args = p.parse_args(argv)

    block = canonical_block()
    slugs = [args.panel] if args.panel else ADOPTED_PANELS
    if not slugs:
        print("No panels adopted yet. Add slugs to ADOPTED_PANELS.")
        return 0

    exit_code = 0
    for slug in slugs:
        path = _panel_path(slug)
        if not path.is_file():
            print(f"SKIP    {slug}: panel not found")
            continue
        html = path.read_text(encoding="utf-8")
        new_html, action = render(html, block)
        if action == "no-head":
            print(f"SKIP    {slug}: no </head> anchor")
            continue
        if action == "unchanged":
            if args.check:
                print(f"OK      {slug}")
            continue
        if args.check:
            print(f"DRIFT   {slug}: would {action}")
            exit_code = 1
            continue
        verb = "DID" if args.apply else "WOULD"
        print(f"{verb}    {slug}: {action}")
        if args.apply:
            path.write_text(new_html, encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
