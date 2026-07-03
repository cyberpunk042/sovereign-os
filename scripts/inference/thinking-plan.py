#!/usr/bin/env python3
"""scripts/inference/thinking-plan.py — SDD-043 Phase 4: the thinking router's planner.

Given a request, produce the ORCHESTRATION PLAN across the tiers: which
tier answers, and whether to escalate into a "thinking" flow —
chain-of-thought on a reasoning model, a Validator pass, self-consistency
sampling, MoE expert gating. It composes the primitives that already exist
as crates (sovereign-router-7axis, sovereign-self-consistency,
sovereign-best-of-n, sovereign-moe-gate, sovereign-confidence-calibration,
sovereign-answer-extract) into a per-request policy decision.

The plan is DATA, not execution — deterministic and testable; the runtime
carries it out. Base tier classification is reused verbatim from the
shipped router (scripts/inference/router.py) so this never diverges from
where a request actually routes.

Resolves SDD-043 Q-3/Q-4 the sovereign way — not by hardcoding a thinking
model or fixing the validator's home, but by making both POLICY FIELDS
(defaulted, overridable per profile):
  - think.model_class    which class does the chain-of-thought (default rlm)
  - validate.mode        pass (a re-check within the flow) | tier (a
                         distinct validator tier) | off       (default pass)
So the operator picks the topology; the code stays flexible.

Usage:
  thinking-plan.py --prompt "prove sqrt(2) irrational" [--task-type reasoning]
                   [--policy <yaml>] [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER = REPO_ROOT / "scripts" / "inference" / "router.py"

# Default thinking policy. Every field is overridable via --policy / a
# profile `thinking_policy` block — nothing is cemented.
DEFAULT_POLICY: dict = {
    # When to escalate a plain route into the thinking flow.
    "escalate": {
        "task_types": ["reasoning"],       # these task types always think
        "tiers": ["oracle_core"],          # oracle-bound requests think
        "explicit_flag": "sovereign_os_think",  # a request may force it
    },
    # Chain-of-thought on a reasoning model.
    "think": {"enabled": True, "model_class": ["rlm", "mixture"]},
    # Validator: pass (re-check inside the flow) | tier (distinct 4th tier) | off.
    "validate": {"mode": "pass", "model_class": ["rlm"]},
    # Self-consistency: draw N samples + vote (sovereign-self-consistency).
    # 1 = off.
    "self_consistency": {"samples": 1},
    # MoE expert gating (sovereign-moe-gate) — only when the target is a
    # mixture model.
    "moe": {"enabled": False, "top_k": 2},
}


def _router():
    spec = importlib.util.spec_from_file_location("router", ROUTER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def _active_runtime_profile_policy() -> dict | None:
    """The `thinking_policy` block of the ACTIVE runtime profile, if any.
    Resolution mirrors runtime-profile.sh: SOVEREIGN_OS_RUNTIME_PROFILE, then
    /etc/… or ~/.sovereign-os/active-runtime-profile → profiles/runtime/<id>.yaml."""
    import os
    rid = os.environ.get("SOVEREIGN_OS_RUNTIME_PROFILE")
    if not rid:
        for cand in ("/etc/sovereign-os/active-runtime-profile",
                     str(Path.home() / ".sovereign-os" / "active-runtime-profile")):
            if Path(cand).is_file():
                rid = Path(cand).read_text().strip()
                break
    if not rid:
        return None
    yml = REPO_ROOT / "profiles" / "runtime" / f"{rid}.yaml"
    if not yml.is_file():
        return None
    import yaml
    doc = yaml.safe_load(yml.read_text()) or {}
    return (doc.get("runtime_profile") or {}).get("thinking_policy")


def load_policy(path: Path | None = None, override: dict | None = None) -> dict:
    """Compose the policy: DEFAULT_POLICY ← active-profile thinking_policy ←
    --policy file ← explicit override. Later sources win; each is sparse."""
    policy = DEFAULT_POLICY
    prof_policy = _active_runtime_profile_policy()
    if prof_policy:
        policy = _deep_merge(policy, prof_policy)
    if path is not None:
        import yaml
        doc = yaml.safe_load(Path(path).read_text()) or {}
        policy = _deep_merge(policy, doc.get("thinking_policy") or doc)
    if override:
        policy = _deep_merge(policy, override)
    return policy


def plan(body: dict, policy: dict | None = None, router=None) -> dict:
    """Return the orchestration plan for a request body."""
    policy = policy or DEFAULT_POLICY
    router = router or _router()

    tier = router.classify(body)
    task_type = router.classify_task_type(body)
    model_class = router.classify_model_class(body)

    esc = policy["escalate"]
    reasons: list[str] = []
    escalate = False
    if task_type in esc.get("task_types", []):
        escalate = True
        reasons.append(f"task_type={task_type} → escalate")
    if tier in esc.get("tiers", []):
        escalate = True
        reasons.append(f"tier={tier} → escalate")
    if esc.get("explicit_flag") and body.get(esc["explicit_flag"]):
        escalate = True
        reasons.append(f"{esc['explicit_flag']}=set → escalate")
    if not escalate:
        reasons.append("simple request → direct route, no thinking")

    steps: list[dict] = []
    if escalate and policy["think"].get("enabled"):
        steps.append({"step": "think", "primitive": "chain-of-thought",
                      "model_class": policy["think"]["model_class"], "tier": "oracle"})
        vmode = policy["validate"].get("mode", "pass")
        if vmode != "off":
            steps.append({"step": "validate", "mode": vmode,
                          "primitive": "answer-extract+confidence-calibration",
                          "model_class": policy["validate"]["model_class"]})
        n = int(policy["self_consistency"].get("samples", 1) or 1)
        if n > 1:
            steps.append({"step": "self_consistency", "primitive": "sovereign-self-consistency",
                          "samples": n})
        if policy["moe"].get("enabled") and model_class == "mixture":
            steps.append({"step": "moe", "primitive": "sovereign-moe-gate",
                          "top_k": policy["moe"].get("top_k", 2)})

    return {
        "route_tier": tier,
        "task_type": task_type,
        "model_class": model_class,
        "escalated": escalate,
        "steps": steps,
        "rationale": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="thinking-router planner (SDD-043 P4)")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--task-type", help="hint: reasoning|code|chat|… (sovereign_os_task_type)")
    ap.add_argument("--think", action="store_true", help="force escalation (sovereign_os_think)")
    ap.add_argument("--policy", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    body: dict = {"messages": [{"role": "user", "content": args.prompt}]}
    if args.task_type:
        body["sovereign_os_task_type"] = args.task_type
    if args.think:
        body["sovereign_os_think"] = True

    p = plan(body, load_policy(args.policy))
    if args.json:
        print(json.dumps(p, indent=2))
    else:
        print(f"route: {p['route_tier']}  (task_type={p['task_type']}, class={p['model_class']})")
        print(f"escalated: {p['escalated']}")
        for s in p["steps"]:
            extra = {k: v for k, v in s.items() if k not in ("step", "primitive")}
            print(f"  → {s['step']}  [{s['primitive']}]  {extra}")
        for r in p["rationale"]:
            print(f"  · {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
