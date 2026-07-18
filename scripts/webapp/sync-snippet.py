#!/usr/bin/env python3
"""sync-snippet.py — generic canonical-snippet distributor (F-2026-073).

The sibling sync-app-shell.py / sync-course.py / sync-helpers.py each manage ONE
byte-duplicated `webapp/_shared/*` block with the same marker-inject + drift-lint
discipline. F-2026-073 found five MORE `_shared/` snippet families still with no
sync tool and no drift gate — the real drift risk (control-surface.js/css, a11y,
demo-mode.js/css, nav, responsive). Rather than copy the sync script five more
times, this ONE generic tool manages every remaining family from a registry
(FAMILIES below) — the "fix it at the root" form of the same pattern. Adding a
family or an adopter is a registry edit, not a new script.

Per the sovereignty-clean doctrine there is no shared runtime asset: the marked
block is DUPLICATED verbatim into each adopted panel and enforced identical by
tests/lint/test_shared_snippets_contract.py.

Snippet types:
  * html — the canonical file already carries its own <style>/<script> wrapper
           (a11y, nav, responsive). Injected verbatim before </head>.
  * js   — raw JS; injected wrapped in <script> … </script> before </head>.
  * css  — raw CSS; injected wrapped in <style> … </style> before </head>.
In every case the BEGIN/END markers live INSIDE any wrapper, so a re-sync
replaces just the marker span and leaves the wrapper intact (idempotent).

Adoption is opt-in per family: only panels in a family's `adopted` list are
touched — everything else is left exactly as-is (adoption grows one-at-a-time,
exactly as sync-helpers.py rolled out).

Mutation discipline (mirrors the siblings):
  * DRY-RUN by default — prints WOULD; requires --apply to write.
  * Reports WOULD/DID/SKIP <path>: <reason> per panel.
  * --check verifies every adopted panel's block matches canonical
    (exit 1 on drift) and writes nothing.

Usage:
  python3 scripts/webapp/sync-snippet.py                      # dry-run, all families
  python3 scripts/webapp/sync-snippet.py --family a11y --apply
  python3 scripts/webapp/sync-snippet.py --check              # CI drift gate
  python3 scripts/webapp/sync-snippet.py --list               # show the registry
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"
SHARED = WEBAPP / "_shared"

# Panels currently missing the WCAG 2.4.1 skip-link (F-2026-074). These are the
# a11y family's first adopters: injecting the marked canonical a11y block gives
# them the skip-link + focus-visible ring + reduced-motion guard, and folds them
# under the drift gate so it can never silently drift again. The block's JS is
# idempotent (returns if a .so-skip-link already exists), so adoption is safe.
_A11Y_BACKPORT = [
    "avx-modes", "brain", "build-configurator", "code-console", "course",
    "cpu-features", "d-21-lm-orchestration", "d-22-lm-status-operability",
    "d-23-models-catalog", "d-24-cpu-features", "d-25-selfdef-management",
    "emulate", "feature-test-lab", "flash", "models-catalog", "orchestration",
    "profile-generation", "runtime-modes", "science", "selfdef-management",
    "ups", "warp",
]

# family → {file, type, begin, end, adopted}
#
# Registry note (F-2026-073, empirically grounded 2026-07-17): the five families
# the finding named split by how their duplication is actually gated —
#   * control-surface.js/css — inlined byte-identical in 61/61 panels and ALREADY
#     drift-gated by tests/lint/test_control_surface_component.py. No marker sync
#     needed; adding markers would break that verbatim lockstep.
#   * demo-mode.js/css — opt-in, inlined byte-identical where present; gated
#     verbatim (no markers) by tests/lint/test_shared_snippets_contract.py.
#   * nav / responsive — the canonical _shared file is NOT the byte-source of what
#     panels carry (0/61 verbatim match); they are genuinely divergent and need a
#     real reconciliation pass, not a mechanical gate (tracked as remaining).
#   * a11y — the one family that needed distribution: 22 panels were missing the
#     skip-link entirely (F-2026-074). This tool injects the MARKED canonical a11y
#     block into them and folds them under the drift gate. Marker-managed here.
# So this marker-injection tool registers a11y today; adoption grows one-at-a-time
# (the sync-helpers.py rollout precedent) — adding a family/adopter is a registry
# edit, never a blind mass-rewrite of drifted panels.
FAMILIES: dict[str, dict] = {
    "a11y": {
        "file": "a11y-snippet.html", "type": "html",
        "begin": "<!-- A11Y:BEGIN M060 -->", "end": "<!-- A11Y:END M060 -->",
        "adopted": list(_A11Y_BACKPORT),
    },
}

_ENDHEAD_RE = re.compile(r"^[ \t]*</head\s*>", re.IGNORECASE | re.MULTILINE)


def _canonical_block(fam: dict) -> str:
    src = (SHARED / fam["file"]).read_text(encoding="utf-8")
    i, j = src.find(fam["begin"]), src.find(fam["end"])
    if i < 0 or j < 0:
        sys.exit(f"FATAL: markers not found in {fam['file']}")
    return src[i:j + len(fam["end"])]


def _wrapped(fam: dict, block: str) -> str:
    """The exact text injected into a panel — the marked block inside its
    wrapper (js→<script>, css→<style>, html→bare)."""
    if fam["type"] == "js":
        return "<script>\n" + block + "\n</script>"
    if fam["type"] == "css":
        return "<style>\n" + block + "\n</style>"
    return block


def _block_re(fam: dict) -> re.Pattern:
    return re.compile(re.escape(fam["begin"]) + r".*?" + re.escape(fam["end"]), re.DOTALL)


def _panel_path(slug: str) -> Path:
    return WEBAPP / slug / "index.html"


def render(html: str, fam: dict, block: str) -> tuple[str, str]:
    """Return (new_html, action). action ∈ replace|insert|unchanged|no-head.
    Replace substitutes just the marker span (wrapper preserved); insert adds
    the wrapped block before </head>."""
    bre = _block_re(fam)
    if bre.search(html):
        new = bre.sub(lambda _m: block, html, count=1)
        return new, ("unchanged" if new == html else "replace")
    m = _ENDHEAD_RE.search(html)
    if not m:
        return html, "no-head"
    at = m.start()
    new = html[:at] + _wrapped(fam, block) + "\n" + html[at:]
    return new, "insert"


def _process(fam_name: str, fam: dict, apply: bool, check: bool) -> tuple[list[str], int]:
    block = _canonical_block(fam)
    drift: list[str] = []
    changed = 0
    for slug in fam["adopted"]:
        path = _panel_path(slug)
        if not path.is_file():
            print(f"SKIP {fam_name}/{slug}: index.html not found")
            continue
        html = path.read_text(encoding="utf-8")
        if check:
            found = _block_re(fam).search(html)
            if not found:
                print(f"DRIFT {fam_name}/{slug}: no block")
                drift.append(slug)
            elif found.group(0) != block:
                print(f"DRIFT {fam_name}/{slug}: block differs from canonical")
                drift.append(slug)
            else:
                print(f"OK    {fam_name}/{slug}")
            continue
        new, action = render(html, fam, block)
        if action == "no-head":
            print(f"SKIP {fam_name}/{slug}: no </head> tag")
            continue
        if action == "unchanged":
            print(f"SKIP {fam_name}/{slug}: already current")
            continue
        changed += 1
        if apply:
            path.write_text(new, encoding="utf-8")
            print(f"DID  {action} {fam_name}/{path.relative_to(REPO_ROOT)}")
        else:
            print(f"WOULD {action} {fam_name}/{path.relative_to(REPO_ROOT)}")
    return drift, changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync canonical _shared snippet families into adopted cockpit panels.")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--family", action="append", default=None,
                    help="family name (repeatable); default = all families")
    ap.add_argument("--check", action="store_true", help="verify blocks match canonical; write nothing; exit 1 on drift")
    ap.add_argument("--list", action="store_true", help="show the family registry and exit")
    args = ap.parse_args()

    if args.list:
        for name, fam in FAMILIES.items():
            print(f"{name:22s} {fam['type']:4s} {fam['file']:24s} "
                  f"adopted={len(fam['adopted'])}")
        return 0

    names = args.family if args.family else list(FAMILIES)
    unknown = [n for n in names if n not in FAMILIES]
    if unknown:
        print(f"unknown family: {unknown}; known: {list(FAMILIES)}", file=sys.stderr)
        return 2

    all_drift, total_changed = [], 0
    for name in names:
        fam = FAMILIES[name]
        drift, changed = _process(name, fam, args.apply, args.check)
        all_drift += [f"{name}/{s}" for s in drift]
        total_changed += changed

    if args.check:
        if all_drift:
            print(f"\n{len(all_drift)} panel(s) drifted from canonical — run: "
                  f"python3 scripts/webapp/sync-snippet.py --apply")
            return 1
        print("\nall adopted panels current.")
        return 0

    if not args.apply and total_changed:
        print(f"\n{total_changed} panel(s) WOULD change — re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
