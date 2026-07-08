"""M008 bit-level-cheats contract lint.

Locks `config/hardware/m008-bit-level-cheats.yaml` to the M008 spec: the 13
bit-level "cheats" that turn AVX-512 instructions into AI control infrastructure
(E0059-E0071). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m008-bit-level-cheats.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M008-bit-level-cheats-avx512-features.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _cheat(n: int) -> dict:
    return next(x for x in _c()["cheats"] if x["n"] == n)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M008"


def test_thirteen_cheats_present():
    assert [x["n"] for x in _c()["cheats"]] == list(range(1, 14))


def test_ternary_and_compress_instructions():
    assert "VPTERNLOG" in _cheat(2)["detail"]
    assert "VPCOMPRESS" in _cheat(4)["detail"]


def test_bitset_token_law_vocab_math():
    assert "128k vocab = 16KB = 250 vector chunks" in _cheat(5)["detail"]


def test_inline_lut_formula():
    assert "decision = (rule_word >> condition) & 1" == _cheat(6)["detail"]


def test_speculative_commit_formula():
    assert _cheat(8)["detail"] == "accept = oracle & grammar & tool & budget & memory"


def test_bloom_popcount_and_filter_cascade():
    assert _cheat(10)["detail"] == "popcount(query & memory)"
    assert "lifecycle / budget / route-tool / grammar / duplicate / cheap-model / oracle" == _cheat(12)["detail"]


def test_three_representations():
    assert _cheat(13)["detail"] == "dense numeric / bitfield law / text payload"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00113", "M00114", "M00116", "M00118", "M00120", "M00123", "M00126"):
        assert mod in body, f"{mod} not in the M008 milestone (must trace to spec)"
