"""M014 trust-boundary contract lint.

Locks `config/security/m014-trust-boundaries.yaml` to the M014 milestone spec:
the 4 trust zones (E0118), the 64-bit capability word (E0121, fields verbatim +
non-overlapping proposed layout), the 6 enforcement layers, the A/B/C/D tool
ladder (E0122), the /ai-exchange boundary + import pipeline (E0123), and the
network-profile ladder (E0124). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "security" / "m014-trust-boundaries.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M014-isolation-and-trust-boundaries.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M014"


def test_four_trust_zones_verbatim():
    zones = _c()["trust_zones"]
    assert [z["zone"] for z in zones] == [0, 1, 2, 3]
    assert [z["module"] for z in zones] == ["M00216", "M00217", "M00218", "M00219"]
    names = [z["name"] for z in zones]
    assert names == ["Host Control Plane", "Oracle Plane", "Scout/Sandbox Plane",
                     "Disposable Tool Sandboxes"], f"trust-zone drift: {names}"


def test_capability_word_8_fields_nonoverlapping_64bit():
    cw = _c()["capability_word"]
    assert cw["module"] == "M00225" and cw["width_bits"] == 64
    assert cw.get("bit_layout_proposed") is True, "bit widths must be flagged agent-proposed (SB-095)"
    names = [f["name"] for f in cw["fields"]]
    assert names == ["allowed_tools", "fs_scope", "network_scope", "max_runtime",
                     "max_memory", "output_type", "trust_level", "flags"], (
        f"M00225 capability-word field drift: {names}")
    used: list[int] = []
    for f in cw["fields"]:
        span = list(range(f["offset"], f["offset"] + f["bits"]))
        assert f["offset"] + f["bits"] <= 64, f"{f['name']} exceeds 64 bits"
        assert not (set(span) & set(used)), f"{f['name']} overlaps another field"
        used += span


def test_six_enforcement_layers():
    layers = _c()["enforcement_layers"]["layers"]
    assert layers == ["CPU policy", "VM config", "filesystem mounts",
                      "network namespace", "tool wrapper", "eBPF observation"], (
        f"M00226 enforcement-layer drift: {layers}")


def test_four_tool_tiers_A_to_D():
    tiers = _c()["tool_tiers"]
    assert [t["tier"] for t in tiers] == ["A", "B", "C", "D"]
    assert [t["module"] for t in tiers] == ["M00227", "M00228", "M00229", "M00230"]


def test_filesystem_boundary_exchange_and_pipeline():
    fb = _c()["filesystem_boundary"]
    assert fb["exchange_dirs"] == ["/ai-exchange/inbox", "/ai-exchange/outbox",
                                   "/ai-exchange/artifacts"]
    # the 6-stage import pipeline, verbatim + in order
    assert fb["import_pipeline"] == ["parse", "scan", "diff", "policy-check",
                                     "oracle-review-if-needed", "commit"]


def test_network_profile_ladder():
    ladder = _c()["network_profiles"]["ladder"]
    assert ladder == ["offline", "package-registries", "docs-web", "arbitrary-web",
                      "authenticated-browser-profile"], f"M00232 ladder drift: {ladder}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00216", "M00219", "M00224", "M00225", "M00226", "M00227",
                "M00230", "M00231", "M00232"):
        assert mod in body, f"{mod} not in the M014 milestone (must trace to spec)"
