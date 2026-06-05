#!/usr/bin/env python3
"""scripts/inference/scheduler-bridge.py — READ-ONLY consumer of the
selfdef MS048 Goldilocks Scheduler decision (the cross-repo "combine"
seam, Solution 1 ← Solution 2).

The sovereign-os runtime gateway consults the selfdef IPS-side scheduler
to get a hardware-aware routing decision for a model request. This bridge
is the CONSUMER side of the integration contract shipped in
`cyberpunk042/selfdef/docs/operator/ms048-scheduler-integration-contract.md`:
it builds a task descriptor, invokes the `selfdef-scheduler-decide`
producer binary, parses the returned `Decision`, and maps the route to a
runtime backend tier — honoring the three consumer obligations:

  1. honor Hibernate  — never force a deferred request onto a tier
  2. map route → tier — Blackwell→oracle, Rtx3090→scout, Cpu→cortex
  3. read-only        — the runtime NEVER writes selfdef IPS state

PROJECT-BOUNDARY DISCIPLINE (operator: "Respect the projects"): the
routing DECISION lives in selfdef. sovereign-os only invokes it
(read-only subprocess) + consumes the result. The runtime's own backend
selection (SDD-011 vLLM/bitnet/llama.cpp) consumes this as a hardware-tier
hint; it does not re-implement the Goldilocks decision.

Sovereignty: stdlib-only. Binary absent / errored → honest "scheduler
unavailable" verdict (the gateway falls back to its own SDD-011 routing),
NEVER a crash and NEVER a fabricated route.

Binary path overridable via SELFDEF_SCHEDULER_DECIDE_BIN
(default /usr/bin/selfdef-scheduler-decide).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

DEFAULT_BIN = os.environ.get(
    "SELFDEF_SCHEDULER_DECIDE_BIN", "/usr/bin/selfdef-scheduler-decide"
)

# Route → runtime backend tier (the integration contract's consumer
# obligation #2). Hybrid keeps the runtime's own split logic; hibernate is
# the defer signal (obligation #1). Keys are the Decision's serialized
# (lowercase) route values, matching the selfdef_scheduler_decisions_by_route
# Prometheus labels.
ROUTE_TO_TIER = {
    "blackwell": "oracle",
    "rtx3090": "scout",
    "cpu": "cortex",
    "hybrid": "hybrid",
    "hibernate": "defer",
}
HIBERNATE_ROUTE = "hibernate"

# Abstract tier role → the runtime's actual inference service (per
# scripts/inference/INDEX.md + router.py: Pulse=bitnet.cpp on CPU, Logic
# Engine=vLLM on RTX 3090, Oracle Core=vLLM+DFlash on Blackwell). This makes
# the scheduler's hardware-tier decision directly actionable by the gateway —
# it names which of the three running services to dispatch to. `hybrid` leaves
# the split to the runtime; `defer` is the Hibernate signal (no service).
TIER_TO_SERVICE = {
    "oracle": "Oracle Core",
    "scout": "Logic Engine",
    "cortex": "Pulse",
    "hybrid": None,  # runtime decides the split
    "defer": None,  # deferred — no service
}

VALID_PROFILES = {
    "fast",
    "careful",
    "private",
    "autonomous",
    "experimental",
    "production",
}


def build_task(
    profile: str,
    latency: float = 0.5,
    cost: float = 0.5,
    risk: float = 0.5,
    energy: float = 0.5,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the task descriptor the producer expects (the 4 model-estimated
    axes; the two substrate axes are measured by the binary, never sent)."""
    task: dict[str, Any] = {
        "profile": profile,
        "latency": latency,
        "cost": cost,
        "risk": risk,
        "energy": energy,
    }
    if request_id:
        task["request_id"] = request_id
    return task


def consult(task: dict[str, Any], binary: str = DEFAULT_BIN, timeout: float = 5.0) -> dict[str, Any]:
    """Invoke selfdef-scheduler-decide with the task; return a consumer
    verdict. Graceful-offline: when the binary is missing/errors, returns
    a `scheduler_available=False` verdict so the gateway falls back to its
    own routing — never raises, never fabricates a route."""
    try:
        proc = subprocess.run(
            [binary],
            input=json.dumps(task),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, PermissionError, OSError) as e:
        return _unavailable(f"binary not invocable: {e}")
    except subprocess.TimeoutExpired:
        return _unavailable("decide timed out")

    if proc.returncode != 0:
        return _unavailable(
            f"decide exit {proc.returncode}: {proc.stderr.strip()[:200]}"
        )
    try:
        decision = json.loads(proc.stdout)
    except (ValueError, json.JSONDecodeError) as e:
        return _unavailable(f"unparseable decision: {e}")

    route = decision.get("route", "")
    tier = ROUTE_TO_TIER.get(route, "unknown")
    return {
        "scheduler_available": True,
        "route": route,
        "backend_tier": tier,
        # the actual runtime service the gateway dispatches to (None for
        # hybrid/defer — runtime decides / request is deferred)
        "runtime_service": TIER_TO_SERVICE.get(tier),
        # obligation #1 — the gateway must defer, not force a tier
        "defer": route == HIBERNATE_ROUTE,
        "compound": decision.get("axis_scores", {}).get("compound"),
        "rationale": decision.get("rationale", ""),
        "request_id": decision.get("request_id", ""),
        "decision": decision,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "scheduler_available": False,
        "route": None,
        "backend_tier": None,
        "defer": False,  # gateway uses its own routing; not a scheduler defer
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    p.add_argument("--latency", type=float, default=0.5)
    p.add_argument("--cost", type=float, default=0.5)
    p.add_argument("--risk", type=float, default=0.5)
    p.add_argument("--energy", type=float, default=0.5)
    p.add_argument("--request-id", default=None)
    p.add_argument("--bin", default=DEFAULT_BIN)
    p.add_argument("--json", action="store_true", help="emit full verdict JSON")
    args = p.parse_args(argv)

    task = build_task(
        args.profile, args.latency, args.cost, args.risk, args.energy, args.request_id
    )
    verdict = consult(task, binary=args.bin)
    if args.json:
        print(json.dumps(verdict, indent=2))
    elif verdict["scheduler_available"]:
        line = f"route={verdict['route']} tier={verdict['backend_tier']}"
        if verdict.get("runtime_service"):
            line += f" service={verdict['runtime_service']!r}"
        if verdict["defer"]:
            line += " (DEFER — gateway must not force a tier)"
        print(line)
    else:
        print(f"scheduler unavailable ({verdict['reason']}) — gateway uses SDD-011 routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
