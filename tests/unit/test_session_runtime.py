"""Unit tests for the SDD-058 M057 session-process runtime
`scripts/lifecycle/session-runtime.py`: the task-command producer that spawns +
PID/cgroup/dataset-tracks real session processes (systemd-run --scope) and
registers them in sessions.json — the producer that makes the SDD-057 save-state
`criu-checkpoint` layer capturable (partial 4/5 → true 5/5).

Covers: the start plan (systemd-run scope, argv-list, no shell), dataset-key
validation, DRY-RUN default (no registration), live registration with a
monkeypatched spawn, the registered pid round-tripping through session-registry,
stop→archived, and the END-TO-END proof that a runtime pid-session yields a true
5-layer save-state.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RT_PATH = REPO_ROOT / "scripts" / "lifecycle" / "session-runtime.py"
SS_PATH = REPO_ROOT / "scripts" / "lifecycle" / "save-state.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RT = _load(RT_PATH, "session_runtime")


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    reg = tmp_path / "sessions.json"
    reg.write_text(json.dumps({"sessions": []}))
    monkeypatch.setattr(RT, "SESSION_REGISTRY", reg)
    monkeypatch.setattr(RT._sr, "SESSION_REGISTRY", reg)
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    return reg


def _sessions(reg):
    return json.loads(reg.read_text())["sessions"]


# ── start (plan + validation) ─────────────────────────────────────────────────

def test_start_dry_run_emits_scope_plan(registry):
    r = RT.start(["sleep", "3600"])
    assert r["ok"] is True and r["dry_run"] is True
    assert r["would_run"][:2] == ["systemd-run", "--scope"]
    assert r["would_run"][-2:] == ["sleep", "3600"]  # argv-list, no shell
    assert r["id"].startswith("sess-")
    assert _sessions(registry) == []  # dry-run registers nothing


def test_start_rejects_unknown_dataset(registry):
    r = RT.start(["x"], dataset_key="nope")
    assert r["ok"] is False and "unknown dataset key" in r["error"]


def test_start_rejects_empty_task(registry):
    r = RT.start([])
    assert r["ok"] is False and "no task command" in r["error"]


# ── start (live registration — the producer) ──────────────────────────────────

def test_start_live_registers_pid_session(registry, monkeypatch):
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: 9999)
    r = RT.start(["sleep", "3600"], dataset_key="agents", confirm=True)
    assert r["ok"] is True and r["pid"] == 9999 and r["state"] == "active"
    sessions = _sessions(registry)
    assert len(sessions) == 1
    s = sessions[0]
    assert s["id"] == r["id"] and s["pid"] == 9999 and s["step"] == 1
    assert s["cgroup"].endswith(".scope") and s["dataset"] == "agents"
    assert s["task"] == "sleep 3600"


def test_start_live_spawn_failure(registry, monkeypatch):
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: None)
    r = RT.start(["sleep", "1"], confirm=True)
    assert r["ok"] is False and "spawn failed" in r["error"]
    assert _sessions(registry) == []  # nothing registered on spawn failure


def test_registered_pid_surfaces_through_registry(registry, monkeypatch):
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: 4321)
    r = RT.start(["agent-loop"], confirm=True)
    sess = next(s for s in RT.session_list() if s["id"] == r["id"])
    assert sess["pid"] == 4321 and sess["dataset"] == "agents"


# ── stop ──────────────────────────────────────────────────────────────────────

def test_stop_dry_run(registry, monkeypatch):
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: 7)
    sid = RT.start(["x"], confirm=True)["id"]
    r = RT.stop(sid)
    assert r["ok"] is True and r["dry_run"] is True
    assert r["would_run"][:2] == ["systemctl", "stop"]


def test_stop_live_archives(registry, monkeypatch):
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: 7)
    monkeypatch.setattr(RT, "_run", lambda cmd, **kw: "")
    sid = RT.start(["x"], confirm=True)["id"]
    r = RT.stop(sid, confirm=True)
    assert r["ok"] is True and r["state"] == "archived"
    assert next(s for s in _sessions(registry) if s["id"] == sid)["state"] == "archived"


def test_stop_unknown_and_unsafe(registry):
    assert RT.stop("sess-nope")["ok"] is False
    assert "unsafe" in RT.stop("a/b")["error"]


# ── END-TO-END: a runtime pid-session yields a true 5/5 save-state ─────────────

def test_runtime_session_enables_true_save_state(registry, tmp_path, monkeypatch):
    """The whole point: a runtime-registered pid-session makes the SDD-057
    save-state criu-checkpoint layer capturable → is_true_save_state == True."""
    mem = tmp_path / "memory.json"
    mem.write_text(json.dumps({"pending": []}))
    monkeypatch.setattr(RT, "_spawn_scope", lambda cmd, unit: 2222)
    sid = RT.start(["agent"], dataset_key="context", confirm=True)["id"]

    SS = _load(SS_PATH, "save_state_e2e")
    monkeypatch.setattr(SS, "SESSION_REGISTRY", registry)
    monkeypatch.setattr(SS._sr, "SESSION_REGISTRY", registry)
    monkeypatch.setattr(SS, "MEMORY_STATE", mem)
    monkeypatch.setenv("SOVEREIGN_OS_ACTIVE_PROFILE", "private")
    cap = SS.capture(sid)
    assert cap["is_true_save_state"] is True
    assert set(cap["captured"]) == set(SS._LAYERS)
    assert cap["layers"]["criu-checkpoint"]["pid"] == 2222
