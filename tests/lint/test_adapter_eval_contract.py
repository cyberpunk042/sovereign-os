"""SDD-724 — adapter-eval runner contract (the MS041 eval GATE-PRODUCER).

adapter-gate.py's eval gate reads a PASSING eval record for the adapter from
evals.jsonl and honest-defers when none exists (SB-077 — never fabricate).
Nothing wrote that record. adapter-eval.py runs a benchmark suite and writes it.
The scoring/grading/record-assembly is pure and CI-tested; only querying the
served model is hardware-gated (injected Responder). These pin:

  1. present + executable + stdlib-only (no torch/transformers).
  2. reuses eval-tracker (store + the _passed rule + the record shape the gate
     and D-10 dashboard read).
  3. graders: contains (default, case-insensitive) / exact / regex (bad regex
     fails safe).
  4. score = fraction passed; passed = score >= threshold; the runner's verdict
     AGREES with eval-tracker._passed (gate_agrees) — they can't disagree.
  5. the written record is discoverable by eval-tracker.load_runs + _passed for
     that adapter_id (exactly what the gate's _eval_evidence does); bounded +
     atomic append.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "inference" / "adapter-eval.py"
TRACKER = REPO_ROOT / "scripts" / "observability" / "eval-tracker.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_present_executable_stdlib():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "adapter-eval.py must be executable"
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import torch", "import transformers", "import trl"):
        assert banned not in body, f"adapter-eval.py must stay stdlib-only ({banned})"


def test_reuses_eval_tracker():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "eval-tracker.py" in body, "must reuse the eval-tracker store + pass rule"
    mod = _load("_ae_reuse", SCRIPT)
    assert hasattr(mod, "_et") and hasattr(mod._et, "_passed")


def test_graders():
    mod = _load("_ae_grade", SCRIPT)
    assert mod.grade("It is Paris.", "paris", "contains") is True
    assert mod.grade("nope", "paris", "contains") is False
    assert mod.grade("Paris", "paris", "exact") is True
    assert mod.grade("Paris, France", "paris", "exact") is False
    assert mod.grade("hello", "^h", "regex") is True
    assert mod.grade("x", "(", "regex") is False, "a bad regex must fail safe, not raise"


def test_score_and_gate_agreement():
    mod = _load("_ae_score", SCRIPT)
    suite = [
        {"prompt": "2+2?", "expect": "4", "grader": "contains"},
        {"prompt": "cap FR?", "expect": "paris", "grader": "contains"},
        {"prompt": "say", "expect": "^h", "grader": "regex"},
    ]
    answers = iter(["the answer is 4", "It is Paris.", "goodbye"])  # 2/3 pass
    res = mod.run_suite("a", suite, lambda _p: next(answers), threshold=0.5)
    assert res["score"] == round(2 / 3, 4)
    assert res["passed"] is True
    assert res["record"]["gate_agrees"] is True, "runner verdict must agree with eval-tracker._passed"
    assert res["record"]["task"] == "adapter-eval", "load_runs drops records without a task"
    assert res["record"]["adapter_id"] == "a"


def test_below_threshold_fails():
    mod = _load("_ae_fail", SCRIPT)
    suite = [{"prompt": "x", "expect": "foo", "grader": "contains"}] * 4
    res = mod.run_suite("a", suite, lambda _p: "nope", threshold=0.5)  # 0/4
    assert res["score"] == 0.0 and res["passed"] is False
    assert res["record"]["gate_agrees"] is True


def test_record_discoverable_by_gate(tmp_path):
    """The written record must be what the gate's _eval_evidence finds: filter by
    adapter_id, take latest, eval-tracker._passed(latest) is True."""
    mod = _load("_ae_disc", SCRIPT)
    et = _load("_et_disc", TRACKER)
    store = tmp_path / "evals.jsonl"
    suite = [{"prompt": "q", "expect": "yes", "grader": "contains"}]
    res = mod.run_suite("admin-lora", suite, lambda _p: "yes", threshold=0.5)
    mod.append_record(res["record"], store=store)
    runs = [r for r in et.load_runs(store) if r.get("adapter_id") == "admin-lora"]
    assert len(runs) == 1 and et._passed(runs[-1]) is True
    assert not store.with_suffix(store.suffix + ".tmp").exists(), "atomic append leaves no .tmp"


def test_append_is_bounded(tmp_path, monkeypatch):
    mod = _load("_ae_bound", SCRIPT)
    monkeypatch.setattr(mod._et, "MAX_RUNS", 3)
    store = tmp_path / "evals.jsonl"
    for i in range(5):
        mod.append_record({"task": "adapter-eval", "adapter_id": "a", "n": i,
                           "score": 1.0, "passed": True}, store=store)
    kept = [json.loads(x)["n"] for x in store.read_text(encoding="utf-8").splitlines()]
    assert kept == [2, 3, 4], "append must keep only the last MAX_RUNS records"
