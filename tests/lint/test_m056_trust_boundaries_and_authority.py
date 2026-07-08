"""M056 trust-boundaries + authority contract lint.

Locks `config/security/m056-trust-boundaries-and-authority.yaml` to the M056
spec: the Authority Model + 7 actor scopes (E0538), the 7 Authority Levels
(E0539), the 5 Trust Rings (E0540), contextual Model Trust (E0541), Cloud Trust
(E0542), Memory Trust 7 levels (E0543), Commit Authority (E0544), Tool Authority
(E0545), User Authority (E0546), and Authority + Profiles + Key Rule (E0547). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "security" / "m056-trust-boundaries-and-authority.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M056-trust-boundaries-and-authority.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M056"


def test_authority_model_seven_actors_and_invariant():
    am = _c()["authority_model"]
    assert am["doctrine"] == "Nothing should have ambient authority"
    actors = [x["actor"] for x in am["actor_scopes"]]
    assert actors == ["User", "Runtime", "Models", "Tools", "Sandboxes", "Cloud", "Memory"]
    assert am["critical_invariant"] == "A model can request authority. It cannot grant itself authority"


def test_seven_authority_levels_verbatim():
    lv = _c()["authority_levels"]["levels"]
    assert [x["level"] for x in lv] == [0, 1, 2, 3, 4, 5, 6]
    names = [x["name"] for x in lv]
    assert names == ["Observe", "Suggest", "Simulate", "Prepare", "Execute bounded",
                     "Commit", "Persist"], f"level drift: {names}"


def test_five_trust_rings_verbatim():
    r = _c()["trust_rings"]["rings"]
    assert [x["ring"] for x in r] == [0, 1, 2, 3, 4]
    assert r[0]["name"] == "Sovereign Kernel" and r[4]["name"] == "Cloud/External"
    assert _c()["trust_rings"]["transition_rule"] == "Movement between rings requires explicit policy"


def test_model_trust_four_roles_nine_dimensions():
    mt = _c()["model_trust"]
    assert len(mt["role_examples"]) == 4
    assert len(mt["trust_dimensions"]) == 9 and "schema_validity" in mt["trust_dimensions"]


def test_cloud_trust_five_allowed_six_restricted():
    ct = _c()["cloud_trust"]
    assert ct["doctrine"] == "Cloud is not forbidden. It is scoped"
    assert len(ct["allowed"]) == 5 and "redacted summaries" in ct["allowed"]
    assert len(ct["restricted"]) == 6 and "raw traces" in ct["restricted"]


def test_memory_trust_seven_levels_verbatim():
    lv = [x["level"] for x in _c()["memory_trust"]["levels"]]
    assert lv == ["raw_observation", "derived_summary", "model_reflection",
                  "user_statement", "test_result", "external_claim", "cloud_generated"]


def test_commit_authority_eight_types_five_needs_three_high_risk():
    ca = _c()["commit_authority"]
    assert len(ca["commit_types"]) == 8 and "adapter promotion" in ca["commit_types"]
    assert ca["every_commit_needs"] == ["actor", "reason", "policy decision",
                                        "rollback status", "trace reference"]
    assert len(ca["high_risk_needs"]) == 3 and "snapshot" in ca["high_risk_needs"]


def test_tool_authority_seven_field_declaration():
    ta = _c()["tool_authority"]
    assert len(ta["declaration"]) == 7 and "secret access" in ta["declaration"]
    assert "flag it" in ta["mismatch_rule"]


def test_user_authority_three_good_three_dangerous():
    ua = _c()["user_authority"]
    assert len(ua["good_overrides"]) == 3 and len(ua["dangerous_overrides"]) == 3
    assert "give agent all secrets forever" in ua["dangerous_overrides"]
    assert "blast radius explicit" in ua["doctrine"]


def test_authority_profiles_six_bindings_key_rule_six_checks():
    ap = _c()["authority_and_profiles"]
    profiles = [x["profile"] for x in ap["profile_bindings"]]
    assert profiles == ["private", "fast", "careful", "autonomous", "experimental", "production"]
    assert ap["key_rule"] == "Authority follows evidence"
    assert len(ap["earned_authority_checks"]) == 6 and "oracle agrees" in ap["earned_authority_checks"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00935", "M00938", "M00940", "M00944", "M00945", "M00948", "M00951"):
        assert mod in body, f"{mod} not in the M056 milestone (must trace to spec)"
