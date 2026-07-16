#!/usr/bin/env python3
"""scripts/inference/adapter-train.py — plan a LoRA/QLoRA training run that
produces a real M046 adapter (SDD-721; the training producer the M046 foundry
deferred to "Stage 4"). Closes the last gap in the loop:

  traces → dataset → **TRAIN (here)** → register → MS041 gate (adapter-gate) →
  transport (adapter-transport, SDD-716) → serve `--lora` (SDD-715) → rollback.

A **planner** (like adapter-transport.py): it prints the exact commands —
`adapter-decide register` (mint the pending adapter) + the trainer invocation +
where the output adapter lands — DRY-RUN by default; `--apply` runs them. The
actual GPU training is SAIN-01-side (E0446: "4090 → train small LoRAs / QLoRA")
and cannot be CI-verified (no GPUs/weights), so the plan construction is what is
tested; the operator (or a SAIN-01 job) applies it.

TERNARY CAVEAT (load-bearing): you CANNOT LoRA-train a packed ternary/GGUF base.
The trainers (unsloth / TRL / PEFT) train an FP16 LoRA on the **unpacked**
safetensors base (e.g. `prism-ml/Ternary-Bonsai-27B-unpacked`), base frozen; the
adapter is then served over the ternary GGUF (SDD-715). The planner WARNS if the
`--base` looks like a `.gguf` / packed-ternary ref.

Trainer metadata (install/detect/hardware-fit) is read from the existing
`scripts/models/toolchains.py` registry (unsloth is catalogued there) — never
reinvented. Sovereignty: stdlib-only; DRY-RUN default (no host mutation, no GPU
job without `--apply`); reuses the adapter registry helpers.

  adapter-train.py plan <id> --base <unpacked> --dataset <path>
                   [--method qlora|lora] [--trainer unsloth|trl] [--epochs N] [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]

# Reuse the toolchains registry (single source of truth for trainer metadata).
_tc_spec = importlib.util.spec_from_file_location(
    "_toolchains_for_train", _REPO_ROOT / "scripts" / "models" / "toolchains.py"
)
_tc = importlib.util.module_from_spec(_tc_spec)  # type: ignore[arg-type]
_tc_spec.loader.exec_module(_tc)  # type: ignore[union-attr]

ADAPTERS_DIR = "/var/lib/sovereign-os/adapters"
ADAPTER_DECIDE = _HERE / "adapter-decide.py"

# QLoRA defaults (unsloth-standard) — operator-overridable.
QLORA_DEFAULTS = {"r": 16, "alpha": 32, "dropout": 0.05, "lr": 2e-4, "load_in_4bit": True}


def _toolchain(name: str) -> dict[str, Any] | None:
    for tool in getattr(_tc, "TOOLCHAINS", []):
        if tool.get("name") == name:
            return tool
    return None


def _base_warning(base: str) -> str | None:
    low = base.lower()
    if low.endswith(".gguf") or "gguf" in low or "-q2_0" in low or "1.58bit" in low:
        return (
            f"base {base!r} looks like a packed ternary/GGUF model — you cannot "
            "LoRA-train it. Use the UNPACKED safetensors base (e.g. "
            "prism-ml/Ternary-Bonsai-27B-unpacked); the adapter serves over the GGUF."
        )
    return None


def plan(
    adapter_id: str,
    base: str,
    dataset: str,
    *,
    method: str = "qlora",
    trainer: str = "unsloth",
    epochs: int = 1,
) -> dict[str, Any]:
    tool = _toolchain(trainer)
    out_dir = f"{ADAPTERS_DIR}/{adapter_id}/train"
    hp = dict(QLORA_DEFAULTS)
    if method == "lora":
        hp["load_in_4bit"] = False

    warnings = [w for w in (_base_warning(base),) if w]
    if not tool:
        warnings.append(f"trainer {trainer!r} is not in the toolchains registry")
    elif "CUDA" in (tool.get("hardware_fit") or []):
        warnings.append(f"{trainer} needs CUDA — run this on SAIN-01 (E0446), not the serving box")

    # The trainer invocation is a scaffold: the GPU-side training entry point is
    # operator-supplied (Stage 4). We emit the intended command + hyperparams so
    # the operator/job runs it on SAIN-01.
    train_cmd = [
        "python3", f"scripts/inference/train/{trainer}-lora.py",
        "--base", base, "--dataset", dataset, "--method", method,
        "--epochs", str(epochs), "--r", str(hp["r"]), "--alpha", str(hp["alpha"]),
        "--lr", str(hp["lr"]), "--out", out_dir,
    ]
    if hp.get("load_in_4bit"):
        train_cmd.append("--load-in-4bit")

    return {
        "adapter_id": adapter_id,
        "base_model": base,
        "dataset": dataset,
        "method": method,
        "trainer": trainer,
        "epochs": epochs,
        "hyperparams": hp,
        "output_dir": out_dir,
        "install_hint": (tool or {}).get("install_hint"),
        "warnings": warnings,
        "steps": [
            {"kind": "register",
             "cmd": ["python3", str(ADAPTER_DECIDE), "register", adapter_id,
                     "--base", base, "--training", method]},
            {"kind": "train", "cmd": train_cmd},
        ],
        "next": "adapter-gate (MS041) → adapter-transport (SDD-716) → serve --lora (SDD-715)",
    }


def _emit(obj: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
        return
    for w in obj.get("warnings", []):
        print(f"WARNING: {w}")
    print(f"# train adapter {obj['adapter_id']}  ({obj['trainer']} / {obj['method']}, "
          f"{obj['epochs']} epoch(s))")
    print(f"#   base    : {obj['base_model']}")
    print(f"#   dataset : {obj['dataset']}")
    print(f"#   output  : {obj['output_dir']}")
    for step in obj["steps"]:
        print(f"  {step['kind']}: {' '.join(step['cmd'])}")
    print(f"  next: {obj['next']}")


def _run(steps: list[dict[str, Any]]) -> int:
    import subprocess

    for step in steps:
        print(f"+ {' '.join(step['cmd'])}")
        rc = subprocess.run(step["cmd"], check=False).returncode
        if rc != 0:
            print(f"step {step['kind']} failed (rc={rc}); stopping", file=sys.stderr)
            return rc
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="plan a LoRA/QLoRA training run (DRY-RUN unless --apply)")
    p.add_argument("adapter_id")
    p.add_argument("--base", required=True, help="UNPACKED safetensors base (not a ternary GGUF)")
    p.add_argument("--dataset", required=True)
    p.add_argument("--method", choices=["qlora", "lora"], default="qlora")
    p.add_argument("--trainer", default="unsloth")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--json", action="store_true")
    p.add_argument("--apply", action="store_true", help="execute the plan (needs the SAIN-01 GPUs)")
    args = ap.parse_args(argv)

    if args.cmd == "plan":
        obj = plan(args.adapter_id, args.base, args.dataset,
                   method=args.method, trainer=args.trainer, epochs=args.epochs)
        _emit(obj, args.json)
        return _run(obj["steps"]) if args.apply else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
