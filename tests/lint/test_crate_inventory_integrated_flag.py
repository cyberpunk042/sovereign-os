"""crate-inventory integrated-flag lint (F-2026-100 / SDD-997).

The crate-inventory (`docs/architecture/crate-inventory.md`) carries a per-crate
✅ **integrated** flag: a crate is integrated only when it is actually USED by a
running production binary — in the dependency closure of gatewayd / telemetry /
resource-control, so its code compiles and links into a process that runs. Being
merely *referenced* is not enough: a cockpit crate wasm-bridged for a panel
(SDD-800, 0 panels wired) or a crate reached only through a demo/dev binary or the
sovereign-llm / sovereign-retrieval hubs is NOT integrated.

This lint keeps the flag honest against the same closure the generator computes:
the set of ✅-flagged crates in the committed doc must equal the production
closure exactly (no missing integration, no over-claim), every flagged crate must
carry a usage note that validates the integration, and the used-not-referenced
boundary is spot-checked (a production binary is flagged; a panel-only cockpit
crate is not).

Per SDD-997; complements the byte-equality sync lint (SDD-995) with an
independent semantic check of what the flag *means*.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN = REPO_ROOT / "scripts" / "docs" / "gen-crate-inventory.py"
INVENTORY = REPO_ROOT / "docs" / "architecture" / "crate-inventory.md"

_FLAGGED = re.compile(r"^- \*\*`(sovereign-[a-z0-9-]+)`\*\* — .* — ✅ \*\*integrated\*\*", re.MULTILINE)


def _load_generator():
    spec = importlib.util.spec_from_file_location("_gen_crate_inventory", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flagged_in_doc() -> set[str]:
    return set(_FLAGGED.findall(INVENTORY.read_text(encoding="utf-8")))


def _production_closure() -> set[str]:
    gen = _load_generator()
    crates = gen.load()
    return gen.closure(crates, gen.PROD_ROOTS)


def test_flagged_set_equals_the_production_closure():
    flagged = _flagged_in_doc()
    prod = _production_closure()
    missing = prod - flagged      # used in production but not flagged integrated
    extra = flagged - prod        # flagged integrated but not actually production-used
    assert not missing and not extra, (
        "crate-inventory ✅ integrated flags drifted from the production closure — "
        "run `python3 scripts/docs/gen-crate-inventory.py`.\n"
        f"  used-but-unflagged: {sorted(missing)}\n"
        f"  flagged-but-not-used: {sorted(extra)}"
    )


def test_every_flagged_crate_has_a_usage_note():
    """The flag must EXPLAIN the usage that validates the integration — a bare
    ✅ with no consumer/binary note is not allowed."""
    body = INVENTORY.read_text(encoding="utf-8")
    bad = re.findall(
        r"^- \*\*`(sovereign-[a-z0-9-]+)`\*\* — .* — ✅ \*\*integrated\*\*(?!: )",
        body, re.MULTILINE,
    )
    assert not bad, f"integrated crates with no usage explanation: {sorted(set(bad))}"


def test_used_not_merely_referenced():
    """The boundary the operator drew: used ≠ referenced-in-a-panel."""
    gen = _load_generator()
    crates = gen.load()
    prod = gen.closure(crates, gen.PROD_ROOTS)
    flagged = _flagged_in_doc()

    # a real production binary is integrated
    assert "sovereign-gatewayd" in flagged, "the gateway daemon must be flagged integrated"

    # no cockpit crate (panel-bridged, 0 panels wired) is integrated
    cockpit_flagged = {n for n in flagged if n.startswith("sovereign-cockpit-")}
    assert not cockpit_flagged, (
        f"cockpit crates are wasm-bridged for panels, not used by a running path — "
        f"they must not be flagged integrated: {sorted(cockpit_flagged)}"
    )
    # and none of them is in the production closure either (defense in depth)
    assert not {n for n in prod if n.startswith("sovereign-cockpit-")}


def test_integrated_count_is_the_minority_reality():
    """Anti-inflation: the audit's honest signal is that most of the workspace is
    NOT yet integrated. The flag must not silently balloon to claim otherwise."""
    total = len(_load_generator().load())
    flagged = len(_flagged_in_doc())
    assert 0 < flagged < total // 2, (
        f"{flagged}/{total} crates flagged integrated — implausible; the flag "
        "should reflect the real production closure, a minority of the workspace"
    )
