"""M084 OPNsense/SD-WAN boundary + Tetragon-dropout resilience contract lint.

Locks `config/server/m084-opnsense-boundary.yaml` to the M084 spec: the
Zero-Trust dual-NIC boundary (E0808/E0809), VLAN 100/200 (E0810/E0811), the
no-outbound-WAN rule (E0812), the Tetragon-dropout gotcha (E0813), the dropout
prevention (E0814/E0815), the read-only firewall interface contract (E0816), and
reconfiguration observability (E0817). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Project boundary (R10212): OPNsense observed READ-ONLY; Tetragon = selfdef MS044.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "server" / "m084-opnsense-boundary.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _vlan(n: int) -> dict:
    return next(x for x in _c()["vlans"] if x["vlan"] == n)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M084"


def test_boundary_zero_trust_and_opnsense_authority():
    b = _c()["boundary"]
    assert "physically segregated at the hardware boundary" in b["doctrine"]
    assert "OPNsense Core Router" in b["perimeter_authority"]


def test_vlan_100_management_2_5gbe():
    v = _vlan(100)
    assert "Intel I226-V 2.5GbE" in v["nic"]
    assert "Tetragon log streams" in v["carries"]


def test_vlan_200_data_10gbe_no_wan():
    v = _vlan(200)
    assert "Marvell AQC113C 10GbE" in v["nic"]
    assert "no outbound WAN" in v["carries"]
    assert "no outbound WAN for the data plane" in _c()["data_plane_rule"]


def test_dropout_gotcha_guardian_blind():
    g = _c()["dropout_gotcha"]
    assert "buffer disconnects" in g["cause"]
    assert "blinding the real-time exploit containment system" in g["effect"]


def test_dropout_prevention_bindsto_eof_restart():
    dp = _c()["dropout_prevention"]
    assert dp["bindsto"]["unit_directive"] == "BindsTo=tetragon.service"
    assert "nonzero exit" in dp["eof_sentinel"]["rule"]
    assert dp["restart_loop"]["unit_directive"] == "Restart=always + RestartSec=1"
    assert dp["shipped_commit"] == "47632d0"


def test_firewall_observation_read_only():
    fo = _c()["firewall_observation"]["contract"]
    assert "READ-ONLY" in fo and "never configures the firewall" in fo


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01412", "M01413", "M01414", "M01417", "M01418", "M01419", "M01420"):
        assert mod in body, f"{mod} not in the M084 milestone (must trace to spec)"
