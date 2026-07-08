#!/usr/bin/env python3
"""scripts/models/fine_tune.py — R244 (SDD-026 Z-2 fine-tune expansion).

Operator-named (verbatim, 2026-05-17 expansion): "download, fine-tune,
parameters, build, run, use and train and adapt and use and eval and
etc."

R232 ships the EVAL surface. R244 ships the FINE-TUNE planner half:
given a base model + a dataset + a method, emit the operator-runnable
harness invocation + record the intent in a JSONL state file so the
dashboard shows "last fine-tune run X hours ago, base=Y, method=Z".

Cycle-8 SEED scope (mirrors R232 eval design):
  - declarative METHOD catalog (4 entries: lora-unsloth / qlora-trl /
    sft-trl / dpo-trl) — each binds operator-friendly name to harness
    + harness_args_template + applicable_base_classes + cost estimate;
  - `fine-tune plan <base> --method M --dataset D` — emit the harness
    invocation + recommended hyperparameters + cost (preview);
  - `fine-tune run <base> --method M --dataset D [--dry-run]` —
    execute (DRY-RUN-default in SEED; harness execution lands when
    operator has unsloth/trl + SAIN-01 GPUs available);
  - `fine-tune history [--base B] [--method M]` — render the JSONL
    state file.

State file: /var/lib/sovereign-os/fine-tune.jsonl (env override:
SOVEREIGN_OS_FINE_TUNE_STATE). One JSON line per invocation.

Exit codes:
  0  command succeeded (plan / dry-run / history rendered)
  1  fine-tune execution failed (only on `run` without --dry-run)
  2  usage error / unknown base / unknown method
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR PyYAML missing — install with `pip install PyYAML`", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "models" / "catalog.yaml"
DEFAULT_STATE = Path("/var/lib/sovereign-os/fine-tune.jsonl")


def resolve_state_path() -> Path:
    env = os.environ.get("SOVEREIGN_OS_FINE_TUNE_STATE")
    return Path(env) if env else DEFAULT_STATE


# Fine-tune method catalog — each entry binds an operator-friendly
# name to a backing harness + a hyperparameter template + applicable
# base-model classes. Cost is wall-clock estimate on SAIN-01.
METHODS: dict[str, dict[str, Any]] = {
    "lora-unsloth": {
        "name": "LoRA via Unsloth (rank-16 default, fastest on consumer GPUs)",
        "harness": "unsloth",
        "method_kind": "lora",
        "harness_args_template": [
            "--model_name_or_path", "{base}",
            "--dataset", "{dataset}",
            "--lora_r", "16",
            "--lora_alpha", "32",
            "--learning_rate", "2e-4",
            "--num_train_epochs", "3",
            "--per_device_train_batch_size", "4",
            "--output_dir", "{output_dir}",
        ],
        "applicable_base_classes": ["llm", "slm", "code"],
        "operator_role": "operator's go-to LoRA fine-tune; 2-5× faster than vanilla",
        "cost_estimate_hours": 2.0,
        "vram_gib_required_min": 16,
    },
    "qlora-trl": {
        "name": "QLoRA via TRL (4-bit base, LoRA on top — fits big models on 24GB GPU)",
        "harness": "trl",
        "method_kind": "qlora",
        "harness_args_template": [
            "sft",
            "--model_name_or_path", "{base}",
            "--dataset_name", "{dataset}",
            "--use_peft",
            "--load_in_4bit",
            "--lora_r", "64",
            "--lora_alpha", "16",
            "--learning_rate", "2e-4",
            "--num_train_epochs", "3",
            "--output_dir", "{output_dir}",
        ],
        "applicable_base_classes": ["llm", "rlm", "code"],
        "operator_role": "operator fits 70B base on a single 24GB card via 4-bit",
        "cost_estimate_hours": 6.0,
        "vram_gib_required_min": 24,
    },
    "sft-trl": {
        "name": "Supervised Fine-Tuning via TRL (full-precision, all weights)",
        "harness": "trl",
        "method_kind": "sft",
        "harness_args_template": [
            "sft",
            "--model_name_or_path", "{base}",
            "--dataset_name", "{dataset}",
            "--learning_rate", "5e-5",
            "--num_train_epochs", "3",
            "--per_device_train_batch_size", "1",
            "--gradient_accumulation_steps", "8",
            "--output_dir", "{output_dir}",
        ],
        "applicable_base_classes": ["llm", "slm"],
        "operator_role": "full-parameter SFT when LoRA isn't enough; expensive",
        "cost_estimate_hours": 24.0,
        "vram_gib_required_min": 48,
    },
    "dpo-trl": {
        "name": "Direct Preference Optimization via TRL (preference pairs → policy)",
        "harness": "trl",
        "method_kind": "dpo",
        "harness_args_template": [
            "dpo",
            "--model_name_or_path", "{base}",
            "--dataset_name", "{dataset}",
            "--beta", "0.1",
            "--learning_rate", "5e-6",
            "--num_train_epochs", "1",
            "--per_device_train_batch_size", "1",
            "--output_dir", "{output_dir}",
        ],
        "applicable_base_classes": ["llm", "rlm"],
        "operator_role": "alignment-style training; consumes preference pairs",
        "cost_estimate_hours": 12.0,
        "vram_gib_required_min": 48,
    },
}


def load_catalog(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        doc = yaml.safe_load(fh)
    return ((doc.get("catalog") or {}).get("models")) or []


def resolve_base(models: list[dict[str, Any]], base: str) -> dict[str, Any] | None:
    s = base.lower()
    for m in models:
        if m.get("id", "").lower() == s:
            return m
    for m in models:
        if s in (m.get("hf_repo_id") or "").lower():
            return m
    return None


def cmd_list_methods(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps({
            "round": "R244",
            "vector": "SDD-026 Z-2 (fine-tune methods)",
            "methods": METHODS,
        }, indent=2))
        return 0
    print("── R244 sovereign-os model fine-tune methods (SDD-026 Z-2) ──")
    for k, m in METHODS.items():
        print(f"  {k}")
        print(f"    name:       {m['name']}")
        print(f"    harness:    {m['harness']}  (kind={m['method_kind']})")
        print(f"    role:       {m['operator_role']}")
        print(f"    base_classes: {', '.join(m['applicable_base_classes'])}")
        print(f"    vram floor: {m['vram_gib_required_min']} GiB")
        print(f"    cost:       ~{m['cost_estimate_hours']} h on SAIN-01")
        print()
    return 0


def build_command(model: dict[str, Any], method_key: str, dataset: str, output_dir: str) -> list[str]:
    method = METHODS[method_key]
    model_name = model.get("hf_repo_id") or model.get("id")
    cmd = [method["harness"]]
    for tok in method["harness_args_template"]:
        if "{base}" in tok:
            cmd.append(tok.replace("{base}", model_name))
        elif "{dataset}" in tok:
            cmd.append(tok.replace("{dataset}", dataset))
        elif "{output_dir}" in tok:
            cmd.append(tok.replace("{output_dir}", output_dir))
        else:
            cmd.append(tok)
    return cmd


def cmd_plan(args: argparse.Namespace) -> int:
    cat = load_catalog(args.catalog)
    model = resolve_base(cat, args.base)
    if model is None:
        print(f"ERROR unknown base model {args.base!r}", file=sys.stderr)
        return 2
    if args.method not in METHODS:
        print(
            f"ERROR unknown method {args.method!r}; known: {sorted(METHODS)}",
            file=sys.stderr,
        )
        return 2
    method = METHODS[args.method]
    if model.get("class") not in method["applicable_base_classes"]:
        print(
            f"ERROR method {args.method!r} not applicable to base class "
            f"{model.get('class')!r}; applicable: "
            f"{method['applicable_base_classes']}",
            file=sys.stderr,
        )
        return 2
    output_dir = args.output_dir or f"/var/lib/sovereign-os/fine-tune/{model['id']}-{args.method}"
    cmd = build_command(model, args.method, args.dataset, output_dir)
    harness_present = shutil.which(method["harness"]) is not None

    # Check VRAM budget against R219 gpu-watch readings.
    vram_warning = None
    base_vram = model.get("vram_gib_min", 0) or 0
    required = method["vram_gib_required_min"]
    if base_vram + required > 24:
        vram_warning = (
            f"base vram_gib_min={base_vram} + method requires "
            f"{required} → estimate {base_vram + required} GiB; "
            f"single-4090 (24 GiB) insufficient — use --device cuda:1 (6000 Blackwell) "
            f"or reduce batch_size / use QLoRA"
        )

    plan = {
        "round": "R244",
        "vector": "SDD-026 Z-2 (fine-tune plan)",
        "base": {"id": model.get("id"), "hf_repo_id": model.get("hf_repo_id"),
                 "class": model.get("class"),
                 "vram_gib_min": base_vram},
        "method": {"key": args.method, **method},
        "dataset": args.dataset,
        "output_dir": output_dir,
        "command": cmd,
        "command_str": " ".join(cmd),
        "harness_present": harness_present,
        "vram_warning": vram_warning,
        "next_step": (
            f"sovereign-osctl models fine-tune run {model.get('id')} "
            f"--method {args.method} --dataset {args.dataset}"
        ),
    }
    if args.json:
        print(json.dumps(plan, indent=2))
        return 0
    print(f"── R244 sovereign-os fine-tune plan ({args.method}) ──")
    print(f"  base:       {model.get('id')}  ({model.get('hf_repo_id') or '-'})")
    print(f"  method:     {method['name']}")
    print(f"  dataset:    {args.dataset}")
    print(f"  output:     {output_dir}")
    print(f"  cost:       ~{method['cost_estimate_hours']} h")
    if harness_present:
        harness_state = "present"
    else:
        harness_state = (
            "NOT installed — `sovereign-osctl models toolchains info "
            f"{method['harness']}` for install hint"
        )
    print(f"  harness:    {method['harness']}  ({harness_state})")
    if vram_warning:
        print(f"  ⚠ vram:     {vram_warning}")
    print(f"  command:    {' '.join(cmd)}")
    print(f"  next:       {plan['next_step']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cat = load_catalog(args.catalog)
    model = resolve_base(cat, args.base)
    if model is None:
        print(f"ERROR unknown base {args.base!r}", file=sys.stderr)
        return 2
    if args.method not in METHODS:
        print(f"ERROR unknown method {args.method!r}", file=sys.stderr)
        return 2
    method = METHODS[args.method]
    if model.get("class") not in method["applicable_base_classes"]:
        print(
            f"ERROR method {args.method!r} not applicable to base class "
            f"{model.get('class')!r}",
            file=sys.stderr,
        )
        return 2
    output_dir = args.output_dir or f"/var/lib/sovereign-os/fine-tune/{model['id']}-{args.method}"
    cmd = build_command(model, args.method, args.dataset, output_dir)
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")

    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rc = 0
    duration_s = 0.0
    if dry:
        outcome = "dry-run"
        detail = f"would exec: {' '.join(cmd)}"
    elif shutil.which(method["harness"]) is None:
        outcome = "harness-missing"
        detail = f"{method['harness']} not on PATH"
        rc = 1
    else:
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            rc = r.returncode
            duration_s = time.time() - t0
            outcome = "ok" if rc == 0 else "failed"
            detail = (r.stdout or "")[-2000:] + (r.stderr or "")[-2000:]
        except OSError as e:
            rc = 1
            outcome = "exec-error"
            detail = str(e)

    record = {
        "round": "R244",
        "base_id": model.get("id"),
        "base_hf_repo": model.get("hf_repo_id"),
        "method": args.method,
        "dataset": args.dataset,
        "output_dir": output_dir,
        "started_at": started_at,
        "duration_s": round(duration_s, 2),
        "outcome": outcome,
        "rc": rc,
        "command": cmd,
        "dry_run": bool(dry),
    }
    # Append to state file always (audit trail).
    state_path = resolve_state_path()
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as e:
        print(f"WARN  could not write {state_path}: {e}", file=sys.stderr)

    if args.json:
        out = dict(record)
        out["detail"] = (detail or "")[:512]
        print(json.dumps(out, indent=2))
    else:
        mark = {"ok": "OK", "dry-run": "DRY", "failed": "FAIL",
                "harness-missing": "MISS", "exec-error": "ERR"}.get(outcome, "?")
        print(f"[{mark}] {model.get('id')} {args.method}  "
              f"({duration_s:.1f}s)  → {outcome}")
        if outcome in ("dry-run", "harness-missing"):
            print(f"      {detail}")
    return rc


def cmd_history(args: argparse.Namespace) -> int:
    state_path = resolve_state_path()
    rows: list[dict[str, Any]] = []
    if state_path.exists():
        try:
            with state_path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            print(f"ERROR reading {state_path}: {e}", file=sys.stderr)
            return 2
    if args.base:
        rows = [r for r in rows if r.get("base_id", "").lower() == args.base.lower()]
    if args.method:
        rows = [r for r in rows if r.get("method") == args.method]
    if args.limit:
        rows = rows[-int(args.limit):]
    if args.json:
        print(json.dumps({
            "round": "R244",
            "state_path": str(state_path),
            "filter": {"base": args.base, "method": args.method},
            "count": len(rows),
            "rows": rows,
        }, indent=2))
        return 0
    print(f"── R244 sovereign-os fine-tune history ({state_path}) ──")
    if not rows:
        print("  (no fine-tune runs recorded)")
        return 0
    for r in rows:
        print(
            f"  {r.get('started_at')}  {r.get('base_id'):28s}  "
            f"{r.get('method'):14s}  rc={r.get('rc')}  "
            f"{r.get('outcome'):16s}  ({r.get('duration_s',0):.1f}s)"
            f"  {'dry-run' if r.get('dry_run') else ''}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fine_tune.py",
        description="R244 (SDD-026 Z-2) — model fine-tune planner + dispatcher + history.",
    )
    p.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    sub = p.add_subparsers(dest="verb", required=True)
    pl = sub.add_parser("list-methods", help="enumerate supported fine-tune methods")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list_methods)
    pp = sub.add_parser("plan", help="show the command + cost for one run")
    pp.add_argument("base")
    pp.add_argument("--method", required=True)
    pp.add_argument("--dataset", required=True)
    pp.add_argument("--output-dir")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_plan)
    pr = sub.add_parser("run", help="execute (DRY-RUN-by-default for SEED)")
    pr.add_argument("base")
    pr.add_argument("--method", required=True)
    pr.add_argument("--dataset", required=True)
    pr.add_argument("--output-dir")
    pr.add_argument("--dry-run", action="store_true")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_run)
    ph = sub.add_parser("history", help="render the fine-tune state file")
    ph.add_argument("--base")
    ph.add_argument("--method")
    ph.add_argument("--limit", type=int)
    ph.add_argument("--json", action="store_true")
    ph.set_defaults(func=cmd_history)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
