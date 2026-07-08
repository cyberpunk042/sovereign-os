"""Unit tests for the SDD-050 snapshot write actuation in
`scripts/lifecycle/rollback-points.py`: snapshot `create`, `prune` (floor +
refuse-by-default + `--force`), and the `recent-N` rollback resolution.

Covers the security-critical, mechanism-independent core: the dataset ENUM
resolution (short key → real '/'-bearing path, never a '/'-arg), the `_SAFE_TAG`
validation (no '@'/'/'/spaces), the prune floor (never the latest; newest-N held
back without --force), and DRY-RUN default (no `zfs` mutation on import/without
--confirm).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "lifecycle" / "rollback-points.py"


def _load():
    spec = importlib.util.spec_from_file_location("rollback_points", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RP = _load()


def _snaps(now: float):
    """A fake newest-first inventory: one dataset (tank/context) with 5 snaps at
    ages 0 / 1 / 10 / 20 / 30 days, plus rpool/sovereign-os with 2 fresh snaps."""
    day = 86400.0
    ctx = [
        {"id": f"tank/context@s{i}", "dataset": "tank/context",
         "tag": f"s{i}", "_creation": now - age * day}
        for i, age in enumerate([0, 1, 10, 20, 30])
    ]
    osd = [
        {"id": f"rpool/sovereign-os@o{i}", "dataset": "rpool/sovereign-os",
         "tag": f"o{i}", "_creation": now - age * day}
        for i, age in enumerate([0, 2])
    ]
    return ctx + osd


# ── create ───────────────────────────────────────────────────────────────────

def test_create_dry_run_resolves_dataset_key(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    r = RP.create("os", "manual-2026-07-08")  # no --confirm → dry
    assert r["dry_run"] is True
    assert r["target"] == "rpool/sovereign-os@manual-2026-07-08"
    assert r["would_run"] == ["zfs", "snapshot", "rpool/sovereign-os@manual-2026-07-08"]


def test_create_unknown_dataset_key_rejected():
    r = RP.create("no-such", "tag")
    assert r["ok"] is False and "unknown dataset key" in r["error"]


@pytest.mark.parametrize("bad", ["bad@tag", "a/b", "a b", "../x", "$(id)", ""])
def test_create_invalid_tag_rejected(bad):
    r = RP.create("os", bad)
    assert r["ok"] is False and "invalid tag" in r["error"]


def test_create_never_passes_slash_dataset_as_arg():
    """The '/'-bearing dataset path is resolved internally — the enum KEY the
    control passes is '/'-free."""
    assert "/" not in "os" and RP._DATASETS["os"] == "rpool/sovereign-os"


def test_create_live_runs_zfs_snapshot(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    calls = []
    monkeypatch.setattr(RP, "_run", lambda cmd, **kw: (calls.append(cmd) or ""))
    r = RP.create("context", "pre-x", confirm=True)
    assert r["ok"] is True
    assert r["ran"] == ["zfs", "snapshot", "tank/context@pre-x"]
    assert calls == [["zfs", "snapshot", "tank/context@pre-x"]]


def test_create_confirm_still_dry_under_env(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = RP.create("os", "x", confirm=True)
    assert r["dry_run"] is True and "ran" not in r


# ── prune (floor + refuse-by-default + --force) ───────────────────────────────

def test_prune_dry_run_floor_withholds_below_floor(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    now = 1_000_000_000.0
    monkeypatch.setattr(RP, "time", type("T", (), {"time": staticmethod(lambda: now)}))
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(now))
    r = RP.prune(5)  # retain 5d, floor default 3, no --confirm → dry
    assert r["dry_run"] is True
    # tank/context ages 0/1/10/20/30 → old(>5d) are idx2(10d),idx3(20d),idx4(30d)
    # idx0 never; idx2 is inside the newest-3 floor → withheld; idx3,idx4 destroyed
    assert r["to_destroy"] == ["tank/context@s3", "tank/context@s4"]
    assert r["withheld_by_floor"] == ["tank/context@s2"]
    assert r["refused"] is True
    assert "tank/context@s0" not in r["to_destroy"]  # never the latest


def test_prune_force_prunes_below_floor_but_never_latest(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    now = 1_000_000_000.0
    monkeypatch.setattr(RP, "time", type("T", (), {"time": staticmethod(lambda: now)}))
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(now))
    r = RP.prune(5, force=True)
    assert r["to_destroy"] == ["tank/context@s2", "tank/context@s3", "tank/context@s4"]
    assert r["withheld_by_floor"] == []
    assert r["refused"] is False
    assert "tank/context@s0" not in r["to_destroy"]  # latest still absolute-safe


def test_prune_live_runs_zfs_destroy(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    now = 1_000_000_000.0
    monkeypatch.setattr(RP, "time", type("T", (), {"time": staticmethod(lambda: now)}))
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(now))
    calls = []
    monkeypatch.setattr(RP, "_run", lambda cmd, **kw: (calls.append(cmd) or ""))
    r = RP.prune(5, confirm=True)
    assert r["ok"] is True and r["failed"] == []
    assert calls == [["zfs", "destroy", "tank/context@s3"],
                     ["zfs", "destroy", "tank/context@s4"]]


def test_prune_invalid_retain_days():
    assert RP.prune("abc")["ok"] is False
    assert RP.prune(-1)["ok"] is False


# ── recent-N rollback resolution ──────────────────────────────────────────────

def test_apply_recent_n_resolves_nth_newest(monkeypatch):
    now = 1_000_000_000.0
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(now))
    r = RP.apply("recent-3")  # dry (no confirm) → 3rd-newest overall = s2
    assert r["dry_run"] is True
    assert r["resolved"] == "tank/context@s2"
    assert r["would_run"] == ["zfs", "rollback", "-r", "tank/context@s2"]


def test_apply_recent_out_of_bounds_unresolved(monkeypatch):
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(1_000_000_000.0))
    r = RP.apply("recent-99")
    assert r["resolved"] is None


def test_apply_latest_still_resolves(monkeypatch):
    monkeypatch.setattr(RP, "collect_snapshots", lambda: _snaps(1_000_000_000.0))
    r = RP.apply("latest")
    assert r["resolved"] == "tank/context@s0"
