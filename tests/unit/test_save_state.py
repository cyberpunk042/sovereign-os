"""Unit tests for the SDD-057 M047 session save-state orchestrator
`scripts/lifecycle/save-state.py`: the 5-layer capture + completeness gate + the
CRIU wrapper path (a real `criu dump` plan only when the session carries a pid).

Covers: the four always/usually-capturable layers (profile-state, memory-record,
replay-log, zfs-snapshot via SDD-050), the CRIU layer flagged missing when no
target pid (honest partial 4/5) vs planned when a pid is present (5/5 true
save-state), DRY-RUN default (no host mutation), `_SAFE_ID` validation, and the
manifest/ledger on live capture.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "lifecycle" / "save-state.py"


def _load():
    spec = importlib.util.spec_from_file_location("save_state", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SS = _load()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """A crafted session registry (one pid-less, one pid-carrying) + memory + paths."""
    reg = tmp_path / "sessions.json"
    reg.write_text(json.dumps({"sessions": [
        {"id": "s-a", "state": "active", "dataset": "agents"},
        {"id": "s-pid", "state": "active", "dataset": "context", "pid": 4321},
    ]}))
    mem = tmp_path / "memory.json"
    mem.write_text(json.dumps({"pending": []}))
    monkeypatch.setattr(SS, "SESSION_REGISTRY", reg)
    monkeypatch.setattr(SS._sr, "SESSION_REGISTRY", reg)
    monkeypatch.setattr(SS, "MEMORY_STATE", mem)
    monkeypatch.setattr(SS, "SAVE_ROOT", tmp_path / "save-state")
    monkeypatch.setattr(SS, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(SS, "SPAN_STORE", tmp_path / "spans.jsonl")
    monkeypatch.setenv("SOVEREIGN_OS_ACTIVE_PROFILE", "private")
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return tmp_path


# ── the 5-layer completeness gate ─────────────────────────────────────────────

def test_five_layers_named_and_ordered():
    assert len(SS._LAYERS) == 5
    assert set(SS._LAYERS) == {"zfs-snapshot", "criu-checkpoint", "replay-log",
                               "memory-record", "profile-state"}


def test_capture_without_pid_is_partial(env):
    r = SS.capture("s-a")  # no --confirm → dry; no pid → criu missing
    assert r["ok"] is True and r["dry_run"] is True
    assert set(r["captured"]) == {"profile-state", "memory-record", "replay-log", "zfs-snapshot"}
    assert r["missing"] == ["criu-checkpoint"]
    assert r["is_true_save_state"] is False
    assert "PARTIAL" in r["note"]
    assert "pending the M057" in r["layers"]["criu-checkpoint"]["note"]


def test_capture_with_pid_is_true_save_state(env):
    r = SS.capture("s-pid")
    assert set(r["captured"]) == set(SS._LAYERS)
    assert r["missing"] == [] and r["is_true_save_state"] is True
    criu = r["layers"]["criu-checkpoint"]
    assert criu["pid"] == 4321
    assert criu["would_run"][:3] == ["criu", "dump", "--tree"]


def test_capture_memory_missing_when_no_memory_json(env, monkeypatch):
    monkeypatch.setattr(SS, "MEMORY_STATE", env / "does-not-exist.json")
    r = SS.capture("s-pid")
    assert "memory-record" in r["missing"] and r["is_true_save_state"] is False


def test_zfs_layer_reuses_rollback_points(env):
    r = SS.capture("s-a")
    zfs = r["layers"]["zfs-snapshot"]
    assert zfs["dataset_key"] == "agents"
    assert zfs["tag"].startswith("save-s-a-")
    # the tag must be a valid rollback-points snapshot tag (no '@' / '/' / spaces)
    assert SS._rp._SAFE_TAG.match(zfs["tag"])


# ── id validation + dry-run safety ────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["a/b", "a b", "$(id)", "../x", ""])
def test_unsafe_id_rejected(env, bad):
    r = SS.capture(bad)
    assert r["ok"] is False and "unsafe session id" in r["error"]


def test_unknown_id_rejected(env):
    r = SS.capture("s-none")
    assert r["ok"] is False and "no session resolved" in r["error"]


def test_dry_run_writes_no_manifest(env):
    SS.capture("s-pid")  # dry
    assert not (env / "save-state").exists()


def test_confirm_still_dry_under_env(env, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = SS.capture("s-pid", confirm=True)
    assert r["dry_run"] is True
    assert not (env / "save-state").exists()


# ── live capture writes the manifest + ledger ─────────────────────────────────

def test_live_capture_writes_manifest_and_ledger(env, monkeypatch):
    # no zfs/criu binaries in CI → those layers degrade gracefully; the manifest
    # + ledger + the 4 non-binary layers still land.
    r = SS.capture("s-a", confirm=True)
    assert r["ok"] is True and "manifest" in r
    man = json.loads(Path(r["manifest"]).read_text())
    assert man["id"] == "s-a" and "profile-state" in man["captured"]
    ledger = json.loads(SS.LEDGER.read_text().strip())
    assert ledger["verb"] == "save-state" and ledger["id"] == "s-a"


# ── restore plan ──────────────────────────────────────────────────────────────

def test_restore_requires_a_manifest(env):
    r = SS.restore("s-pid")
    assert r["ok"] is False and "no save-state manifest" in r["error"]


def test_restore_plan_from_manifest(env):
    SS.capture("s-pid", confirm=True)  # writes a manifest (with criu images_dir)
    r = SS.restore("s-pid")
    assert r["ok"] is True and r["dry_run"] is True
    assert r["plan"]["criu-checkpoint"]["would_run"][:2] == ["criu", "restore"]
    assert "@save-s-pid-" in r["plan"]["zfs-snapshot"]["target"]


# ── SDD-065 — per-session ZFS dataset preference ──────────────────────────────

def test_zfs_layer_prefers_per_session_dataset_path(env, monkeypatch):
    """A session carrying `dataset_path` (SDD-065 per-session child) snapshots THAT
    dataset directly, not the shared enum dataset."""
    reg = env / "sessions.json"
    reg.write_text(json.dumps({"sessions": [
        {"id": "s-ps", "state": "active", "dataset": "agents",
         "dataset_path": "tank/agents/s-ps", "pid": 5555},
    ]}))
    r = SS.capture("s-ps")
    zfs = r["layers"]["zfs-snapshot"]
    assert zfs["dataset_path"] == "tank/agents/s-ps"
    assert "dataset_key" not in zfs  # went the per-session path, not the enum
    assert zfs["result"]["target"] == f"tank/agents/s-ps@{zfs['tag']}"


def test_zfs_layer_enum_fallback_without_dataset_path(env):
    """Without `dataset_path` the shared enum dataset is used (the SDD-057 default —
    keeps the existing behavior)."""
    zfs = SS.capture("s-a")["layers"]["zfs-snapshot"]
    assert zfs["dataset_key"] == "agents" and "dataset_path" not in zfs
