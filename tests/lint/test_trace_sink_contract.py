"""SDD-723 — the goal-loop trace sink contract (the M046 trace SOURCE).

goal-driver.py's loop is where a goal's success/failure is KNOWN (done →
success, paused → failure), so it is the natural place to emit training traces
that adapter-dataset.py (SDD-722) then curates. These pin:

  1. run_loop accepts a trace_sink and emits ONE trajectory record at
     termination — messages alternate user/assistant across iterations.
  2. outcome is derived from the terminal state: done → success, else failure.
  3. the record shape is exactly what adapter-dataset.py curates
     ({"messages":[…], "outcome":…, "goal":…}) — proven by feeding it through.
  4. append_trace is bounded (keeps last max_lines) + atomic (no .tmp left) so
     an always-on loop can't grow the log unbounded.
  5. --no-trace / trace_sink=None emits nothing.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "scripts" / "inference" / "goal-driver.py"
CTL = REPO_ROOT / "scripts" / "inference" / "goal-ctl.py"
DATASET = REPO_ROOT / "scripts" / "inference" / "adapter-dataset.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _driver_with_state(monkeypatch, tmp_path):
    """Load goal-driver with goal state redirected to a temp file (env is read at
    import, so set it before loading both modules)."""
    monkeypatch.setenv("SOVEREIGN_OS_AGENT_STATE", str(tmp_path / "agent-state.json"))
    gd = _load("_gd_trace", DRIVER)
    return gd


def _scripted(steps):
    it = iter(steps)
    return lambda _prompt: next(it)


def test_success_trajectory_emitted_and_curatable(monkeypatch, tmp_path):
    gd = _driver_with_state(monkeypatch, tmp_path)
    gd._goal.set_goal("harden the gateway", None)
    captured: list[dict] = []
    res = gd.run_loop(
        _scripted([
            {"text": "looked at config", "done": False},
            {"text": "applied hardening [[GOAL_DONE]]", "done": True},
        ]),
        max_iters=50, no_progress_limit=3, trace_sink=captured.append,
    )
    assert res["stop_reason"] == "done"
    assert len(captured) == 1
    rec = captured[0]
    assert rec["outcome"] == "success"
    assert rec["goal"] == "harden the gateway"
    roles = [m["role"] for m in rec["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"], roles

    # the record is exactly what adapter-dataset.py curates
    ds = _load("_ds_for_trace", DATASET)
    curated = ds.curate([rec], label="success", min_turns=2)
    assert curated["kept_count"] == 1
    assert ds.DONE_SENTINEL not in curated["kept"][0]["messages"][-1]["content"]


def test_paused_trajectory_is_failure(monkeypatch, tmp_path):
    gd = _driver_with_state(monkeypatch, tmp_path)
    gd._goal.set_goal("do the thing", None)
    captured: list[dict] = []
    res = gd.run_loop(
        _scripted([{"text": "stuck", "done": False}] * 5),
        max_iters=50, no_progress_limit=2, trace_sink=captured.append,
    )
    assert res["stop_reason"] == "no-progress"
    assert captured and captured[0]["outcome"] == "failure"


def test_no_sink_emits_nothing(monkeypatch, tmp_path):
    gd = _driver_with_state(monkeypatch, tmp_path)
    gd._goal.set_goal("x", None)
    # trace_sink=None (the --no-trace path) must not raise and must not write.
    res = gd.run_loop(_scripted([{"text": "done [[GOAL_DONE]]", "done": True}]),
                      max_iters=50, no_progress_limit=3, trace_sink=None)
    assert res["stop_reason"] == "done"


def test_append_trace_is_bounded_and_atomic(monkeypatch, tmp_path):
    gd = _driver_with_state(monkeypatch, tmp_path)
    log = tmp_path / "traces" / "agentic.jsonl"
    for i in range(5):
        gd.append_trace({"n": i}, path=log, max_lines=3)
    kept = [json.loads(x)["n"] for x in log.read_text(encoding="utf-8").splitlines()]
    assert kept == [2, 3, 4], "must keep only the last max_lines records"
    assert not (tmp_path / "traces" / "agentic.jsonl.tmp").exists(), "atomic write leaves no .tmp"


def test_trace_log_default_path_and_stdlib(monkeypatch, tmp_path):
    gd = _driver_with_state(monkeypatch, tmp_path)
    assert str(gd.TRACE_LOG).endswith("/traces/agentic.jsonl")
    body = DRIVER.read_text(encoding="utf-8")
    for banned in ("import torch", "import requests", "import numpy"):
        assert banned not in body, f"goal-driver must stay stdlib-only ({banned})"
