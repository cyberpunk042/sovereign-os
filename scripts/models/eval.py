#!/usr/bin/env python3
"""scripts/models/eval.py — R232 (SDD-026 Z-2 expansion).

Operator-named (verbatim, 2026-05-17 expansion): "[…] download,
fine-tune, parameters, build, run, use and train and adapt and use
and eval and etc."

LM-Studio-equivalent EVAL surface. R231 ships rich detail per
model; R232 ships the eval planning surface: given a model slug +
a benchmark name, emit the operator-runnable invocation + record
the eval intent in a state file so the dashboard can show "last
eval ran X hours ago, score=N".

Cycle-8 SEED: the actual benchmark executors (lm-eval-harness,
HumanEval, MMLU, etc.) require GB of harness installs + actual
model loading; those are out of scope for the SEED round. R232
ships:

  - a benchmark CATALOG (operator-readable list of supported
    benchmarks with their tier / what-they-measure / runtime cost
    estimate);
  - `eval plan <slug> --benchmark B` — emit the exact command the
    operator should run (with --dry-run output so the dashboard
    can preview);
  - `eval run <slug> --benchmark B [--dry-run]` — execute (DRY-RUN
    is the default until SAIN-01 hardware lands) + record the
    result to the state file;
  - `eval history [--slug S] [--benchmark B]` — operator-readable
    eval log (the dashboard's "evals tab" data source).

State file: /var/lib/sovereign-os/models-eval.jsonl (one JSON line
per eval invocation). Honors SOVEREIGN_OS_MODELS_EVAL_STATE env.

Exit codes:
  0  command succeeded (plan / dry-run / history rendered)
  1  benchmark execution failed (only on `eval run` without --dry-run)
  2  usage error / unknown slug / unknown benchmark
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
DEFAULT_STATE = Path("/var/lib/sovereign-os/models-eval.jsonl")


def resolve_state_path() -> Path:
    env = os.environ.get("SOVEREIGN_OS_MODELS_EVAL_STATE")
    return Path(env) if env else DEFAULT_STATE


# Benchmark catalog — declarative. Each entry binds an operator-
# friendly name to the harness invocation + the target model classes
# it makes sense for. Cost estimate is wall-clock for a single-shot
# eval on SAIN-01 (RTX PRO 6000 + 4090); a SEED estimate, refined
# once real evals land.
BENCHMARKS: dict[str, dict[str, Any]] = {
    "mmlu": {
        "name": "MMLU (Massive Multitask Language Understanding)",
        "harness": "lm-eval",
        "harness_args": ["--tasks", "mmlu", "--num_fewshot", "5"],
        "measures": "general academic + reasoning across 57 subjects",
        "applicable_classes": ["llm", "slm", "rlm", "code", "ternary-lm", "mixture"],
        "cost_estimate_minutes": 45,
    },
    "humaneval": {
        "name": "HumanEval (Python code synthesis)",
        "harness": "lm-eval",
        "harness_args": ["--tasks", "humaneval", "--num_fewshot", "0"],
        "measures": "Python function synthesis from docstring (pass@1)",
        "applicable_classes": ["llm", "code", "rlm"],
        "cost_estimate_minutes": 15,
    },
    "gsm8k": {
        "name": "GSM8K (grade-school math, chain-of-thought)",
        "harness": "lm-eval",
        "harness_args": ["--tasks", "gsm8k", "--num_fewshot", "8"],
        "measures": "multi-step arithmetic reasoning",
        "applicable_classes": ["llm", "slm", "rlm", "ternary-lm"],
        "cost_estimate_minutes": 20,
    },
    "arc-challenge": {
        "name": "ARC-Challenge (science QA, hard partition)",
        "harness": "lm-eval",
        "harness_args": ["--tasks", "arc_challenge", "--num_fewshot", "25"],
        "measures": "grade-school science multiple-choice",
        "applicable_classes": ["llm", "slm", "rlm", "ternary-lm"],
        "cost_estimate_minutes": 10,
    },
    "truthfulqa": {
        "name": "TruthfulQA (factual accuracy under adversarial prompts)",
        "harness": "lm-eval",
        "harness_args": ["--tasks", "truthfulqa_mc1"],
        "measures": "resistance to confident-but-wrong outputs",
        "applicable_classes": ["llm", "slm", "rlm"],
        "cost_estimate_minutes": 8,
    },
    "mteb-retrieval": {
        "name": "MTEB Retrieval (embedding model recall@k)",
        "harness": "mteb",
        "harness_args": ["--task-types", "Retrieval"],
        "measures": "dense-retrieval recall on standard retrieval suites",
        "applicable_classes": ["embed"],
        "cost_estimate_minutes": 30,
    },
    # 2026-07-19 (oracle-alternatives evaluation) — the serving bench
    # gate. Unlike the lm-eval/mteb rows this is a BUILTIN executor:
    # it drives a live OpenAI-compatible endpoint (router :8080 or a
    # tier port) with streaming requests and measures TTFT + decode
    # tok/s. This is the promotion gate the operator-must-confirm
    # catalog candidates (GLM-4.7 / MiniMax-M3 / gpt-oss-120b /
    # GLM-4.7-Flash) wait on — see
    # docs/evaluations/oracle-alternatives-glm47-m3-gptoss-2026-07-19.md.
    # No GB harness install; stdlib-only; safe on any reachable server.
    "throughput": {
        "name": "Serving throughput (TTFT + decode tok/s, streaming)",
        "harness": "builtin",
        "harness_args": [],
        "measures": "time-to-first-token + steady-state decode tokens/sec against a live endpoint",
        "applicable_classes": [
            "llm", "slm", "rlm", "code", "ternary-lm", "mixture", "multimodal",
        ],
        "cost_estimate_minutes": 5,
    },
}

# Throughput-bench prompt battery — deliberately mixed shape (short
# chat, code synthesis, longer reasoning) so decode rate isn't gamed
# by one prompt style. Operator-overridable count via
# SOVEREIGN_OS_BENCH_PROMPTS (cycles through this list).
THROUGHPUT_PROMPTS: list[str] = [
    "Explain, in three short paragraphs, why ZFS copies=2 on a "
    "16k-recordsize dataset is a different trade-off than RAID 1.",
    "Write a Python function `topo_sort(edges: list[tuple[str, str]]) "
    "-> list[str]` implementing Kahn's algorithm with cycle detection. "
    "Include type hints and a docstring.",
    "A workstation has two GPUs (96GB and 32GB) and 256GB RAM. A "
    "358B-parameter MoE model with 32B active parameters is quantized "
    "to 4 bits. Walk through whether it fits, and where each part "
    "should live for best decode speed.",
]


def load_catalog(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        doc = yaml.safe_load(fh)
    return ((doc.get("catalog") or {}).get("models")) or []


def resolve_slug(models: list[dict[str, Any]], slug: str) -> dict[str, Any] | None:
    s = slug.lower()
    for m in models:
        if m.get("id", "").lower() == s:
            return m
    for m in models:
        if s in (m.get("hf_repo_id") or "").lower():
            return m
    return None


def cmd_list_benchmarks(args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R232",
                    "vector": "SDD-026 Z-2 (eval surface)",
                    "benchmarks": BENCHMARKS,
                },
                indent=2,
            )
        )
        return 0
    print("── R232 sovereign-os model eval benchmarks (SDD-026 Z-2) ──")
    for k, b in BENCHMARKS.items():
        print(f"  {k}")
        print(f"    name:     {b['name']}")
        print(f"    measures: {b['measures']}")
        print(f"    classes:  {', '.join(b['applicable_classes'])}")
        print(f"    cost:     ~{b['cost_estimate_minutes']} min on SAIN-01")
        print()
    return 0


def build_command(model: dict[str, Any], benchmark_key: str) -> list[str]:
    bench = BENCHMARKS[benchmark_key]
    if bench["harness"] == "builtin":
        # Self-executed (no external harness). The command shown to the
        # operator is the eval.py re-invocation itself.
        return [
            "scripts/models/eval.py",
            "run",
            str(model.get("id")),
            "--benchmark",
            benchmark_key,
        ]
    # Construct an lm-eval / mteb invocation. The model name passed to
    # the harness is the hf_repo_id (or model id as fallback).
    model_name = model.get("hf_repo_id") or model.get("id")
    cmd = [
        bench["harness"],
        "--model",
        "hf",
        "--model_args",
        f"pretrained={model_name}",
        *bench["harness_args"],
        "--output_path",
        f"/var/lib/sovereign-os/eval/{model.get('id')}-{benchmark_key}.json",
    ]
    return cmd


def run_throughput_bench(
    model: dict[str, Any],
    endpoint: str,
    max_tokens: int,
    n_prompts: int,
) -> dict[str, Any]:
    """Drive a live OpenAI-compatible endpoint with streaming chat
    completions; measure per-prompt TTFT + decode tok/s. stdlib-only.

    Token counting: prefers the server's `usage.completion_tokens`
    (vLLM/llama-server emit it with stream_options include_usage);
    falls back to counting content-bearing SSE chunks (≈1 token each).
    """
    import urllib.error
    import urllib.request

    served_model = os.environ.get("SOVEREIGN_OS_BENCH_MODEL") or (
        model.get("hf_repo_id") or model.get("id")
    )
    per_prompt: list[dict[str, Any]] = []
    for i in range(n_prompts):
        prompt = THROUGHPUT_PROMPTS[i % len(THROUGHPUT_PROMPTS)]
        payload = json.dumps(
            {
                "model": served_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
        ).encode()
        req = urllib.request.Request(
            endpoint.rstrip("/") + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        t_start = time.time()
        t_first: float | None = None
        t_last = t_start
        chunk_tokens = 0
        usage_tokens: int | None = None
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                for raw in resp:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    usage = obj.get("usage") or {}
                    if usage.get("completion_tokens"):
                        usage_tokens = int(usage["completion_tokens"])
                    choices = obj.get("choices") or []
                    delta = (choices[0].get("delta") or {}) if choices else {}
                    if delta.get("content"):
                        now = time.time()
                        if t_first is None:
                            t_first = now
                        t_last = now
                        chunk_tokens += 1
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            per_prompt.append({"prompt_idx": i, "error": str(e)})
            continue
        tokens = usage_tokens if usage_tokens is not None else chunk_tokens
        ttft = (t_first - t_start) if t_first is not None else None
        decode_s = (t_last - t_first) if t_first is not None else 0.0
        decode_tok_s = (
            (tokens - 1) / decode_s if tokens > 1 and decode_s > 0 else None
        )
        per_prompt.append(
            {
                "prompt_idx": i,
                "tokens": tokens,
                "ttft_s": round(ttft, 3) if ttft is not None else None,
                "decode_tok_s": round(decode_tok_s, 2)
                if decode_tok_s is not None
                else None,
            }
        )
    good = [p for p in per_prompt if p.get("decode_tok_s")]
    metrics: dict[str, Any] = {
        "endpoint": endpoint,
        "served_model": served_model,
        "n_prompts": n_prompts,
        "n_ok": len(good),
        "per_prompt": per_prompt,
    }
    if good:
        metrics["ttft_s_mean"] = round(
            sum(p["ttft_s"] for p in good if p.get("ttft_s") is not None)
            / max(1, len([p for p in good if p.get("ttft_s") is not None])),
            3,
        )
        metrics["decode_tok_s_mean"] = round(
            sum(p["decode_tok_s"] for p in good) / len(good), 2
        )
    return metrics


def cmd_plan(args: argparse.Namespace) -> int:
    cat = load_catalog(args.catalog)
    target = resolve_slug(cat, args.slug)
    if target is None:
        print(f"ERROR unknown slug {args.slug!r}", file=sys.stderr)
        return 2
    if args.benchmark not in BENCHMARKS:
        print(
            f"ERROR unknown benchmark {args.benchmark!r}; known: "
            f"{sorted(BENCHMARKS.keys())}",
            file=sys.stderr,
        )
        return 2
    bench = BENCHMARKS[args.benchmark]
    if target.get("class") not in bench["applicable_classes"]:
        print(
            f"ERROR benchmark {args.benchmark!r} not applicable to "
            f"class {target.get('class')!r}; applicable classes: "
            f"{bench['applicable_classes']}",
            file=sys.stderr,
        )
        return 2
    cmd = build_command(target, args.benchmark)
    harness_present = (
        True
        if bench["harness"] == "builtin"
        else shutil.which(bench["harness"]) is not None
    )
    plan = {
        "round": "R232",
        "vector": "SDD-026 Z-2 (eval plan)",
        "model": {"id": target.get("id"), "hf_repo_id": target.get("hf_repo_id")},
        "benchmark": {"key": args.benchmark, **bench},
        "command": cmd,
        "command_str": " ".join(cmd),
        "harness_present": harness_present,
        "next_step": (
            f"sovereign-osctl models eval run {target.get('id')} "
            f"--benchmark {args.benchmark}"
        ),
    }
    if args.json:
        print(json.dumps(plan, indent=2))
        return 0
    print(f"── R232 sovereign-os models eval plan ({args.benchmark}) ──")
    print(f"  model:     {target.get('id')}  ({target.get('hf_repo_id') or '-'})")
    print(f"  benchmark: {bench['name']}")
    print(f"  cost:      ~{bench['cost_estimate_minutes']} min")
    print(f"  harness:   {bench['harness']}  "
          f"({'present on PATH' if harness_present else 'NOT installed — pip install required'})")
    print(f"  command:   {' '.join(cmd)}")
    print(f"  next:      {plan['next_step']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cat = load_catalog(args.catalog)
    target = resolve_slug(cat, args.slug)
    if target is None:
        print(f"ERROR unknown slug {args.slug!r}", file=sys.stderr)
        return 2
    if args.benchmark not in BENCHMARKS:
        print(f"ERROR unknown benchmark {args.benchmark!r}", file=sys.stderr)
        return 2
    bench = BENCHMARKS[args.benchmark]
    if target.get("class") not in bench["applicable_classes"]:
        print(
            f"ERROR benchmark {args.benchmark!r} not applicable to "
            f"class {target.get('class')!r}",
            file=sys.stderr,
        )
        return 2
    cmd = build_command(target, args.benchmark)
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")

    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rc = 0
    duration_s = 0.0
    metrics: dict[str, Any] | None = None
    if dry:
        outcome = "dry-run"
        if bench["harness"] == "builtin":
            endpoint = args.endpoint or os.environ.get(
                "SOVEREIGN_OS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1"
            )
            detail = (
                f"would stream {os.environ.get('SOVEREIGN_OS_BENCH_PROMPTS', '3')} "
                f"prompts against {endpoint} and measure TTFT + decode tok/s"
            )
        else:
            detail = f"would exec: {' '.join(cmd)}"
    elif bench["harness"] == "builtin":
        endpoint = args.endpoint or os.environ.get(
            "SOVEREIGN_OS_BENCH_ENDPOINT", "http://127.0.0.1:8080/v1"
        )
        n_prompts = int(os.environ.get("SOVEREIGN_OS_BENCH_PROMPTS", "3"))
        max_toks = int(os.environ.get("SOVEREIGN_OS_BENCH_MAX_TOKENS", "256"))
        t0 = time.time()
        metrics = run_throughput_bench(target, endpoint, max_toks, n_prompts)
        duration_s = time.time() - t0
        if metrics.get("n_ok", 0) == 0:
            outcome = "failed"
            rc = 1
            detail = f"no successful streamed completion from {endpoint}"
        else:
            outcome = "ok"
            detail = (
                f"decode {metrics.get('decode_tok_s_mean')} tok/s mean, "
                f"TTFT {metrics.get('ttft_s_mean')}s mean "
                f"({metrics['n_ok']}/{metrics['n_prompts']} prompts ok)"
            )
            if args.min_tok_s is not None and (
                (metrics.get("decode_tok_s_mean") or 0) < args.min_tok_s
            ):
                outcome = "below-gate"
                rc = 1
                detail += f" — BELOW --min-tok-s gate ({args.min_tok_s})"
    elif shutil.which(bench["harness"]) is None:
        outcome = "harness-missing"
        detail = f"{bench['harness']} not on PATH"
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
        "round": "R232",
        "model_id": target.get("id"),
        "hf_repo_id": target.get("hf_repo_id"),
        "benchmark": args.benchmark,
        "started_at": started_at,
        "duration_s": round(duration_s, 2),
        "outcome": outcome,
        "rc": rc,
        "command": cmd,
        "dry_run": bool(dry),
    }
    if metrics is not None:
        record["metrics"] = metrics
    if args.min_tok_s is not None:
        record["min_tok_s_gate"] = args.min_tok_s

    # Append to state file even on failure (audit trail).
    state_path = resolve_state_path()
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError as e:
        # Don't mask the eval rc with a state-write failure.
        print(f"WARN  could not write {state_path}: {e}", file=sys.stderr)

    if args.json:
        # Truncate detail on JSON output (it can be huge harness output).
        out = dict(record)
        out["detail"] = (detail or "")[:512]
        print(json.dumps(out, indent=2))
    else:
        mark = {
            "ok": "OK",
            "dry-run": "DRY",
            "failed": "FAIL",
            "below-gate": "GATE",
            "harness-missing": "MISS",
            "exec-error": "ERR ",
        }.get(outcome, "?")
        print(f"[{mark}] {target.get('id')} / {args.benchmark}  "
              f"({duration_s:.1f}s)  → {outcome}")
        if outcome in ("dry-run", "harness-missing", "ok", "below-gate", "failed"):
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

    if args.slug:
        rows = [r for r in rows if r.get("model_id", "").lower() == args.slug.lower()]
    if args.benchmark:
        rows = [r for r in rows if r.get("benchmark") == args.benchmark]
    if args.limit:
        rows = rows[-int(args.limit):]

    if args.json:
        print(
            json.dumps(
                {
                    "round": "R232",
                    "state_path": str(state_path),
                    "filter": {"slug": args.slug, "benchmark": args.benchmark},
                    "count": len(rows),
                    "rows": rows,
                },
                indent=2,
            )
        )
        return 0
    print(f"── R232 sovereign-os models eval history ({state_path}) ──")
    if not rows:
        print("  (no eval runs recorded)")
        return 0
    for r in rows:
        m = r.get("metrics") or {}
        tok_s = m.get("decode_tok_s_mean")
        extra = f"  {tok_s} tok/s" if tok_s is not None else ""
        print(
            f"  {r.get('started_at')}  {r.get('model_id'):30s}  "
            f"{r.get('benchmark'):16s}  rc={r.get('rc')}  "
            f"{r.get('outcome'):14s}  ({r.get('duration_s',0):.1f}s)"
            f"  {'dry-run' if r.get('dry_run') else ''}{extra}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eval.py",
        description="R232 (SDD-026 Z-2) — model eval planner + dispatcher + history.",
    )
    p.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list-benchmarks", help="enumerate supported benchmarks")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list_benchmarks)

    pp = sub.add_parser("plan", help="show the command + cost for one eval")
    pp.add_argument("slug")
    pp.add_argument("--benchmark", required=True)
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_plan)

    pr = sub.add_parser("run", help="execute eval (DRY-RUN-by-default for SEED)")
    pr.add_argument("slug")
    pr.add_argument("--benchmark", required=True)
    pr.add_argument(
        "--dry-run",
        action="store_true",
        help="record intent + print command without executing",
    )
    pr.add_argument(
        "--endpoint",
        help="throughput benchmark only: OpenAI-compatible base URL "
        "(default $SOVEREIGN_OS_BENCH_ENDPOINT or http://127.0.0.1:8080/v1)",
    )
    pr.add_argument(
        "--min-tok-s",
        type=float,
        default=None,
        help="throughput benchmark only: promotion gate — rc=1 (outcome "
        "below-gate) when mean decode tok/s lands under this. Operator "
        "sets the bar; no default.",
    )
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_run)

    ph = sub.add_parser("history", help="render the eval state file")
    ph.add_argument("--slug")
    ph.add_argument("--benchmark")
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
