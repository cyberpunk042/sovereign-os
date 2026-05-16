#!/usr/bin/env python3
"""scripts/hardware/selfdef-signing-audit.py — operator-facing
audit of module-manifest signing posture (R195).

selfdef SD-R55 (cycle 3) added an optional [signing] block to each
module.toml. Modules declaring `required = true` refuse to apply
without a valid minisign signature. This script walks the operator's
selfdef catalog + reports per-module signing posture so operators
audit their supply-chain coverage without needing to invoke
selfdefctl on every host.

CLI:
  selfdef-signing-audit.py                # human catalog overview
  selfdef-signing-audit.py --json         # machine-readable
  selfdef-signing-audit.py --dir <path>   # override modules dir

Exit codes:
  0  audit completed (regardless of how many modules are unsigned)
  1  one or more required-signed modules MISSING their .minisig
  2  argument / I/O error

Three states per module:
  - "no signing block"       (cycle-1+2 default; informational)
  - "signed-optional"        (required=false; .minisig may or may not exist)
  - "signed-required-valid"  (required=true; .minisig present)
  - "signed-required-missing" (required=true; .minisig ABSENT — gate would fail)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_MODULES_DIR = Path("/usr/share/selfdef/modules")


def parse_signing_block(manifest_path: Path) -> dict | None:
    """Tiny TOML reader for the [signing] block — same pattern as
    scripts/hardware/selfdef-modules-gate.py. Returns {} when the
    block exists without keys (still gives us the section marker),
    or None when no block is present."""
    if not manifest_path.exists():
        return None
    section: str | None = None
    out: dict = {}
    found = False
    for raw in manifest_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section == "signing":
                found = True
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip(",")
        if section == "signing":
            if v.startswith('"') and v.endswith('"'):
                out[k] = v[1:-1]
            elif v in ("true", "false"):
                out[k] = v == "true"
            else:
                out[k] = v
    return out if found else None


def classify(module_dir: Path) -> dict:
    """Returns a per-module dict with name, signing posture + state."""
    manifest = module_dir / "module.toml"
    minisig = manifest.with_suffix(".toml.minisig")
    signing = parse_signing_block(manifest)
    name = module_dir.name

    if signing is None:
        return {
            "name": name,
            "has_signing_block": False,
            "required": False,
            "minisig_present": minisig.exists(),
            "state": "no signing block",
        }

    required = bool(signing.get("required", False))
    minisig_present = minisig.exists()
    if not required:
        state = "signed-optional"
    elif minisig_present:
        state = "signed-required-valid"
    else:
        state = "signed-required-missing"
    return {
        "name": name,
        "has_signing_block": True,
        "required": required,
        "minisig_present": minisig_present,
        "trust_root": signing.get("trust_root"),
        "state": state,
    }


def walk_catalog(dir_: Path) -> list[dict]:
    if not dir_.exists() or not dir_.is_dir():
        return []
    out = []
    for entry in sorted(dir_.iterdir()):
        if (entry / "module.toml").exists():
            out.append(classify(entry))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="audit selfdef module-manifest signing posture (R195)")
    p.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("SELFDEF_MODULES_DIR", str(DEFAULT_MODULES_DIR))),
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    rows = walk_catalog(args.dir)
    if not rows:
        sys.stderr.write(f"no modules found in {args.dir}\n")
        return 2

    counts = {
        "no_signing_block": sum(1 for r in rows if r["state"] == "no signing block"),
        "signed_optional": sum(1 for r in rows if r["state"] == "signed-optional"),
        "signed_required_valid": sum(
            1 for r in rows if r["state"] == "signed-required-valid"
        ),
        "signed_required_missing": sum(
            1 for r in rows if r["state"] == "signed-required-missing"
        ),
    }
    rc = 1 if counts["signed_required_missing"] > 0 else 0

    if args.json:
        print(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "modules_dir": str(args.dir),
                    "total": len(rows),
                    "counts": counts,
                    "modules": rows,
                },
                indent=2,
            )
        )
        return rc

    print("# R195: selfdef module-manifest signing audit")
    print(f"# {len(rows)} module(s) in {args.dir}")
    print(
        f"# counts: unsigned={counts['no_signing_block']}"
        f" optional={counts['signed_optional']}"
        f" required-valid={counts['signed_required_valid']}"
        f" required-missing={counts['signed_required_missing']}"
    )
    if counts["signed_required_missing"] > 0:
        print(
            "# ⚠ apply will FAIL on hosts running these required-but-missing modules"
        )
    print()
    print(f"{'STATE':<26}  {'MODULE':<28}  notes")
    for r in rows:
        marker = {
            "no signing block": " ",
            "signed-optional": "·",
            "signed-required-valid": "✓",
            "signed-required-missing": "✗",
        }.get(r["state"], "?")
        notes = ""
        if r.get("trust_root"):
            notes = f"trust_root={r['trust_root']}"
        print(f"{marker} {r['state']:<24}  {r['name']:<28}  {notes}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
