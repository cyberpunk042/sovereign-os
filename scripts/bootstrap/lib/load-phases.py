#!/usr/bin/env python3
"""scripts/bootstrap/lib/load-phases.py — phase-table loader (R202).

Parses config/bootstrap/phases.yaml and emits one pipe-delimited
record per phase:

  ID|NAME|DESCRIPTION|ARTIFACT1|ARTIFACT2|...

This is the canonical source consumed by:
  scripts/bootstrap/phases.sh  (R160 — inventory mode)
  scripts/bootstrap/run.sh     (R201 — dry-run plan)

Drift policy: when a phase changes, edit phases.yaml only.

Exit codes:
  0 — phase table emitted
  2 — yaml malformed or missing
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    print("ERROR pyyaml not installed", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "bootstrap" / "phases.yaml"


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR phases.yaml not found at {YAML_PATH}", file=sys.stderr)
        return 2

    with YAML_PATH.open() as fh:
        doc = yaml.safe_load(fh)

    phases = doc.get("phases", []) if isinstance(doc, dict) else []
    if not phases:
        print("ERROR phases.yaml has no 'phases' list", file=sys.stderr)
        return 2

    for p in phases:
        pid = p["id"]
        name = p["name"]
        desc = p["description"]
        artifacts = p.get("artifacts", [])
        fields = [pid, name, desc, *artifacts]
        if any("|" in f for f in fields):
            print("ERROR phases.yaml field contains '|' separator", file=sys.stderr)
            return 2
        print("|".join(fields))
    return 0


if __name__ == "__main__":
    sys.exit(main())
