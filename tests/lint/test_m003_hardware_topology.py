"""M003 hardware-topology + PCIe-discipline contract lint.

Locks `config/hardware/m003-hardware-topology.yaml` to the M003 spec: the
hardware inventory (E0020-E0026), the PCIe lane-sharing trap (E0027), the better
layout (E0028), the power envelope + PSU (E0029/E0030), and the CUDA-P2P-vs-IOMMU
note (E0031). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "hardware" / "m003-hardware-topology.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M003-hardware-topology-pcie-discipline.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M003"


def test_inventory_seven_components():
    comps = [x["component"] for x in _c()["inventory"]]
    assert len(comps) == 7
    assert any("Ryzen 9 9900X" in c for c in comps)
    assert any("Blackwell" in c for c in comps)
    assert any("ProArt X870E-Creator" in c for c in comps)


def test_blackwell_96gb_gddr7_600w():
    bw = next(x for x in _c()["inventory"] if "Blackwell" in x["component"])
    assert "96 GB GDDR7" in bw["spec"] and "600W" in bw["spec"]


def test_lane_trap_verbatim():
    assert _c()["lane_trap"] == "PCIEX16(G5)_2 shares lanes with M.2_2"


def test_better_layout_x8_x8():
    assert _c()["better_layout"] == "Blackwell x8 + 4090 x8 + M.2_1 x4 + chipset NVMe x4"


def test_power_envelope_and_psu():
    pe = _c()["power_envelope"]
    assert "600W Blackwell" in pe["draws"] and "350W 4090" in pe["draws"]
    assert "1600W minimum" in pe["psu"]


def test_p2p_iommu_incompatible():
    assert _c()["p2p_iommu_note"] == "CUDA bare-metal PCIe P2P incompatible with IOMMU on Linux"


def test_nic_drivers_atlantic_igc():
    d = {x["nic"]: x["driver"] for x in _c()["nic_drivers"]}
    assert d["Marvell AQC113C 10GbE"] == "atlantic"
    assert d["Intel I226-V 2.5GbE"] == "igc"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00029", "M00031", "M00034", "M00040", "M00041", "M00042", "M00043"):
        assert mod in body, f"{mod} not in the M003 milestone (must trace to spec)"
