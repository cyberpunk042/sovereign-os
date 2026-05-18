"""R396 (E10.M40) — ZFS dataset operator-verbatim §4.1 + §3 content lint.

Master spec §3 + §4.1 specifies the operator-verbatim ZFS Storage
Tuning Matrix shipped on sovereign-os:

  tank/models  — recordsize=1M    compression=lz4     redundant_metadata=most
  tank/context — recordsize=16k   compression=zstd-9  copies=2  sync=always
  tank/agents  — recordsize=128k  compression=zstd-3

These are operator-named per-dataset access-pattern tuning. Drift
would silently change storage IO characteristics:
  - tank/models smaller recordsize → fragmented 100GB+ weight reads
  - tank/context losing copies=2 → context-state durability gap
  - tank/agents zstd-3 → zstd-1 silently weakens compression

R396 pins the dataset specs at L0 profile layer. Inverse of catalog
content pinning — this is OPERATIONAL STORAGE specs.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"


def _profile_datasets() -> list[dict]:
    """Parse the profile YAML, return the ZFS dataset list. NEVER-raises."""
    if yaml is None or not PROFILE.is_file():
        return []
    doc = yaml.safe_load(PROFILE.read_text(encoding="utf-8")) or {}
    # Path: hardware.storage.datasets (no zfs sub-key in actual yaml)
    for path in (
        ["hardware", "storage", "datasets"],
        ["hardware", "storage", "zfs", "datasets"],
        ["storage", "zfs", "datasets"],
        ["storage", "datasets"],
    ):
        node = doc
        for p in path:
            if isinstance(node, dict):
                node = node.get(p, {})
            else:
                node = {}
        if isinstance(node, list) and node:
            return node
    return []


def _dataset_by_name(name: str) -> dict | None:
    for ds in _profile_datasets():
        if isinstance(ds, dict) and ds.get("name") == name:
            return ds
    return None


def test_profile_has_zfs_datasets_section():
    """sain-01.yaml MUST declare ZFS datasets (§4.1 storage matrix)."""
    datasets = _profile_datasets()
    assert datasets, (
        "sain-01.yaml missing hardware.storage.zfs.datasets section "
        "(§4.1 storage matrix)"
    )


def test_tank_models_dataset_present():
    """§4.1 verbatim: 'tank/models' (1M recordsize, lz4)."""
    ds = _dataset_by_name("tank/models")
    assert ds is not None, (
        "tank/models dataset missing from profile (§4.1 storage matrix)"
    )


def test_tank_models_recordsize_1m():
    """§4.1 verbatim: tank/models recordsize=1M (operator-named for
    100GB+ weight file sequential reads)."""
    ds = _dataset_by_name("tank/models") or {}
    rs = str(ds.get("recordsize", ""))
    assert rs in ("1M", "1m", "1048576"), (
        f"tank/models recordsize MUST be 1M per §4.1; got {rs!r}"
    )


def test_tank_models_compression_lz4():
    """§4.1 verbatim: tank/models compression=lz4."""
    ds = _dataset_by_name("tank/models") or {}
    assert ds.get("compression") == "lz4", (
        f"tank/models compression MUST be lz4 per §4.1; got "
        f"{ds.get('compression')!r}"
    )


def test_tank_models_redundant_metadata_most():
    """§4.1 verbatim: tank/models redundant_metadata=most."""
    ds = _dataset_by_name("tank/models") or {}
    assert ds.get("redundant_metadata") == "most", (
        f"tank/models redundant_metadata MUST be 'most' per §4.1; got "
        f"{ds.get('redundant_metadata')!r}"
    )


def test_tank_context_dataset_present():
    """§4.1 verbatim: 'tank/context' (16k recordsize, zstd-9, copies=2)."""
    ds = _dataset_by_name("tank/context")
    assert ds is not None, (
        "tank/context dataset missing from profile (§4.1 + §7.1 — "
        "state-fabric storage)"
    )


def test_tank_context_recordsize_16k():
    """§4.1 verbatim: tank/context recordsize=16k."""
    ds = _dataset_by_name("tank/context") or {}
    rs = str(ds.get("recordsize", ""))
    assert rs in ("16k", "16K", "16384"), (
        f"tank/context recordsize MUST be 16k per §4.1; got {rs!r}"
    )


def test_tank_context_compression_zstd_9():
    """§4.1 verbatim: tank/context compression=zstd-9 (max compression
    for state files; small recordsize tolerates the CPU cost)."""
    ds = _dataset_by_name("tank/context") or {}
    assert ds.get("compression") == "zstd-9", (
        f"tank/context compression MUST be zstd-9 per §4.1; got "
        f"{ds.get('compression')!r}"
    )


def test_tank_context_copies_2():
    """§4.1 verbatim: tank/context copies=2 (durability for state
    fabric — IDENTITY.md / SOUL.md / AGENTS.md / CLAUDE.md MUST
    survive single-block corruption)."""
    ds = _dataset_by_name("tank/context") or {}
    assert ds.get("copies") == 2, (
        f"tank/context copies MUST be 2 per §4.1 (state-fabric "
        f"durability); got {ds.get('copies')!r}"
    )


def test_tank_agents_dataset_present():
    """§4.1 verbatim: 'tank/agents' (128k recordsize, zstd-3)."""
    ds = _dataset_by_name("tank/agents")
    assert ds is not None, (
        "tank/agents dataset missing from profile (§4.1 stateful "
        "local agent storage)"
    )


def test_tank_agents_recordsize_128k():
    """§4.1 verbatim: tank/agents recordsize=128k."""
    ds = _dataset_by_name("tank/agents") or {}
    rs = str(ds.get("recordsize", ""))
    assert rs in ("128k", "128K", "131072"), (
        f"tank/agents recordsize MUST be 128k per §4.1; got {rs!r}"
    )


def test_tank_agents_compression_zstd_3():
    """§4.1 verbatim: tank/agents compression=zstd-3."""
    ds = _dataset_by_name("tank/agents") or {}
    assert ds.get("compression") == "zstd-3", (
        f"tank/agents compression MUST be zstd-3 per §4.1; got "
        f"{ds.get('compression')!r}"
    )


def test_no_silent_compression_downgrade():
    """Catch silent compression-algorithm drift to weaker algos
    (lz4 → no compression, zstd-9 → zstd-1, etc). Operator-named
    levels are load-bearing storage decisions."""
    expected = {
        "tank/models": "lz4",
        "tank/context": "zstd-9",
        "tank/agents": "zstd-3",
    }
    for name, expected_compression in expected.items():
        ds = _dataset_by_name(name) or {}
        actual = ds.get("compression")
        assert actual == expected_compression, (
            f"{name} compression drift: expected {expected_compression!r}, "
            f"got {actual!r} (§4.1 contract)"
        )


def test_storage_throughput_target_documented():
    """§1.2 verbatim: '31.5 GB/s target' (2x PCIe 5.0 NVMe ZFS RAID 0).
    The throughput target should be documented in profile or comments."""
    body = PROFILE.read_text(encoding="utf-8")
    body_lower = body.lower()
    has_throughput = (
        "31.5" in body
        or "raid 0" in body_lower
        or "raid0" in body_lower
        or "raid-0" in body_lower
    )
    assert has_throughput, (
        "sain-01.yaml missing 31.5 GB/s or RAID 0 throughput documentation "
        "(§1.2 verbatim storage target)"
    )
