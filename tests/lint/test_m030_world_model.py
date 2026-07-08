"""M030 world-model-plane contract lint.

Locks `config/agent/m030-world-model.yaml` to the M030 spec: the 13 world
elements (E0281), the tier catalog (E0283), the 6-mask catalog + hot-metadata
arrays (E0284), the World Model Plane 7 sub-parts (E0287), and the Ultimate Loop
9-step runtime (E0287, order). No minimization; array count recorded, not
fabricated.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m030-world-model.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M030-world-model-plane-state-action-transition.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M030"


def test_thirteen_world_elements_verbatim():
    e = _c()["world_elements"]["elements"]
    assert e == ["filesystem", "codebase", "terminal", "browser", "GUI",
                 "documents", "databases", "network-services", "VM-sandbox",
                 "model-serving-stack", "ZFS-snapshots", "user-preferences",
                 "project-state"], f"world-element drift: {e}"
    assert len(e) == 13


def test_tier_catalog_five_verbatim():
    t = _c()["tier_catalog"]["tiers"]
    assert t == ["Deterministic", "Learned-Local", "Language", "Simulated", "Human"]


def test_six_mask_catalog_verbatim():
    m = _c()["mask_catalog"]["masks"]
    assert m == ["safe_to_simulate", "needs_sandbox", "needs_human", "needs_oracle",
                 "can_commit", "should_rollback"], f"mask drift: {m}"


def test_hot_metadata_count_recorded_not_fabricated():
    h = _c()["hot_metadata_arrays"]
    assert h["array_count"] == 8
    # only the 6 named-in-features arrays; the other 2 are NOT fabricated
    assert len(h["named_arrays"]) == 6, "must not fabricate the 2 unnamed arrays"


def test_world_model_plane_seven_sub_parts():
    sp = _c()["world_model_plane"]["sub_parts"]
    assert len(sp) == 7 and "rollback-planner" in sp and "transition-predictors" in sp


def test_ultimate_loop_nine_steps_in_order():
    s = _c()["ultimate_loop"]["steps"]
    assert s == ["observe", "generate", "predict", "score", "simulate", "act",
                 "observe", "update", "commit"], f"Ultimate-Loop drift: {s}"
    assert len(s) == 9


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00493", "M00505", "M00506", "M00507", "M00508", "M00509"):
        assert mod in body, f"{mod} not in the M030 milestone (must trace to spec)"
