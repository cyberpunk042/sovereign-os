"""M012 storage-and-replay-plane contract lint.

Locks `config/storage/m012-storage-and-replay-plane.yaml` to the M012 milestone
spec: the 4 storage classes (E0099), the 8 ZFS datasets (E0100), the append-only
replay-log record fields (E0102), the columnar-state columns (E0103), and the 6
memory indexes (E0104). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "storage" / "m012-storage-and-replay-plane.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M012-storage-and-replay-plane.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M012"


def test_four_storage_classes_verbatim():
    sc = _c()["storage_classes"]
    assert [c["class"] for c in sc] == [1, 2, 3, 4]
    names = [c["name"] for c in sc]
    assert names == ["Immutable Artifacts", "Replay Logs", "Hot Caches",
                     "Workspace State"], f"storage-class drift: {names}"


def test_eight_zfs_datasets_verbatim():
    ds = _c()["zfs_datasets"]
    names = [d["dataset"] for d in ds]
    assert names == ["tank/models", "tank/datasets", "tank/runtime/replay",
                     "tank/runtime/cache", "tank/runtime/kv", "tank/workspaces",
                     "tank/checkpoints", "tank/snapshots"], f"ZFS dataset drift: {names}"
    assert [d["module"] for d in ds] == [f"M00{n}" for n in range(185, 193)]


def test_replay_log_record_ten_fields_append_only():
    r = _c()["replay_log_record"]
    assert r["module"] == "M00193" and r.get("append_only") is True
    assert r["fields"] == ["branch_id", "parent_id", "state_before", "candidate_ref",
                           "policy_mask", "grammar_state", "model", "accepted",
                           "tool_intent", "timestamp"], f"replay-record field drift: {r['fields']}"


def test_columnar_state_columns():
    c = _c()["columnar_runtime_state"]
    assert c["columns"] == ["branch_id", "score_q16", "risk_u8", "control_u64",
                            "memory_ref_u64"], f"columnar drift: {c['columns']}"


def test_six_memory_indexes():
    idx = _c()["memory_indexes"]["indexes"]
    assert idx == ["content-hash", "embedding", "bitmap-metadata",
                   "replay-transition", "tool-result", "KV-block-hash"], (
        f"memory-index drift: {idx}")


def test_retention_policy_sacred_includes_replay_log():
    """E0101 sacred-vs-disposable: the replay log is SACRED (never pruned)."""
    rp = _c()["retention_policy"]
    assert "replay-log" in rp["sacred"]
    assert "KV-cache" in rp["valuable_but_disposable"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00181", "M00184", "M00185", "M00192", "M00193", "M00194", "M00195"):
        assert mod in body, f"{mod} not in the M012 milestone (must trace to spec)"
