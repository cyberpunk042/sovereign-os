"""M023 execution-substrate contract lint.

Locks `config/execution/m023-execution-substrate.yaml` to the M023 spec: the 6
execution tiers (E0211), the 8 REPLs + capability descriptor (E0212), the WASM
tool interface (E0213), the capability word (E0214), and the Tool-ABI manifest
(E0215). No minimization; count-only entries (capability-word bitfields,
tool-ABI fields) must NOT fabricate names.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "execution" / "m023-execution-substrate.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M023-execution-substrate-wasm-deno-python-vm-tiers.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M023"


def test_six_execution_tiers_verbatim():
    t = _c()["execution_tiers"]
    assert [x["tier"] for x in t] == [0, 1, 2, 3, 4, 5]
    names = [x["name"] for x in t]
    assert names == ["Pure Logic", "WASM Plugins", "Deno Scripts", "Python REPL",
                     "Containers / MicroVMs", "VFIO 4090 VM"], f"tier drift: {names}"


def test_eight_repls_verbatim():
    k = _c()["repls"]["kinds"]
    assert k == ["math", "Python", "Deno/TypeScript", "SQL", "shell", "browser",
                 "simulation", "WASM plugin"], f"REPL drift: {k}"
    assert len(k) == 8


def test_repl_capability_descriptor_seven_fields():
    f = _c()["repl_capability_descriptor"]["fields"]
    assert f == ["runtime", "allow_net", "allow_read", "allow_write", "allow_run",
                 "max_time_ms", "output_schema"], f"descriptor drift: {f}"


def test_wasm_interface_five_signatures():
    s = _c()["wasm_tool_interface"]["signatures"]
    assert s == ["parse", "score", "filter", "transform", "validate"], f"WASM sig drift: {s}"


def test_capability_word_eight_bitfields_ref_M014_not_fabricated():
    cw = _c()["capability_word"]
    assert cw["width_bits"] == 64 and cw["bitfield_count"] == 8
    assert "M014" in cw["fields_ref"], "capability-word fields must cross-ref M014, not fabricate"


def test_tool_abi_count_recorded_not_fabricated():
    ta = _c()["tool_abi_manifest"]
    assert ta["named_field_count"] == 8
    # count-only: must not carry a fabricated `fields` list
    assert "fields" not in ta, "tool-ABI field NAMES not in the dump table — count only, no invention"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00371", "M00376", "M00377", "M00385", "M00386", "M00387", "M00388"):
        assert mod in body, f"{mod} not in the M023 milestone (must trace to spec)"
