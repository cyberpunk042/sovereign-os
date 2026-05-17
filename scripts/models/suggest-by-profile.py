#!/usr/bin/env python3
"""scripts/models/suggest-by-profile.py — R214 profile-aware model suggester.

Given a master-spec § 18 runtime profile (ultra-sovereign-efficiency,
high-concurrency-burst, deep-context-synthesis), cross-references the
profile's `allocations` against the R212 model catalog and reports for
each Trinity agent:

  - declared model (verified-real / aspirational / unmapped)
  - vram requirement vs the allocation's vram_limit_bytes (when set)
  - alternative catalog entries (same class, smaller quantization) for
    downsizing when the declared model doesn't fit operator hardware

Operator-meaningful super-feature: turns the static profile YAML +
static catalog YAML into actionable runtime advice without the
operator manually cross-walking both files.

CLI:
  suggest-by-profile.py --runtime-profile high-concurrency-burst
  suggest-by-profile.py --runtime-profile <id> --json
  suggest-by-profile.py --list  (list known profile ids)

Exit codes:
  0  suggestions emitted
  1  every allocation flagged (no verified-real model / VRAM
     exceeded) — operator should redesign before running
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "models" / "catalog.yaml"
PROFILES_DIR = REPO_ROOT / "profiles" / "runtime"


def load_catalog() -> dict[str, dict[str, Any]]:
    with CATALOG_PATH.open() as fh:
        doc = yaml.safe_load(fh)
    return {m["id"]: m for m in doc["catalog"]["models"]}


def load_profile(pid: str) -> dict[str, Any] | None:
    p = PROFILES_DIR / f"{pid}.yaml"
    if not p.exists():
        return None
    with p.open() as fh:
        return yaml.safe_load(fh)["runtime_profile"]


def list_profile_ids() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def alternatives(catalog: dict[str, dict[str, Any]],
                 declared: dict[str, Any]) -> list[dict[str, Any]]:
    """Same `class` entries with vram_gib_min ≤ declared's."""
    declared_vram = declared.get("vram_gib_min")
    declared_class = declared.get("class")
    if not declared_class:
        return []
    out = []
    for m in catalog.values():
        if m["id"] == declared["id"]:
            continue
        if m.get("class") != declared_class:
            continue
        m_vram = m.get("vram_gib_min")
        if declared_vram is None or m_vram is None:
            continue
        if m_vram <= declared_vram:
            out.append(m)
    out.sort(key=lambda x: x.get("vram_gib_min") or 0)
    return out


def analyse(profile: dict[str, Any],
            catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    any_flagged = False
    for alloc in profile.get("allocations") or []:
        model_id = alloc.get("model")
        agent = alloc.get("agent_id", "?")
        tier = alloc.get("tier", "?")
        vram_limit = alloc.get("vram_limit_bytes")
        vram_limit_gib = (vram_limit / (1024**3)) if vram_limit else None

        declared = catalog.get(model_id)
        row: dict[str, Any] = {
            "agent_id": agent,
            "tier": tier,
            "declared_model": model_id,
            "vram_limit_gib": vram_limit_gib,
            "status": "unmapped",  # default
            "flags": [],
            "alternatives": [],
        }
        if declared is None:
            row["flags"].append(
                f"model {model_id!r} not in catalog — operator must "
                "add an entry to models/catalog.yaml"
            )
            any_flagged = True
        else:
            row["status"] = declared.get("status", "?")
            row["class"] = declared.get("class")
            row["quantization"] = declared.get("quantization")
            row["size_class"] = declared.get("size_class")
            row["vram_gib_min"] = declared.get("vram_gib_min")
            row["hf_repo_id"] = declared.get("hf_repo_id")
            if declared.get("status") == "aspirational":
                row["flags"].append(
                    "aspirational entry — operator must substitute the "
                    "closest_real_alternative until upstream ships the real model"
                )
                any_flagged = True
            if (
                vram_limit_gib is not None
                and declared.get("vram_gib_min") is not None
                and declared["vram_gib_min"] > vram_limit_gib
            ):
                row["flags"].append(
                    f"VRAM requirement {declared['vram_gib_min']} GiB exceeds "
                    f"allocation limit {vram_limit_gib:.1f} GiB"
                )
                any_flagged = True
                # Suggest smaller-quantization alternatives
                alts = alternatives(catalog, declared)
                alts = [a for a in alts if (a.get("vram_gib_min") or 0) <= vram_limit_gib]
                row["alternatives"] = [
                    {
                        "id": a["id"],
                        "quantization": a.get("quantization"),
                        "vram_gib_min": a.get("vram_gib_min"),
                        "status": a.get("status"),
                    }
                    for a in alts[:5]
                ]
        rows.append(row)
    return {
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "allocations": rows,
        "any_flagged": any_flagged,
    }


def render_text(analysis: dict[str, Any]) -> str:
    lines = []
    lines.append(
        f"── R214 model suggester ── runtime profile: "
        f"{analysis['profile_id']} ({analysis['profile_name']})\n"
    )
    for row in analysis["allocations"]:
        lines.append(f"Agent: {row['agent_id']}  (tier: {row['tier']})")
        lines.append(f"  Declared model:  {row['declared_model']}")
        if row["status"] != "unmapped":
            lines.append(
                f"  Catalog status:  {row['status']}"
                + (f"  class={row.get('class')}" if row.get("class") else "")
                + (f"  quant={row.get('quantization')}" if row.get("quantization") else "")
                + (f"  size={row.get('size_class')}" if row.get("size_class") else "")
            )
            if row.get("vram_gib_min") is not None:
                vlim = row.get("vram_limit_gib")
                vlim_str = f"{vlim:.1f} GiB" if vlim is not None else "(none)"
                lines.append(
                    f"  VRAM:            needs {row['vram_gib_min']} GiB"
                    f"  vs limit {vlim_str}"
                )
            if row.get("hf_repo_id"):
                lines.append(f"  HF repo id:      {row['hf_repo_id']}")
        for f in row["flags"]:
            lines.append(f"  ⚠ {f}")
        if row["alternatives"]:
            lines.append("  Suggested alternatives (same class, smaller quant):")
            for a in row["alternatives"]:
                lines.append(
                    f"    - {a['id']} ({a['quantization']}, "
                    f"{a['vram_gib_min']} GiB, status={a['status']})"
                )
        lines.append("")
    if analysis["any_flagged"]:
        lines.append(
            "⚠ At least one allocation flagged — see ⚠ markers above. "
            "Operator should resolve before running this profile."
        )
    else:
        lines.append(
            "✓ Every allocation maps to a verified-real catalog entry "
            "that fits its VRAM allocation."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Profile-aware model suggester — cross-reference a runtime "
            "profile's allocations against the R212 model catalog."
        )
    )
    p.add_argument("--runtime-profile", dest="profile", help="profile id (e.g. high-concurrency-burst)")
    p.add_argument("--list", action="store_true", help="list known profile ids and exit 0")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.list:
        for pid in list_profile_ids():
            print(pid)
        return 0

    if not args.profile:
        print("ERROR --runtime-profile or --list required", file=sys.stderr)
        return 2

    profile = load_profile(args.profile)
    if profile is None:
        print(
            f"ERROR runtime profile {args.profile!r} not found at "
            f"{PROFILES_DIR}/{args.profile}.yaml",
            file=sys.stderr,
        )
        return 2

    catalog = load_catalog()
    analysis = analyse(profile, catalog)

    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        sys.stdout.write(render_text(analysis))

    return 1 if analysis["any_flagged"] else 0


if __name__ == "__main__":
    sys.exit(main())
