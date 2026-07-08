#!/usr/bin/env python3
"""scripts/observability/cost-policy.py — the cost-policy WRITE surface (D-04).

The read side (`sovereign-osctl costs summary/policy/today/export`) lives in
cost-tracker.py. This is the deliberately-separate write side: flip
`cloud_enabled` in /etc/sovereign-os/cost-policy.toml so the operator can HALT
all cloud spend (or resume it) from the cockpit.

Safety (matches the sanctioned R10274 pattern):
  - DRY-RUN by DEFAULT — a real write needs `--confirm` AND (via the exec daemon)
    the operator key + type-to-confirm + SOVEREIGN_OS_ACTION_EXEC_LIVE=1.
    `SOVEREIGN_OS_DRY_RUN=1` forces dry-run regardless.
  - stdlib-only: tomllib to read, a small hand-serializer to write (no tomli_w).

Verbs:
  cost-policy show                     print the resolved policy (read-only)
  cost-policy halt-cloud   [--confirm] set cloud_enabled=false (stops cloud spend)
  cost-policy resume-cloud [--confirm] set cloud_enabled=true

Exit codes: 0 ok / dry-run · 1 write error · 2 usage error.
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

POLICY_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_COST_POLICY", "/etc/sovereign-os/cost-policy.toml"))

# Verbatim keys (parity with cost-tracker.py POLICY_DEFAULTS). Only cloud_enabled
# is mutated here; the rest are preserved on write.
DEFAULTS: dict[str, Any] = {
    "cloud_enabled": False,
    "cloud_requires_approval": True,
    "daily_budget_usd": None,
    "per_request_max_usd": None,
    "private_paths_never_cloud": True,
    "log_prompts": "local_only",
}


def load(path: Path = POLICY_PATH) -> dict[str, Any]:
    """Resolve the policy: file values over sovereign-safe defaults."""
    policy = dict(DEFAULTS)
    if path.is_file():
        try:
            with path.open("rb") as fh:
                doc = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError, ValueError):
            return policy
        for k in DEFAULTS:
            if k in doc:
                policy[k] = doc[k]
    return policy


def serialize(policy: dict[str, Any]) -> str:
    """Hand-serialize the flat policy to TOML (stdlib has no writer). None →
    an explanatory comment (TOML has no null; absence = the safe default)."""
    out = [
        "# /etc/sovereign-os/cost-policy.toml — operator cost policy.",
        "# Managed by `sovereign-osctl cost-policy` (halt-cloud / resume-cloud).",
        "# Absent keys fall back to sovereign-safe defaults (see cost-tracker.py).",
        "",
    ]
    for k, v in policy.items():
        if v is None:
            out.append(f"# {k} = <unset — safe default applies>")
        elif isinstance(v, bool):
            out.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            out.append(f"{k} = {v}")
        else:
            out.append(f'{k} = "{v}"')
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="cost-policy write surface (D-04)")
    ap.add_argument("verb", choices=("show", "halt-cloud", "resume-cloud"))
    ap.add_argument("--confirm", action="store_true",
                    help="apply the write (default is dry-run)")
    args = ap.parse_args(argv)

    policy = load()
    if args.verb == "show":
        print(serialize(policy), end="")
        return 0

    target = args.verb == "resume-cloud"  # halt-cloud → False, resume-cloud → True
    policy["cloud_enabled"] = target
    dry = (not args.confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    if dry:
        why = "no --confirm" if not args.confirm else "SOVEREIGN_OS_DRY_RUN=1"
        print(f"DRY-RUN ({why}): would set cloud_enabled = "
              f"{'true' if target else 'false'} in {POLICY_PATH}")
        print(serialize(policy), end="")
        return 0
    try:
        POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
        POLICY_PATH.write_text(serialize(policy))
    except OSError as e:
        print(f"ERROR writing {POLICY_PATH}: {e}", file=sys.stderr)
        return 1
    print(f"cloud_enabled = {'true' if target else 'false'} written to {POLICY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
