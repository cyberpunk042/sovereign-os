"""autohealth `status` consumers MUST read the verdict from last_tick.

The R308 `autohealth status --json` verb nests its health verdict +
severity_counts under a `last_tick` object (the cached latest tick); the
top level carries only engine state (tick_count, suppression_keys). Four
intelligence/diagnostic consumers probe `autohealth status` and surface
its verdict:
  - morning-brief.py        (operator daily brief)
  - next-action-advisor.py  (what-to-do-next advisor)
  - cot-registry.py         (health-triage chain-of-thought flow)
  - state-snapshot.py       (read-only probe catalog)

All four originally read top-level `verdict`/`severity` — which `status`
never emits — so every one silently showed no health signal. They were
fixed to read `last_tick.verdict`. The morning-brief schema-binding gate
locks morning-brief + the producer contract, but nothing guarded the other
three from regressing back to a top-level-only read (the producer gate
stays green through such a regression). This gate freezes the consumption
contract: every consumer of `autohealth status` MUST reference `last_tick`
in its verdict/severity extraction.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Each consumer that probes `autohealth status` and reads its verdict.
CONSUMERS = [
    "scripts/intelligence/morning-brief.py",
    "scripts/intelligence/next-action-advisor.py",
    "scripts/intelligence/cot-registry.py",
    "scripts/diagnostics/state-snapshot.py",
]


def _probes_autohealth_status(text: str) -> bool:
    # The consumer runs `autohealth status` (as an argv list or a verb str).
    return ("autohealth" in text
            and ('"status"' in text or "autohealth status" in text
                 or "autohealth.py" in text))


@pytest.mark.parametrize("rel", CONSUMERS)
def test_consumer_exists_and_probes_autohealth_status(rel):
    p = REPO_ROOT / rel
    assert p.is_file(), f"expected autohealth-status consumer missing: {rel}"
    assert _probes_autohealth_status(p.read_text(encoding="utf-8")), (
        f"{rel} no longer probes `autohealth status` — update this gate's "
        f"CONSUMERS list if the wiring intentionally changed."
    )


@pytest.mark.parametrize("rel", CONSUMERS)
def test_consumer_reads_verdict_from_last_tick(rel):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "last_tick" in text, (
        f"{rel} probes `autohealth status` but does NOT reference "
        f"`last_tick` — its verdict/severity extraction has regressed to a "
        f"top-level read, which `status` never emits, so the health signal "
        f"is silently dead. Read the verdict from last_tick (see "
        f"morning-brief.probe_autohealth)."
    )
