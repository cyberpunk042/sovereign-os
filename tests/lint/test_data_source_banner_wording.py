"""Data-source banner wording consistency (SDD-141).

Panels show a `#data-source-banner` / `#ds-state-detail` status line saying which
endpoint they consume and how to recover when the daemon is down. Two phrasings
had coexisted:

  canonical (Pattern-A, ~13 panels via #ds-state-detail):
    consuming <code>/api/X</code> from the <name> API daemon
    cannot reach <code>/api/X</code> — is the <name> API daemon running? (err)

  terse (Pattern-B, 5 panels via #data-source-banner):
    consuming <code>/api/X</code>
    cannot reach the <name> API daemon (err)

The terse error dropped the endpoint + the recover-prompt ("is it running?").
SDD-141 converged the 5 Pattern-B panels to the canonical shape. This pins it:
no panel keeps the terse `cannot reach the <name> API daemon` form, and each of
the 5 converted panels carries the canonical `#data-source-banner` phrasing.
(Panel-specific honest tails — code-console's "the three-pane console stays
fully visible", d-25's producer disclaimer — are preserved and not constrained.)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"

# the terse anti-pattern the canonical form replaces
_TERSE_RE = re.compile(r"cannot reach the [a-z][a-z0-9-]* API daemon")

CONVERTED = ("code-console", "d-21-lm-orchestration", "d-23-models-catalog",
             "d-24-cpu-features", "d-25-selfdef-management")


def test_no_panel_keeps_the_terse_cannot_reach_the_daemon_form():
    offenders: list[str] = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        for i, line in enumerate(idx.read_text(encoding="utf-8").splitlines(), 1):
            if _TERSE_RE.search(line):
                offenders.append(f"{idx.parent.name}:{i}")
    assert not offenders, (
        "terse 'cannot reach the <name> API daemon' banner — use the canonical "
        "'cannot reach <code>/api/X</code> — is the <name> API daemon running?':\n  "
        + "\n  ".join(offenders)
    )


def test_converted_banners_use_the_canonical_shape():
    for slug in CONVERTED:
        body = (WEBAPP / slug / "index.html").read_text(encoding="utf-8")
        # the error branch: cannot reach <code>…</code> — is the … API daemon running?
        assert re.search(
            r"data-source-banner'\)\.innerHTML = 'cannot reach <code>[^']*</code> — is the "
            r"[a-z0-9-]+ API daemon running\?", body
        ), f"{slug}: #data-source-banner error branch not in canonical 'is the … running?' form"
        # the positive branch: consuming <code>…</code> from the … API daemon
        assert re.search(
            r"data-source-banner'\)\.innerHTML = 'consuming <code>[^']*</code> from the "
            r"[a-z0-9-]+ API daemon", body
        ), f"{slug}: #data-source-banner positive branch not in canonical 'from the … daemon' form"
