#!/usr/bin/env python3
"""scripts/inference/adapter-eval.py — run a benchmark suite against a served
adapter and write the eval-run record the MS041 gate reads (SDD-724; the eval
GATE-PRODUCER the foundry deferred). Closes the eval half of the MS041 triple-gate:

  train (SDD-721) → register → **eval (this) → adapter-gate eval** → snapshot →
  human/oracle → promote (adapter-decide).

`adapter-gate.py`'s `_eval_evidence` filters `evals.jsonl` for a PASSING record
for the adapter and honest-defers (SB-077 — never fabricate) with *"run the eval
first"* when none exists. Nothing produced that record. This runs the suite and
writes it, so the eval gate becomes reachable from real evidence.

Split like the rest of the foundry: the ONLY hardware-gated step is querying the
served adapter (`/v1/chat/completions`). Everything else — grading each answer,
scoring, assembling the record in `eval-tracker.py`'s exact shape — is pure and
CI-tested via an injected `Responder` (real = HTTP to the daemon; tests = a
scripted/replay responder, no model). The pass criterion is `eval-tracker._passed`
itself (score ≥ 0.5), so gate and runner can never disagree.

Suite = JSONL, one benchmark item per line:
  {"prompt": "...", "expect": "...", "grader": "contains" | "exact" | "regex"}

DRY-RUN by default (computes the score + previews the record); `--apply` appends
the record to the eval store (`SOVEREIGN_OS_EVAL_STORE`, default
`/var/log/sovereign-os/evals.jsonl`), bounded to the store's `MAX_RUNS`.

  adapter-eval.py run <id> --suite <suite.jsonl> [--model NAME] [--port 8083]
                  [--threshold 0.5] [--apply] [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]

# Reuse the eval-tracker (single source of truth for the store + pass rule + the
# record shape the D-10 dashboard and the MS041 gate both read).
_et_spec = importlib.util.spec_from_file_location(
    "_eval_tracker_for_eval", _REPO_ROOT / "scripts" / "observability" / "eval-tracker.py"
)
_et = importlib.util.module_from_spec(_et_spec)  # type: ignore[arg-type]
_et_spec.loader.exec_module(_et)  # type: ignore[union-attr]

# A Responder takes a prompt and returns the model's answer text.
Responder = Callable[[str], str]


def grade(answer: str, expect: str, grader: str) -> bool:
    """Pure grader. `contains` (default), `exact`, or `regex`. Case-insensitive
    for contains/exact (benchmark answers are text, not code)."""
    a = answer.strip()
    if grader == "exact":
        return a.casefold() == expect.strip().casefold()
    if grader == "regex":
        try:
            return re.search(expect, answer) is not None
        except re.error:
            return False
    # default: contains
    return expect.strip().casefold() in a.casefold()


def run_suite(
    adapter_id: str,
    suite: list[dict[str, Any]],
    responder: Responder,
    *,
    suite_name: str = "adapter-eval",
    model: str | None = None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Query the responder per item, grade, score = fraction passed. Returns the
    per-item results + the eval-run record (eval-tracker shape). `passed` uses
    eval-tracker._passed against the record so the gate can't disagree."""
    items: list[dict[str, Any]] = []
    n_pass = 0
    for i, it in enumerate(suite):
        prompt = str(it.get("prompt", ""))
        expect = str(it.get("expect", ""))
        grader = str(it.get("grader", "contains"))
        answer = responder(prompt)
        ok = grade(answer, expect, grader)
        n_pass += int(ok)
        items.append({"i": i, "grader": grader, "expect": expect, "passed": ok,
                      "answer": answer[:200]})

    total = len(suite)
    score = round(n_pass / total, 4) if total else 0.0
    record = {
        "task": "adapter-eval",
        "suite": suite_name,
        "intervention_class": "bb",       # prompt-only black-box eval
        "model": model or adapter_id,
        "role": "candidate",
        "score": score,                    # 0-1 fraction (eval-tracker normalises)
        "passed": score >= threshold,
        "adapter_id": adapter_id,
        "trace_id": f"adapter-eval-{adapter_id}-{suite_name}",
        "n": total,
        "n_pass": n_pass,
    }
    # Cross-check: our pass verdict must agree with the gate's own rule.
    record["gate_agrees"] = (_et._passed(record) == record["passed"])
    return {"record": record, "items": items, "score": score, "passed": record["passed"]}


def http_responder(model: str, port: int) -> Responder:
    """Real responder: one /v1/chat/completions call per benchmark item against
    the served adapter (the daemon has the `--lora` loaded)."""
    url = f"http://127.0.0.1:{port}/v1/chat/completions"

    def respond(prompt: str) -> str:
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 (loopback daemon)
            data = json.loads(r.read())
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    return respond


def append_record(record: dict[str, Any], *, store: Path | None = None) -> None:
    """Append the eval-run record to the store, bounded to eval-tracker's MAX_RUNS
    (oldest trimmed) so an always-on eval loop can't grow it unbounded. Atomic."""
    import os

    store = store or _et.EVAL_STORE
    store.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if store.is_file():
        lines = [ln for ln in store.read_text(encoding="utf-8").splitlines() if ln.strip()]
    lines.append(json.dumps(record, ensure_ascii=False))
    if len(lines) > _et.MAX_RUNS:
        lines = lines[-_et.MAX_RUNS:]
    tmp = store.with_suffix(store.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, store)


def _read_suite(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _emit(res: dict[str, Any], apply: bool, as_json: bool) -> None:
    rec = res["record"]
    if as_json:
        print(json.dumps({"record": rec, "wrote": apply}, indent=2))
        return
    verdict = "PASS" if rec["passed"] else "FAIL"
    print(f"# eval {rec['adapter_id']}  suite={rec['suite']}  "
          f"score={rec['score']} ({rec['n_pass']}/{rec['n']})  → {verdict}")
    for it in res["items"]:
        mark = "ok " if it["passed"] else "MISS"
        print(f"  [{mark}] expect~{it['expect']!r} ({it['grader']})")
    if not apply:
        print(f"  (DRY-RUN — pass --apply to record to {_et.EVAL_STORE})")
    else:
        print(f"  recorded → {_et.EVAL_STORE}")
    print(f"  next: sovereign-osctl adapters gate eval {rec['adapter_id']} --confirm")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a benchmark suite against a served adapter (DRY-RUN unless --apply)")
    r.add_argument("adapter_id")
    r.add_argument("--suite", required=True, help="JSONL benchmark suite")
    r.add_argument("--model", default=None, help="served model name (default: the adapter id)")
    r.add_argument("--port", type=int, default=8083)
    r.add_argument("--threshold", type=float, default=0.5)
    r.add_argument("--apply", action="store_true", help="record the eval run (default: DRY-RUN)")
    r.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "run":
        suite_path = Path(args.suite)
        if not suite_path.is_file():
            print(f"adapter-eval: no such suite: {suite_path}", file=sys.stderr)
            return 2
        suite = _read_suite(suite_path)
        res = run_suite(
            args.adapter_id, suite,
            http_responder(args.model or args.adapter_id, args.port),
            suite_name=suite_path.stem, model=args.model, threshold=args.threshold,
        )
        if args.apply:
            append_record(res["record"])
        _emit(res, args.apply, args.json)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
