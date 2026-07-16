"""SDD-722 — adapter-dataset curator contract (the E0444 dataset producer).

adapter-dataset.py is the UPSTREAM half of the M046 loop (traces → dataset →
TRAIN → register → gate → transport → serve). Unlike adapter-train (a GPU
planner), curation is pure I/O and runs in CI, so these pin the real behaviour:

  1. present + executable + stdlib-only (no torch/datasets/transformers).
  2. reuses goal-driver's DONE_SENTINEL as the success label (SDD-719).
  3. success filter: outcome==success OR final assistant msg carries the
     sentinel; failures excluded in label=success, included in label=all.
  4. rails: too-short dropped (min-turns), duplicates deduped, sentinel stripped
     from the emitted target.
  5. DRY-RUN default — no file written without --apply; --apply writes JSONL.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "inference" / "adapter-dataset.py"


def _load():
    spec = importlib.util.spec_from_file_location("_adapter_dataset", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "adapter-dataset.py must be executable"


def test_stdlib_only_no_heavy_import():
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import torch", "import datasets", "import transformers", "import trl"):
        assert banned not in body, f"adapter-dataset.py must stay stdlib-only ({banned})"


def test_reuses_goal_driver_sentinel():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "goal-driver.py" in body, "must import the success sentinel from goal-driver"
    mod = _load()
    assert mod.DONE_SENTINEL == "[[GOAL_DONE]]", "success label is the goal loop's completion token"


def test_success_filter_and_dedup():
    mod = _load()
    traces = [
        {"messages": [{"role": "user", "content": "fix"},
                      {"role": "assistant", "content": "done [[GOAL_DONE]]"}]},
        {"messages": [{"role": "user", "content": "fix"},
                      {"role": "assistant", "content": "done [[GOAL_DONE]]"}]},  # dup
        {"messages": [{"role": "user", "content": "x"},
                      {"role": "assistant", "content": "nope"}], "outcome": "failure"},
        {"messages": [{"role": "user", "content": "hi"}]},  # too short
        {"messages": [{"role": "user", "content": "ship"},
                      {"role": "assistant", "content": "ok"}], "outcome": "success"},
    ]
    res = mod.curate(traces, label="success", min_turns=2)
    assert res["kept_count"] == 2, res  # deduped success + explicit success
    assert res["dropped"]["too_short"] == 1
    assert res["dropped"]["not_success"] == 1
    assert res["dropped"]["duplicate"] == 1


def test_sentinel_stripped_from_target():
    mod = _load()
    res = mod.curate(
        [{"messages": [{"role": "user", "content": "go"},
                       {"role": "assistant", "content": "finished [[GOAL_DONE]]"}]}],
        label="success", min_turns=2,
    )
    target = res["kept"][0]["messages"][-1]["content"]
    assert mod.DONE_SENTINEL not in target, "the completion token must not leak into the training target"
    assert target == "finished"


def test_label_all_includes_failures():
    mod = _load()
    traces = [
        {"messages": [{"role": "user", "content": "a"},
                      {"role": "assistant", "content": "b"}], "outcome": "failure"},
    ]
    assert mod.curate(traces, label="success")["kept_count"] == 0
    allres = mod.curate(traces, label="all")
    assert allres["kept_count"] == 1
    assert allres["kept"][0]["label"] == "failure"


def test_dry_run_default_no_write(tmp_path):
    traces = tmp_path / "t.jsonl"
    traces.write_text(json.dumps(
        {"messages": [{"role": "user", "content": "go"},
                      {"role": "assistant", "content": "done [[GOAL_DONE]]"}]}) + "\n",
        encoding="utf-8")
    out = tmp_path / "ds.jsonl"
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "curate", "a",
         "--traces", str(traces), "--out", str(out)],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0, r.stderr
    assert not out.exists(), "DRY-RUN must not write the dataset"
    assert "DRY-RUN" in r.stdout

    r2 = subprocess.run(
        [sys.executable, str(SCRIPT), "curate", "a",
         "--traces", str(traces), "--out", str(out), "--apply"],
        capture_output=True, text=True, timeout=15,
    )
    assert r2.returncode == 0, r2.stderr
    assert out.exists(), "--apply must write the dataset"
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert line["messages"][-1]["content"] == "done"
