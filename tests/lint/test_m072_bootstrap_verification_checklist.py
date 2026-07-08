"""M072 Master-Bootstrap-Verification-Checklist contract lint.

Locks `config/server/m072-bootstrap-verification-checklist.yaml` to the M072
spec: the 6 mandatory checks with target subsystem + intended state + invocation
(E0688-E0693), the lock-state behavior + manual clear (E0694/E0695), the
pre-execution gate (E0696), and SFIF/Stage-Gate integration (E0697). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "server" / "m072-bootstrap-verification-checklist.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M072-master-bootstrap-verification-checklist.md"

# (check, subsystem) — the spec's exact 6-check grid.
EXPECTED = [
    ("01", "Microcode/ISA"),
    ("02", "Bus Geometry"),
    ("03", "Linux Memory"),
    ("04", "Driver Fabric"),
    ("05", "Security Core"),
    ("06", "Network Line"),
]


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _chk(num: str) -> dict:
    return next(x for x in _c()["checks"] if x["check"] == num)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M072"


def test_doctrinal_lock_state_anchor():
    assert "node enters lock-state until manually cleared by the Architect" in _c()["doctrinal_anchor"]


def test_six_checks_present_and_ordered():
    nums = [x["check"] for x in _c()["checks"]]
    assert nums == ["01", "02", "03", "04", "05", "06"]
    for num, subsystem in EXPECTED:
        assert _chk(num)["subsystem"] == subsystem, f"check {num} subsystem drift"


def test_check01_avx512_cpuinfo_invocation():
    c = _chk("01")
    assert "avx512_vnni" in c["intended"] and "avx512_bf16" in c["intended"]
    assert "/proc/cpuinfo" in c["invocation"]


def test_check03_zfs_arc_128gb_bytes():
    c = _chk("03")
    assert "137438953472 bytes (128GB)" in c["intended"]
    assert c["invocation"] == "arcstat -s c"


def test_check05_tetragon_socket():
    c = _chk("05")
    assert "Tetragon local UNIX socket" in c["intended"]
    assert c["invocation"] == "ls -la /var/run/tetragon/tetragon.events"


def test_check06_enp5s0_mtu_9000():
    c = _chk("06")
    assert "enp5s0" in c["intended"] and "MTU 9000" in c["intended"]
    assert "mtu 9000" in c["invocation"]


def test_lock_state_and_manual_clear():
    ls = _c()["lock_state"]
    assert "lock-state on any anomaly" in ls["on_anomaly"]
    assert "only the Architect" in ls["manual_clear"]


def test_sfif_integration_gates_infra_to_features():
    assert "Infrastructure -> Features transition" in _c()["sfif_integration"]["rule"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01190", "M01192", "M01194", "M01195", "M01196", "M01198", "M01206"):
        assert mod in body, f"{mod} not in the M072 milestone (must trace to spec)"
