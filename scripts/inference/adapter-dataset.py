#!/usr/bin/env python3
"""scripts/inference/adapter-dataset.py — curate a LoRA training dataset from
agentic interaction traces (SDD-722; the E0444 "trace → success/failure examples
→ curated dataset" producer). The upstream half of the M046 loop:

  traces (this) → **dataset** → TRAIN (adapter-train, SDD-721) → register →
  MS041 gate (adapter-gate) → transport (SDD-716) → serve `--lora` (SDD-715).

Unlike adapter-train (a planner — GPU training is SAIN-01-side), curation is
pure I/O and RUNS in CI: it reads a JSONL **trace log** and writes a curated
JSONL **dataset** that unsloth/TRL consume as `--dataset`. Each trace line is one
agentic interaction the gateway/goal-loop emits:

  {"messages": [{"role": "...", "content": "..."}, ...],
   "outcome": "success" | "failure" | null,   # optional explicit label
   "goal": "..."}                              # optional

SUCCESS SIGNAL (load-bearing, real reuse): a trajectory is a positive example
when `outcome == "success"` OR its final assistant message carries the goal
loop's own completion token — `DONE_SENTINEL` imported from goal-driver.py
(SDD-719). So "the goal loop said it finished" IS the training label; no separate
oracle needed. The sentinel is stripped from the emitted target so the model
learns the behaviour, not the token.

Curation rails: drop interactions shorter than `--min-turns`, drop ones with no
assistant reply, dedup identical message sequences. Emits chat-format lines
`{"messages": [...]}`. DRY-RUN by default (reports kept/dropped + reasons +
previews the first example); `--apply` writes the dataset to `--out` (default
`/var/lib/sovereign-os/adapters/<id>/dataset/train.jsonl`).

Sovereignty: stdlib-only; DRY-RUN default (no host write without `--apply`).

  adapter-dataset.py curate <id> --traces <log.jsonl> [--out <path>]
                    [--label success|all] [--min-turns N] [--apply] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent

# Reuse the goal loop's completion token as the success label (SDD-719).
_gd_spec = importlib.util.spec_from_file_location(
    "_goal_driver_for_dataset", _HERE / "goal-driver.py"
)
_gd = importlib.util.module_from_spec(_gd_spec)  # type: ignore[arg-type]
_gd_spec.loader.exec_module(_gd)  # type: ignore[union-attr]
DONE_SENTINEL: str = getattr(_gd, "DONE_SENTINEL", "[[GOAL_DONE]]")

ADAPTERS_DIR = "/var/lib/sovereign-os/adapters"


def _messages(rec: dict[str, Any]) -> list[dict[str, Any]]:
    msgs = rec.get("messages")
    return msgs if isinstance(msgs, list) else []


def _last_assistant(msgs: list[dict[str, Any]]) -> dict[str, Any] | None:
    for m in reversed(msgs):
        if m.get("role") == "assistant":
            return m
    return None


def is_success(rec: dict[str, Any]) -> bool:
    """A positive example: explicit outcome==success, OR the final assistant
    message carries the goal loop's DONE_SENTINEL."""
    if rec.get("outcome") == "success":
        return True
    if rec.get("outcome") == "failure":
        return False
    last = _last_assistant(_messages(rec))
    return bool(last and DONE_SENTINEL in str(last.get("content", "")))


def _clean(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip the completion sentinel from assistant targets (learn the
    behaviour, not the token) and keep only role/content."""
    out = []
    for m in msgs:
        content = str(m.get("content", ""))
        if m.get("role") == "assistant":
            content = content.replace(DONE_SENTINEL, "").rstrip()
        out.append({"role": m.get("role"), "content": content})
    return out


def _seq_hash(msgs: list[dict[str, Any]]) -> str:
    payload = json.dumps(msgs, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def curate(
    traces: list[dict[str, Any]],
    *,
    label: str = "success",
    min_turns: int = 2,
) -> dict[str, Any]:
    kept: list[dict[str, Any]] = []
    dropped: dict[str, int] = {"too_short": 0, "no_assistant": 0, "not_success": 0, "duplicate": 0}
    seen: set[str] = set()

    for rec in traces:
        msgs = _messages(rec)
        if len(msgs) < min_turns:
            dropped["too_short"] += 1
            continue
        if _last_assistant(msgs) is None:
            dropped["no_assistant"] += 1
            continue
        ok = is_success(rec)
        if label == "success" and not ok:
            dropped["not_success"] += 1
            continue
        cleaned = _clean(msgs)
        h = _seq_hash(cleaned)
        if h in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(h)
        example: dict[str, Any] = {"messages": cleaned}
        if label == "all":
            example["label"] = "success" if ok else "failure"
        kept.append(example)

    return {
        "kept": kept,
        "kept_count": len(kept),
        "dropped": dropped,
        "dropped_count": sum(dropped.values()),
        "total": len(traces),
        "label": label,
        "min_turns": min_turns,
    }


def _read_traces(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _emit(adapter_id: str, out_path: str, res: dict[str, Any], apply: bool, as_json: bool) -> None:
    summary = {
        "adapter_id": adapter_id,
        "output": out_path,
        "kept": res["kept_count"],
        "dropped": res["dropped"],
        "total": res["total"],
        "label": res["label"],
        "wrote": apply,
        "next": f"adapter-train.py plan {adapter_id} --base <unpacked> --dataset {out_path}",
    }
    if as_json:
        print(json.dumps(summary, indent=2))
        return
    print(f"# curate dataset for adapter {adapter_id}  (label={res['label']}, min_turns={res['min_turns']})")
    print(f"#   traces  : {res['total']}")
    print(f"#   kept    : {res['kept_count']}")
    for reason, n in res["dropped"].items():
        if n:
            print(f"#   dropped : {n} ({reason})")
    print(f"#   output  : {out_path}  ({'WROTE' if apply else 'DRY-RUN — pass --apply to write'})")
    if res["kept"]:
        first = json.dumps(res["kept"][0], ensure_ascii=False)
        print(f"#   example : {first[:200]}{'…' if len(first) > 200 else ''}")
    print(f"  next: {summary['next']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("curate", help="curate a training dataset from traces (DRY-RUN unless --apply)")
    c.add_argument("adapter_id")
    c.add_argument("--traces", required=True, help="JSONL trace log")
    c.add_argument("--out", default=None, help="output dataset path (default under /adapters/<id>/dataset)")
    c.add_argument("--label", choices=["success", "all"], default="success")
    c.add_argument("--min-turns", type=int, default=2)
    c.add_argument("--apply", action="store_true", help="write the dataset (default: DRY-RUN)")
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "curate":
        traces_path = Path(args.traces)
        if not traces_path.is_file():
            print(f"adapter-dataset: no such trace log: {traces_path}", file=sys.stderr)
            return 2
        out_path = args.out or f"{ADAPTERS_DIR}/{args.adapter_id}/dataset/train.jsonl"
        res = curate(_read_traces(traces_path), label=args.label, min_turns=args.min_turns)
        if args.apply:
            dest = Path(out_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("w", encoding="utf-8") as fh:
                for ex in res["kept"]:
                    fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
        _emit(args.adapter_id, out_path, res, args.apply, args.json)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
