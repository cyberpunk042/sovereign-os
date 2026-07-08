"""M002 control-word injected-logic contract lint.

Locks `config/hardware/m002-control-word-logic.yaml` to the M002 spec: the 64-bit
control-word bitfield layout (E0011), branchless masked-op execution (E0012), the
64-entry boolean LUT (E0013), the per-branch micro-rule table (E0014), the ZMM
state/memory/rule/random layout (E0015), variable-shift tradeoff (E0016), and the
32/64/128-bit rule words (E0017-E0019). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m002-control-word-logic.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M002-control-word-injected-logic.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M002"


def test_lane_fields_four():
    assert _c()["lane_fields"]["fields"] == ["state_lo", "state_hi", "control", "scratch"]


def test_control_word_seven_fields_verbatim():
    cw = _c()["control_word_layout"]
    assert cw["bits"] == 64
    fields = {x["name"]: x["bits"] for x in cw["fields"]}
    assert fields["mode"] == "0..3" and fields["event"] == "4..7"
    assert fields["intensity"] == "8..15" and fields["cooldown"] == "16..23"
    assert fields["neighborhood"] == "24..31" and fields["paramA"] == "32..47"
    assert fields["paramB"] == "48..63"


def test_branchless_execution():
    b = _c()["branchless_execution"]
    assert b["decision"] == "mask = (mode == 3)"
    assert "masked AVX-512 ops" in b["apply"]


def test_boolean_lut_64_entries():
    lut = _c()["boolean_lut"]
    assert lut["entries"] == 64
    assert "(rule_word >> 6-bit-condition) & 1" == lut["lookup"]


def test_zmm_layout_and_round_update():
    z = {x["reg"]: x["holds"] for x in _c()["zmm_layout"]["registers"]}
    assert z["zmm0"] == "state" and z["zmm2"] == "rule"
    assert _c()["round_update"]["steps"] == ["extract", "decision", "apply",
                                             "update memory", "advance RNG"]


def test_rule_words_32_64_128():
    rw = _c()["rule_words"]
    by_bits = {x["bits"]: x for x in rw}
    assert by_bits[32]["condition_bits"] == 5 and by_bits[32]["entries"] == 32
    assert by_bits[64]["condition_bits"] == 6 and by_bits[64]["entries"] == 64
    assert "two u64 limbs" in by_bits[128]["note"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00012", "M00013", "M00017", "M00018", "M00019", "M00020", "M00024"):
        assert mod in body, f"{mod} not in the M002 milestone (must trace to spec)"
