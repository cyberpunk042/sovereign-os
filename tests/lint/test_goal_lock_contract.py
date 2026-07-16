"""SDD-719 — /goal lock + loop-until-goal contract (implementation slice 1).

Proves the operator-facing goal state + the loop-until-goal guards without a
model (a scripted responder drives the loop — the SDD-712 pattern):

  - goal-ctl verbs: set / show / pause·resume·done·abandon / progress.
  - the goal `text` is SACROSANCT — progress/iterations never rewrite it.
  - loop-until-goal stops on done / max-iters / no-progress, and pauses (not
    abandons) the goal on the two guards.
  - the driver is a no-op when no goal is active.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_CTL = REPO_ROOT / "scripts" / "inference" / "goal-ctl.py"
GOAL_DRIVER = REPO_ROOT / "scripts" / "inference" / "goal-driver.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path):
    """Fresh goal-ctl + goal-driver pointed at a tmp state file."""
    state = tmp_path / "agent-state.json"
    ctl = _load(GOAL_CTL, "_goal_ctl_test")
    ctl.STATE_PATH = state
    drv = _load(GOAL_DRIVER, "_goal_driver_test")
    drv._goal.STATE_PATH = state  # the driver's imported goal-ctl instance
    return ctl, drv


def test_scripts_present_and_executable():
    import os
    for p in (GOAL_CTL, GOAL_DRIVER):
        assert p.is_file(), f"missing {p}"
        assert os.access(p, os.X_OK), f"{p.name} must be executable"


def test_set_show_and_status_verbs(env):
    ctl, _ = env
    assert ctl.set_goal("ship the dual-Turing serving stack", plan=["build", "flash"]) == 0
    g = ctl._get_goal()
    assert g["text"] == "ship the dual-Turing serving stack"
    assert g["status"] == "active" and g["plan"] == ["build", "flash"]
    assert ctl._set_status("paused") == 0 and ctl._get_goal()["status"] == "paused"
    assert ctl._set_status("active") == 0 and ctl._get_goal()["status"] == "active"


def test_goal_text_is_sacrosanct(env):
    ctl, _ = env
    ctl.set_goal("verbatim objective", plan=None)
    ctl.add_progress("did a thing")
    ctl.add_progress("did another thing")
    g = ctl._get_goal()
    assert g["text"] == "verbatim objective", "progress must never rewrite the goal text"
    assert g["iterations"] == 2 and g["last_progress"] == "did another thing"


def test_loop_stops_on_done(env):
    ctl, drv = env
    ctl.set_goal("achieve X", plan=None)
    calls = {"n": 0}

    def responder(prompt):
        calls["n"] += 1
        # progress on pass 1, completion on pass 2
        if calls["n"] == 1:
            return {"text": "step one done", "done": False}
        return {"text": f"finished {drv.DONE_SENTINEL}", "done": True}

    out = drv.run_loop(responder, max_iters=50, no_progress_limit=3)
    assert out["stop_reason"] == "done" and out["final_status"] == "done"
    assert ctl._get_goal()["status"] == "done"


def test_loop_stops_on_max_iters(env):
    ctl, drv = env
    ctl.set_goal("open-ended goal", plan=None)
    n = {"i": 0}

    def responder(prompt):
        n["i"] += 1
        return {"text": f"progress {n['i']}", "done": False}  # always new, never done

    out = drv.run_loop(responder, max_iters=5, no_progress_limit=99)
    assert out["stop_reason"] == "max-iters" and out["final_status"] == "paused"
    assert ctl._get_goal()["status"] == "paused", "guard pauses (not abandons) the goal"


def test_loop_stops_on_no_progress(env):
    ctl, drv = env
    ctl.set_goal("stuck goal", plan=None)

    def responder(prompt):
        return {"text": "same stuck answer", "done": False}  # never changes → no progress

    out = drv.run_loop(responder, max_iters=50, no_progress_limit=3)
    assert out["stop_reason"] == "no-progress" and out["final_status"] == "paused"


def test_driver_noop_without_active_goal(env):
    ctl, drv = env
    # no goal at all
    out = drv.run_loop(lambda p: {"text": "x", "done": True}, max_iters=50, no_progress_limit=3)
    assert out["stop_reason"] == "not-active"
    # a paused goal is also not pursued
    ctl.set_goal("g", plan=None)
    ctl._set_status("paused")
    out = drv.run_loop(lambda p: {"text": "x", "done": True}, max_iters=50, no_progress_limit=3)
    assert out["stop_reason"] == "not-active"


def test_build_prompt_quotes_goal_and_asks_for_sentinel(env):
    _, drv = env
    p = drv.build_prompt({"text": "do the thing", "plan": ["a"], "last_progress": "started"})
    assert "do the thing" in p and drv.DONE_SENTINEL in p and "started" in p
