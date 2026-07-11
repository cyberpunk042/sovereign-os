"""Single status-color token vocabulary (SDD-144).

The cockpit had two rival status-color vocabularies: `--good/--bad/--warn` (the
de-facto canonical — enforced by test_dashboard_palette_consistency.py + the
d-21/23/24/25 contracts + the SDD-040 bridge, declared by ~49 panels, referenced
275× in rules) and `--ok/--danger/--warn` (only in the advisory grammar doc +
build-configurator + a course panel + two shared-snippet fallbacks). SDD-144
canonised `--good/--bad` and removed `--ok/--danger` everywhere.

This guard keeps it single-vocabulary: no panel HTML nor shared snippet may
declare or reference `--ok` / `--danger`. (The grammar doc + design-token names
elsewhere are out of scope — this scans the rendered surfaces only.)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"

# `--ok` / `--danger` as a CSS custom-property token: `--ok:` decl or `var(--ok` ref.
_RIVAL_RE = re.compile(r"(?:--(?:ok|danger)\s*:|var\(\s*--(?:ok|danger)\b)")


def _scan_targets() -> list[Path]:
    # every panel index.html + the shared snippets that get inlined into them
    return sorted(WEBAPP.glob("*/index.html")) + sorted((WEBAPP / "_shared").glob("*.html"))


def test_no_rival_status_token_vocabulary_remains():
    offenders: list[str] = []
    for f in _scan_targets():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if _RIVAL_RE.search(line):
                rel = f.relative_to(REPO)
                offenders.append(f"{rel}:{i}")
    assert not offenders, (
        "rival status-color tokens `--ok`/`--danger` found — the cockpit uses ONE "
        "vocabulary `--good`/`--bad` (SDD-144). Use --good/--bad:\n  " + "\n  ".join(offenders)
    )


def test_canonical_tokens_still_present_on_the_reference_panel():
    """build-configurator (the grammar-doc reference impl) must now declare the
    canonical --good/--bad it is the reference for."""
    body = (WEBAPP / "build-configurator" / "index.html").read_text(encoding="utf-8")
    for tok in ("--good:", "--bad:", "--warn:"):
        assert tok in body, f"build-configurator missing canonical token {tok!r} after SDD-144"
