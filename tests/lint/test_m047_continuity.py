"""M047 continuity contract lint.

Locks `config/execution/m047-continuity.yaml` to the M047 spec: the 7-type
continuity taxonomy (E0448), Checkpointed Agent Sessions via CRIU (E0449),
Semantic Checkpoints (E0450), ZFS + CRIU Together (E0451), Warm Sandboxes
(E0452), Hibernated Thought (E0453), Systemd Continuity (E0454), Userspace Soft
Reboot (E0455), the 8-level continuity ladder (E0456), and the 11-step Hyper
Loop With Continuity (E0457). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "execution" / "m047-continuity.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M047-continuity-criu-zfs-warm-sandboxes-hibernated-thought.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M047"


def test_seven_continuity_types_verbatim():
    t = _c()["continuity_taxonomy"]["types"]
    assert t == ["process", "container", "workspace", "memory", "model", "workflow",
                 "user-intent"], f"type drift: {t}"


def test_checkpointed_sessions_criu_and_capabilities():
    cs = _c()["checkpointed_sessions"]
    assert cs["primitive"] == "CRIU (Checkpoint/Restore In Userspace)"
    assert len(cs["capabilities"]) == 6 and "safe rollback" in cs["capabilities"]
    assert "CRIU is not magic" in cs["caveat"]


def test_semantic_checkpoint_ten_fields():
    sc = _c()["semantic_checkpoints"]
    assert len(sc["fields"]) == 10 and "human gate state" in sc["fields"]
    assert sc["closing"] == "This is continuity with meaning"


def test_save_state_five_layers():
    lay = _c()["save_state_layers"]["layers"]
    assert [x["layer"] for x in lay] == [1, 2, 3, 4, 5]
    assert lay[0]["name"] == "ZFS snapshot" and lay[1]["name"] == "CRIU checkpoint"
    assert lay[4]["name"] == "Profile state"


def test_warm_sandboxes_branch_search():
    ws = _c()["warm_sandboxes"]
    assert ws["warm_pattern"] == ["restore checkpoint", "apply patch", "run tests"]
    assert len(ws["branch_search"]) == 7
    assert ws["closing"] == "This is test-time compute for software engineering"


def test_hibernated_thought_six_conditions_five_fields():
    ht = _c()["hibernated_thought"]
    assert len(ht["wait_conditions"]) == 6 and "memory pressure" in ht["wait_conditions"]
    assert ht["state_fields"] == ["branch summary", "state vector", "tool futures",
                                  "context refs", "next wake condition"]


def test_systemd_continuity_seven_units_and_oomd():
    sc = _c()["systemd_continuity"]
    assert "systemd-oomd" in sc["oomd"] and "PSI" in sc["oomd"]
    assert len(sc["unit_examples"]) == 7 and "gateway.service" in sc["unit_examples"]


def test_soft_reboot_four_capabilities():
    sr = _c()["soft_reboot"]
    assert "restart userspace without full hardware/kernel reboot" in sr["definition"]
    assert len(sr["capabilities"]) == 4 and "resume checkpoints" in sr["capabilities"]


def test_continuity_ladder_eight_levels_and_split():
    cl = _c()["continuity_ladder"]
    assert [x["level"] for x in cl["levels"]] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert cl["levels"][7]["name"] == "user-sovereign life continuity"
    assert "level 3-7" in cl["split"]


def test_hyper_loop_eleven_steps_and_key_line():
    hl = _c()["hyper_loop_continuity"]
    assert len(hl["steps"]) == 11 and hl["steps"][0] == "Map environment"
    assert hl["steps"][-1] == "Resume later"
    assert "Continuity turns inference into practice" in hl["key_line"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00782", "M00784", "M00789", "M00790", "M00792", "M00797", "M00798"):
        assert mod in body, f"{mod} not in the M047 milestone (must trace to spec)"
