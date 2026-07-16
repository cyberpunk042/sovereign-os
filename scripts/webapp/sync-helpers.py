#!/usr/bin/env python3
"""sync-helpers.py — canonical helper distributor (sibling of sync-app-shell.py).

Injects the canonical helpers block (webapp/_shared/helpers.js, between the
HELPERS:BEGIN / HELPERS:END markers, inclusive) into each adopted panel's
<head> so the helpers are defined before any panel-specific <script> runs.

Idempotent: a panel that already carries a block gets it REPLACED, so re-running
is a no-op when nothing changed. Per the sovereignty-clean doctrine there is no
shared runtime asset — the block is DUPLICATED verbatim into every adopted panel
and enforced identical by tests/lint/test_helpers_contract.py.

Adoption is opt-in: only panels in ADOPTED_PANELS are touched — the rest stay
exactly as they are. Panels on the adoption list MUST remove their local
esc()/fmtBytes()/fmtNum() definitions so the canonical block is the sole source.

Mutation discipline (mirrors sync-app-shell.py):
  * DRY-RUN by default — prints WOULD; requires --apply to write.
  * Reports WOULD/DID/SKIP <path>: <reason> per panel.
  * --check verifies every adopted panel's block matches canonical
    (exit 1 on drift) and writes nothing.

Usage:
  python3 scripts/webapp/sync-helpers.py                 # dry-run over the adopted list
  python3 scripts/webapp/sync-helpers.py --apply         # write the adopted list
  python3 scripts/webapp/sync-helpers.py --panel d-04-costs --apply
  python3 scripts/webapp/sync-helpers.py --check         # CI-style drift check
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"
SNIPPET = WEBAPP / "_shared" / "helpers.js"

BEGIN = "/* HELPERS:BEGIN M073"
END = "/* HELPERS:END M073 */"

# Opt-in adoption list — grow this list one (or a few) at a time; only listed
# panels are touched. Each adopted panel MUST remove its local definitions of
# esc(), fmtBytes(), fmtNum() so the canonical block is the single source.
ADOPTED_PANELS = [
]

_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
# Inject just before </head> so helpers are defined before any panel script runs.
_ENDHEAD_RE = re.compile(r"^[ \t]*</head\s*>", re.IGNORECASE | re.MULTILINE)


def canonical_block() -> str:
    src = SNIPPET.read_text(encoding="utf-8")
    i, j = src.find(BEGIN), src.find(END)
    if i < 0 or j < 0:
        sys.exit(f"FATAL: markers not found in {SNIPPET}")
    return src[i : j + len(END)]


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync the canonical helpers block into adopted cockpit panels.")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--panel", action="append", default=None, help="panel slug (repeatable); default = the adopted list")
    ap.add_argument("--all", action="store_true", help="operate over the full adopted list")
    ap.add_argument("--check", action="store_true", help="verify blocks match canonical; write nothing; exit 1 on drift")
    args = ap.parse_args()

    block = canonical_block()
    targets = args.panel if args.panel else ADOPTED_PANELS

    drift, changed = [], 0
    for slug in targets:
        path = _panel_path(slug)
        if not path.is_file():
            print(f"SKIP {slug}: index.html not found")
            continue
        html = path.read_text(encoding="utf-8")

        if args.check:
            found = _BLOCK_RE.search(html)
            if not found:
                print(f"DRIFT {slug}: no helpers block")
                drift.append(slug)
            elif found.group(0) != block:
                print(f"DRIFT {slug}: block differs from canonical")
                drift.append(slug)
            else:
                print(f"OK    {slug}")
            continue

        new, action = render(html, block)
        if action == "no-head":
            print(f"SKIP {slug}: no </head> tag")
            continue
        if action == "unchanged":
            print(f"SKIP {slug}: already current")
            continue
        changed += 1
        if args.apply:
            path.write_text(new, encoding="utf-8")
            print(f"DID  {action} {path.relative_to(REPO_ROOT)}")
        else:
            print(f"WOULD {action} {path.relative_to(REPO_ROOT)}")

    if args.check:
        if drift:
            print(f"\n{len(drift)} panel(s) drifted from canonical — run: python3 scripts/webapp/sync-helpers.py --apply")
            return 1
        print("\nall adopted panels current.")
        return 0

    if not args.apply and changed:
        print(f"\n{changed} panel(s) WOULD change — re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
