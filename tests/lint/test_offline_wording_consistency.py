"""Honest-offline card wording consistency (SDD-140).

Panels that show a "the <X> daemon is unreachable — … Nothing is fabricated
(SB-077)." scaffold card when their daemon is down (the SDD-111/113/115
always-visible pattern) had drifted in wording: d-24 said "… populates when
it's reachable" (the canonical exemplar), d-23 said "… will list here when
it's reachable", d-25 said "… populate here when it's reachable". Same honest
message, three phrasings.

This converges them to one shape and pins it:
  the <X> daemon is unreachable — <what> populate[s] when it's reachable.
  Nothing is fabricated (SB-077).

The honesty clause ("Nothing is fabricated (SB-077).") + the "when it's
reachable" promise are the load-bearing invariants (SB-077); the drift
phrasings ("will list here" / "populate here") are banned so they can't return.
Only the true scaffold cards are checked — the phrase also appears in assistant
hover-intel prose ("… daemon is unreachable;") and code comments, which are a
different context and out of scope.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"

# the panels that render a daemon-unreachable honest-offline scaffold card
OFFLINE_CARD_PANELS = ("d-23-models-catalog", "d-24-cpu-features", "d-25-selfdef-management")

# the canonical honesty tail every such card must end with (SB-077)
CANONICAL_TAIL = "when it's reachable. Nothing is fabricated (SB-077)."
CARD_LEAD = "daemon is unreachable —"
DRIFT_PHRASES = ("will list here", "populate here")


def _card_line(body: str) -> str | None:
    """The scaffold-card string = the line carrying BOTH the lead and the
    honesty clause (distinguishes it from assistant prose / comments)."""
    for line in body.splitlines():
        if CARD_LEAD in line and "Nothing is fabricated (SB-077)." in line:
            return line
    return None


def test_offline_cards_use_the_canonical_honesty_wording():
    missing: list[str] = []
    for slug in OFFLINE_CARD_PANELS:
        body = (WEBAPP / slug / "index.html").read_text(encoding="utf-8")
        line = _card_line(body)
        if line is None:
            missing.append(f"{slug}: no daemon-unreachable scaffold card found")
            continue
        # the escaped apostrophe (it\'s) is literal in the JS string source
        if CANONICAL_TAIL.replace("it's", "it\\'s") not in line:
            missing.append(f"{slug}: card does not end with the canonical '{CANONICAL_TAIL}'")
    assert not missing, "honest-offline cards drift from the canonical wording:\n  " + "\n  ".join(missing)


def test_no_drift_verb_phrasings_anywhere():
    offenders: list[str] = []
    for idx in sorted(WEBAPP.glob("*/index.html")):
        body = idx.read_text(encoding="utf-8")
        for phrase in DRIFT_PHRASES:
            if phrase in body:
                offenders.append(f"{idx.parent.name}: {phrase!r}")
    assert not offenders, (
        "banned honest-offline drift phrasings — use '… populate[s] when it's reachable':\n  "
        + "\n  ".join(offenders)
    )
