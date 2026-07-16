"""SDD-721 — adapter-train planner contract (the M046 training producer).

adapter-train.py is the training-command PLANNER that closes the last gap in the
M046 loop (traces → dataset → TRAIN → register → gate → transport → serve). GPU
training is SAIN-01-side and can't run in CI, so these pin the plan SHAPE + the
two load-bearing correctness rules:

  1. present + executable + stdlib-only (no torch/unsloth import at module load).
  2. reuses toolchains.py (trainer metadata) + adapter-decide (register step).
  3. plan emits [register, train]; output under /adapters/<id>/train; the train
     step carries the base + dataset + output + QLoRA hyperparams.
  4. the TERNARY CAVEAT: a packed ternary/GGUF `--base` WARNS (you can't LoRA-
     train it; use the unpacked base).
  5. DRY-RUN default — no execution without --apply.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "inference" / "adapter-train.py"


def _load():
    spec = importlib.util.spec_from_file_location("_adapter_train", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "adapter-train.py must be executable"


def test_stdlib_only_no_heavy_import():
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import torch", "import unsloth", "import transformers", "import trl"):
        assert banned not in body, f"adapter-train.py must not import a trainer at load ({banned})"


def test_reuses_toolchains_and_adapter_decide():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "toolchains.py" in body, "must read trainer metadata from toolchains.py"
    assert "adapter-decide.py" in body, "must emit the adapter-decide register step"


def test_plan_shape_unpacked_base():
    mod = _load()
    p = mod.plan("my-adapter", "prism-ml/Ternary-Bonsai-27B-unpacked",
                 "/data/ds.jsonl", method="qlora", trainer="unsloth")
    kinds = [s["kind"] for s in p["steps"]]
    assert kinds == ["register", "train"], f"unexpected steps: {kinds}"
    assert p["output_dir"].endswith("/adapters/my-adapter/train")
    train = next(s for s in p["steps"] if s["kind"] == "train")["cmd"]
    assert "--base" in train and "prism-ml/Ternary-Bonsai-27B-unpacked" in train
    assert "--dataset" in train and "/data/ds.jsonl" in train
    assert "--out" in train and p["output_dir"] in train
    assert p["hyperparams"]["r"] == 16, "QLoRA rank default"


def test_ternary_gguf_base_warns():
    mod = _load()
    p = mod.plan("bad", "Ternary-Bonsai-27B-Q2_0.gguf", "/d", method="qlora")
    assert any("packed ternary" in w or "gguf" in w.lower() for w in p["warnings"]), (
        "a packed ternary/GGUF base must warn (can't LoRA-train it)"
    )


def test_qlora_uses_4bit_lora_does_not():
    mod = _load()
    q = mod.plan("a", "base-unpacked", "/d", method="qlora")
    lo = mod.plan("b", "base-unpacked", "/d", method="lora")
    assert q["hyperparams"]["load_in_4bit"] is True
    assert lo["hyperparams"]["load_in_4bit"] is False


def test_dry_run_default_no_execution():
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "plan", "a",
         "--base", "base-unpacked", "--dataset", "/d"],
        capture_output=True, text=True, timeout=15,
    )
    assert out.returncode == 0, out.stderr
    assert "train:" in out.stdout and "register:" in out.stdout
