"""M009 Deterministic Cortex Runtime v0 (full spec) contract lint.

Locks `config/agent/m009-deterministic-cortex-runtime-v0.yaml` to the M009 spec:
the AVX-512 feature catalog (E0072), hot-vs-cold layer separation (E0073), the
64-bit branch control word bit order (E0074), the scheduler tick algorithm
(E0075), the speculative-CPU analogy (E0076), and the concrete advanced tricks
(E0077). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m009-deterministic-cortex-runtime-v0.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M009-deterministic-cortex-runtime-v0.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M009"


def test_feature_catalog_eight():
    f = [x["feature"] for x in _c()["feature_catalog"]]
    assert f == ["VPTERNLOG", "VPCOMPRESS", "VPEXPAND", "VPOPCNTDQ", "VP2INTERSECT",
                 "VBMI", "VBMI2", "k-masks"]


def test_hot_and_cold_tiers():
    t = _c()["tiers"]
    assert len(t["hot"]) == 8 and "sketches" in t["hot"] and "control words" in t["hot"]
    assert t["cold"] == ["actual prompt text", "documents", "code chunks", "long traces"]


def test_control_word_nine_fields_and_rationale():
    cw = _c()["control_word"]
    fields = {x["name"]: x["bits"] for x in cw["fields"]}
    assert len(fields) == 9
    assert fields["route"] == "0..3" and fields["lifecycle"] == "8..15" and fields["flags"] == "56..63"
    assert cw["bit_order_rationale"] == "most frequently tested fields packed low"


def test_scheduler_tick_seven_steps():
    s = _c()["scheduler_tick"]["steps"]
    assert len(s) == 7
    assert s[0] == "load 8" and s[-1] == "enqueue dense batches"
    assert "compute oracle-needed mask" in s


def test_speculative_cpu_analogy_and_invariant():
    sc = _c()["speculative_cpu_analogy"]
    m = {x["cpu_stage"]: x["hardware"] for x in sc["mapping"]}
    assert m["predictor"] == "RTX 4090" and m["retirement"] == "RTX PRO"
    assert "reorder+commit" in m and m["architectural state"] == "RAM+ZFS"
    assert "deterministic runtime commits" in sc["invariant"]


def test_advanced_tricks_vpternlog_fusion():
    at = _c()["advanced_tricks"]
    assert at["vpternlog_fusion"] == "commit = (oracle_ok & grammar_ok) | (trusted_fast_path & low_risk)"
    assert "sketches-before-embeddings" in at["sketches_first"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00130", "M00132", "M00138", "M00140", "M00142", "M00143", "M00145"):
        assert mod in body, f"{mod} not in the M009 milestone (must trace to spec)"
