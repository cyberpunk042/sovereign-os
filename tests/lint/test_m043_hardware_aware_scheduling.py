"""M043 hardware-aware-scheduling contract lint.

Locks `config/inference/m043-hardware-aware-scheduling.yaml` to the M043 spec:
the 6 frontier questions (E0409), the 3 external research anchors (E0410), the
cloud-vs-station translation + 4 principles (E0411), and the 5 hyper features —
Context Residency (E0412), AVX-512 Routing Brain (E0413), Blackwell Context
Sovereign (E0414), 4090 Cognitive Scratchpad (E0415), KV-Aware Profiles
(E0416) — plus the bridge formula + placement + living resource model (E0417).
No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m043-hardware-aware-scheduling.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M043-bridge-layer-hardware-aware-intelligence-scheduling.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M043"
    assert _c()["bridge_mandate"] == "hardware-aware intelligence scheduling"


def test_six_frontier_questions_verbatim():
    q = _c()["frontier_questions"]["questions"]
    assert len(q) == 6 and q[0] == "Where is the context?"
    assert "Is this worth oracle compute?" in q


def test_three_research_anchors_verbatim():
    a = [x["source"] for x in _c()["research_anchors"]]
    assert a == ["NVIDIA Dynamo", "Ray Serve", "Together CPD"], f"anchor drift: {a}"


def test_station_translation_four_tiers():
    t = [x["tier"] for x in _c()["station_translation"]["layers"]]
    assert t == ["Blackwell", "4090", "Ryzen AVX-512", "RAM-ZFS"], f"tier drift: {t}"


def test_four_scheduling_principles_verbatim():
    p = _c()["scheduling_principles"]["principles"]
    assert p == ["route to where useful context already lives", "avoid recomputing prefill",
                 "reuse stable prefixes",
                 "separate cheap exploration from expensive verification"]


def test_context_residency_six_kv_types():
    cr = _c()["context_residency"]
    assert cr["resident_kv_types"] == ["system prompt KV", "tool schema KV",
                                       "repo map KV", "project policy KV",
                                       "user preference KV", "active task KV"]
    assert cr["closing"] == "This is how hardware becomes intelligence"


def test_routing_brain_ten_fields_eight_decisions():
    rb = _c()["avx512_routing_brain"]
    assert len(rb["hot_metadata_fields"]) == 10 and "cache_hit_prob" in rb["hot_metadata_fields"]
    d = rb["bulk_eval_decisions"]
    assert d == ["use_local", "use_cloud", "use_blackwell", "use_4090", "use_sandbox",
                 "reuse_context", "require_oracle", "require_human"], f"decision drift: {d}"


def test_blackwell_five_roles_and_mandate():
    bw = _c()["blackwell_context_sovereign"]
    assert len(bw["roles"]) == 5 and "serve as final commit judge" in bw["roles"]
    assert "preserve the expensive mental state" in bw["mandate"]


def test_4090_eight_uses_and_doctrine():
    s = _c()["scratchpad_4090"]
    assert len(s["uses"]) == 8 and "SLM workers" in s["uses"]
    assert s["doctrine"] == "It can be wrong. That is fine. The CPU filters. Blackwell verifies"


def test_kv_aware_profiles_six_bundles():
    b = [x["profile"] for x in _c()["kv_aware_profiles"]["bundles"]]
    assert b == ["fast", "careful", "deep", "private", "autonomous", "experimental"]


def test_bridge_formula_two_examples():
    bf = _c()["bridge_formula"]
    assert bf["formula"] == "research concept -> hardware policy -> real user choice"
    assert len(bf["examples"]) == 2
    assert "Careful code mode" in bf["examples"][0]["user_choice"]


def test_placement_six_dimensions_and_living_resource_nine():
    pl = _c()["placement"]
    assert "It is in placement" in pl["breakthrough"]
    assert len(pl["dimensions"]) == 6 and len(pl["care_about"]) == 8
    lr = _c()["living_resource_model"]["dimensions"]
    assert lr == ["compute", "memory", "KV", "risk", "cost", "latency", "privacy",
                  "reversibility", "confidence"], f"resource-model drift: {lr}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00716", "M00721", "M00723", "M00724", "M00726", "M00728", "M00730"):
        assert mod in body, f"{mod} not in the M043 milestone (must trace to spec)"
