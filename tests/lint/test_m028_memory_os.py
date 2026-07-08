"""M028 memory-OS contract lint.

Locks `config/agent/m028-memory-os.yaml` to the M028 spec: the 7 named memory
types + ground-truth layer (E0260/E0261), the MemoryItem struct (E0262), the
temporal query verbs (E0263), the admission rules + 11-stage lifecycle (E0264).
No minimization; the "8th" type name is NOT fabricated (count discrepancy
recorded).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m028-memory-os.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M028-memory-os-8-memory-types.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M028"


def test_seven_named_memory_types_verbatim():
    t = _c()["memory_types"]
    assert [x["type"] for x in t] == [1, 2, 3, 4, 5, 6, 7]
    names = [x["name"] for x in t]
    assert names == ["Working Memory", "Episodic Memory", "Semantic Memory",
                     "Procedural Memory", "Temporal Graph Memory", "Value Memory",
                     "KV Memory"], f"memory-type drift: {names}"


def test_eighth_type_name_not_fabricated():
    # title says 8; only 7 are named. The contract must flag this, not invent an
    # 8th type name.
    assert _c().get("title_says_eight") is True
    types = _c()["memory_types"]
    assert len(types) == 7, "must not fabricate an 8th memory-type name"


def test_memory_item_ten_uint64_fields_verbatim():
    m = _c()["memory_item"]
    assert m["field_type"] == "uint64_t"
    assert m["fields"] == ["id", "type", "source_ref", "time_range", "trust",
                           "freshness", "topic_sketch", "entity_sketch",
                           "value_score", "flags"], f"MemoryItem drift: {m['fields']}"


def test_temporal_query_five_verbs():
    v = _c()["temporal_query_verbs"]["verbs"]
    assert v == ["true-then", "true-now", "changed", "contradicted-by",
                 "last-verified"], f"temporal-verb drift: {v}"


def test_memory_lifecycle_eleven_stages_in_order():
    s = _c()["memory_lifecycle"]["stages"]
    assert s == ["observe", "classify", "quarantine", "link", "score", "store-raw",
                 "extract-facts", "verify", "promote", "decay", "archive"], (
        f"memory-lifecycle drift: {s}")
    assert len(s) == 11


def test_ground_truth_layer_eight():
    g = _c()["ground_truth_layer"]["layers"]
    assert len(g) == 8 and "trust-score" in g and "raw-episode" in g


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00459", "M00465", "M00466", "M00467", "M00469", "M00471", "M00472"):
        assert mod in body, f"{mod} not in the M028 milestone (must trace to spec)"
