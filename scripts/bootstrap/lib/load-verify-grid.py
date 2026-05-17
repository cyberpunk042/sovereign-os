#!/usr/bin/env python3
"""scripts/bootstrap/lib/load-verify-grid.py — R207 verify-grid metadata loader.

Parses config/bootstrap/verify-grid.yaml and emits one record per
check:

  ID|NAME|MASTER_SPEC_SECTION|CHECKS_WHAT

The full doc renderer reads the YAML directly via pyyaml; this loader
exists for the shell consumer (verify.sh CHECK_NAMES array) so verify
metadata can never drift from its rendered doc.

Exit codes:
  0 — table emitted
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
YAML_PATH = REPO_ROOT / "config" / "bootstrap" / "verify-grid.yaml"


def main() -> int:
    if not YAML_PATH.exists():
        print(f"ERROR verify-grid.yaml not found at {YAML_PATH}", file=sys.stderr)
        return 2

    with YAML_PATH.open() as fh:
        doc = yaml.safe_load(fh)

    checks = doc.get("verify_grid", {}).get("checks", []) if isinstance(doc, dict) else []
    if not checks:
        print("ERROR verify-grid.yaml has no checks list", file=sys.stderr)
        return 2

    for c in checks:
        fields = [c["id"], c["name"], c["master_spec_section"], c["checks_what"]]
        if any("|" in f for f in fields):
            print("ERROR verify-grid.yaml field contains '|' separator", file=sys.stderr)
            return 2
        print("|".join(fields))
    return 0


if __name__ == "__main__":
    sys.exit(main())
