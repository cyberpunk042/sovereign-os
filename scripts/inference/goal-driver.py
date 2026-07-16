#!/usr/bin/env python3
"""scripts/inference/goal-driver.py — loop-until-goal (SDD-719, implementation
slice 1; the SDD-718 self-loop tier realized as an orchestrator).

While a `/goal` (goal-ctl.py) is `active`, this re-arms the daemon's server-side
agentic loop (SDD-712, `sovereign_agentic: true`) once per iteration toward the
locked goal — feeding the goal + recent progress back each pass — until:

  - the model signals completion  → goal status `done`
  - the goal-level step ceiling    → status `paused` (default max-iterations 50)
  - the goal-level no-progress guard → status `paused` (default 3 stuck passes)

Two guards, distinct from SDD-712's PER-STEP repeat-guard: the **goal-level**
max-iterations ceiling + the **goal-level** no-progress guard, so "keep going
until done" can never pin the box. The model marks completion by ending a reply
with the sentinel `[[GOAL_DONE]]` (the prompt tells it to).

The per-iteration call goes through a `Responder`: the real one POSTs to the
gateway `/v1/chat/completions`; tests inject a scripted responder (no model, no
network — the SDD-712 pattern), so the loop logic is proven without weights.

Sovereignty: stdlib-only; only writes goal progress (never executes tools —
tool dispatch + its permission gating is the daemon's job, SDD-720). Runs only
while a goal is `active` (no goal → no-op).

  goal-driver.py run [--max-iters 50] [--no-progress 3] [--model NAME] [--port 8083]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent

# Reuse goal-ctl's state helpers (hyphenated filename → importlib).
_spec = importlib.util.spec_from_file_location("_goal_ctl", _HERE / "goal-ctl.py")
_goal = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_goal)  # type: ignore[union-attr]

DONE_SENTINEL = "[[GOAL_DONE]]"

# A Responder takes the built prompt and returns {"text": str, "done": bool}.
Responder = Callable[[str], dict[str, Any]]


def build_prompt(goal: dict[str, Any]) -> str:
    """Goal text (sacrosanct-verbatim) + plan + recent progress + the completion
    contract. The goal text is quoted, never paraphrased."""
    parts = [f"GOAL (do not restate, pursue it): {goal['text']}"]
    if goal.get("plan"):
        parts.append("PLAN:\n" + "\n".join(f"  {i}. {s}" for i, s in enumerate(goal["plan"], 1)))
    if goal.get("last_progress"):
        parts.append(f"PROGRESS SO FAR: {goal['last_progress']}")
    parts.append(
        "Take the next concrete step toward the GOAL. When (and only when) the "
        f"GOAL is fully achieved, end your reply with the token {DONE_SENTINEL}."
    )
    return "\n\n".join(parts)


def gateway_responder(model: str, port: int) -> Responder:
    """Real responder: one agentic /v1/chat/completions call per iteration."""
    url = f"http://127.0.0.1:{port}/v1/chat/completions"

    def respond(prompt: str) -> dict[str, Any]:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "sovereign_agentic": True,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 (loopback daemon)
            data = json.loads(r.read())
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        return {"text": text, "done": DONE_SENTINEL in text}

    return respond


def run_loop(
    responder: Responder,
    *,
    max_iters: int = 50,
    no_progress_limit: int = 3,
) -> dict[str, Any]:
    """Loop-until-goal. Returns {stop_reason, iterations, final_status}.
    stop_reason ∈ {done, max-iters, no-progress, not-active}."""
    g = _goal._get_goal()
    if not g or g.get("status") != "active":
        return {"stop_reason": "not-active", "iterations": g.get("iterations", 0) if g else 0,
                "final_status": g.get("status") if g else None}

    no_progress = 0
    while True:
        g = _goal._get_goal()
        if not g or g.get("status") != "active":
            return {"stop_reason": "not-active", "iterations": g.get("iterations", 0) if g else 0,
                    "final_status": g.get("status") if g else None}
        if int(g.get("iterations", 0)) >= max_iters:
            _goal._set_status("paused")
            return {"stop_reason": "max-iters", "iterations": g["iterations"], "final_status": "paused"}

        prev = g.get("last_progress", "")
        result = responder(build_prompt(g))
        text = (result.get("text") or "").strip()
        made_progress = bool(text) and text != prev
        # add_progress bumps iterations + records last_progress (never touches text).
        _goal.add_progress(text[:200] if text else "(no output)")
        no_progress = 0 if made_progress else no_progress + 1

        if result.get("done"):
            _goal._set_status("done")
            g = _goal._get_goal()
            return {"stop_reason": "done", "iterations": g["iterations"], "final_status": "done"}
        if no_progress >= no_progress_limit:
            _goal._set_status("paused")
            g = _goal._get_goal()
            return {"stop_reason": "no-progress", "iterations": g["iterations"], "final_status": "paused"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="pursue the active goal until done / capped / stuck")
    p.add_argument("--max-iters", type=int, default=50)
    p.add_argument("--no-progress", type=int, default=3)
    p.add_argument("--model", default="local")
    p.add_argument("--port", type=int, default=8083)
    p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "run":
        g = _goal._get_goal()
        if not g or g.get("status") != "active":
            print("goal-driver: no active goal (set one with goal-ctl.py set)", file=sys.stderr)
            return 2
        out = run_loop(
            gateway_responder(args.model, args.port),
            max_iters=args.max_iters,
            no_progress_limit=args.no_progress,
        )
        print(json.dumps(out, indent=2) if args.json
              else f"stopped: {out['stop_reason']} after {out['iterations']} iterations "
                   f"(goal → {out['final_status']})")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
