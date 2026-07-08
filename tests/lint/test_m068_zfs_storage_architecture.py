"""M068 ZFS-storage-architecture contract lint.

Locks `config/storage/m068-zfs-storage-architecture.yaml` to the M068 spec: the
ZFS DKMS init (E0658/E0659), pool hardening (E0660), the tank dataset hierarchy
(E0661), sync=always for tank/context (E0662), recordsize=16k for tank/containers
(E0663), layer allocation + KV-cache fp8 (E0665), and the snapshot policy
(E0667). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "storage" / "m068-zfs-storage-architecture.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M068-zfs-storage-architecture.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _ds(name: str) -> dict:
    return next(x for x in _c()["datasets"] if x["dataset"] == name)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M068"


def test_dkms_three_packages():
    d = _c()["dkms"]
    assert d["packages"] == ["dkms", "zfs-dkms", "zfsutils-linux"]
    assert "6.12-znver5" in d["validation"]


def test_pool_create_command_verbatim():
    p = _c()["pool"]
    assert p["create_command"] == ("zpool create -f -o ashift=12 -O compression=lz4 "
                                   "-O atime=off tank /dev/nvme0n1")
    assert p["ashift"] == 12 and p["compression"] == "lz4" and p["atime"] == "off"


def test_dataset_hierarchy_five():
    d = [x["dataset"] for x in _c()["datasets"]]
    assert d == ["tank", "tank/context", "tank/containers", "tank/models", "tank/logs"]


def test_tank_context_sync_always():
    assert _ds("tank/context")["sync"] == "always"
    assert "sovereignty-critical" in _ds("tank/context")["role"]


def test_tank_containers_recordsize_16k():
    c = _ds("tank/containers")
    assert c["recordsize"] == "16k"
    assert "Podman graph driver" in c["role"] and "uncompressed" in c["role"]


def test_layer_allocation_kv_cache_fp8():
    la = _c()["layer_allocation"]
    assert "KV cache fp8 compression" in la["scheme"]


def test_snapshot_policy_365_days():
    sp = _c()["snapshot_policy"]["rule"]
    assert "pre-commit snapshot" in sp and "365 days" in sp


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01139", "M01141", "M01142", "M01143", "M01144", "M01148", "M01151"):
        assert mod in body, f"{mod} not in the M068 milestone (must trace to spec)"
