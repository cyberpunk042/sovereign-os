"""sovereign-os profile mixin merger — resolves parent + mixins → effective profile.

Q-002 substantive closure. Per SDD-004 § Inheritance model:
  Hybrid: single-parent inheritance + cross-cutting mixins.

Merge order (last applied wins on scalar conflicts):
  1. Mixins (in declaration order, first → last)
  2. Parent profile (if identity.parent is set)
  3. This profile (child)

Deterministic rules per SDD-004 § Inheritance:
  - Scalars: child > parent > mixins (last-applied wins)
  - Lists: child appends to parent + mixins; profile.packages.deny
    entries REMOVE matching items from packages.{base,profile} +
    role.<name>
  - Maps: deep-merge with child-wins-on-conflict
  - Mixin-vs-mixin scalar conflict: BUILD FAILS (no silent precedence)

Usage:
  python3 -m tools.profile_merger profiles/sain-01.yaml
  → prints the effective profile (YAML) with all mixins resolved
"""

from __future__ import annotations

import argparse
import copy
import pathlib
import sys
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILE_DIR = REPO_ROOT / "profiles"
MIXIN_DIR = PROFILE_DIR / "mixins"


class MergeError(RuntimeError):
    """Raised on mixin-vs-mixin scalar conflict (no silent precedence)."""


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_profile(profile_id: str) -> dict[str, Any]:
    p = PROFILE_DIR / f"{profile_id}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"profile not found: {p}")
    return load_yaml(p)


def load_mixin(mixin_id: str) -> dict[str, Any]:
    p = MIXIN_DIR / f"{mixin_id}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"mixin not found: {p}")
    return load_yaml(p)


def is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def merge_two(
    base: dict[str, Any],
    overlay: dict[str, Any],
    *,
    strict_scalar_conflict: bool = False,
    overlay_label: str = "overlay",
    base_label: str = "base",
) -> dict[str, Any]:
    """Deep-merge `overlay` into `base`, returning a new dict.

    - Scalars: overlay wins (unless strict_scalar_conflict, then raises
      MergeError on disagreement)
    - Lists: overlay appended to base
    - Maps: recursive deep-merge
    """
    result = copy.deepcopy(base)
    for key, ov in overlay.items():
        if key not in result:
            result[key] = copy.deepcopy(ov)
            continue
        existing = result[key]
        # Recurse on maps
        if isinstance(existing, dict) and isinstance(ov, dict):
            result[key] = merge_two(
                existing,
                ov,
                strict_scalar_conflict=strict_scalar_conflict,
                overlay_label=overlay_label,
                base_label=base_label,
            )
        # Append lists
        elif isinstance(existing, list) and isinstance(ov, list):
            # Avoid duplicate string entries (package lists etc.) while
            # preserving operator-declared ordering
            seen = {repr(x) for x in existing}
            for item in ov:
                if repr(item) not in seen:
                    existing.append(copy.deepcopy(item))
                    seen.add(repr(item))
            result[key] = existing
        # Scalar override
        elif is_scalar(existing) and is_scalar(ov):
            if strict_scalar_conflict and existing != ov:
                raise MergeError(
                    f"scalar conflict on key '{key}': "
                    f"{base_label}={existing!r} vs {overlay_label}={ov!r}; "
                    f"two mixins cannot disagree on the same scalar field"
                )
            result[key] = ov
        else:
            # Type mismatch — overlay wins (operator-intentional override)
            result[key] = copy.deepcopy(ov)
    return result


def merge_mixins(mixin_ids: list[str]) -> dict[str, Any]:
    """Merge multiple mixin docs in declaration order.

    Mixin-vs-mixin scalar conflicts raise MergeError per SDD-004.
    """
    if not mixin_ids:
        return {}
    accumulator: dict[str, Any] = {}
    for mid in mixin_ids:
        raw = load_mixin(mid)
        # Mixin files have a 'mixin:' identity block + same top-level
        # keys as profiles. We merge from the contribution-side keys
        # (everything except the 'mixin:' metadata).
        contrib = {k: v for k, v in raw.items() if k not in ("mixin", "schema_version")}
        if not accumulator:
            accumulator = copy.deepcopy(contrib)
        else:
            accumulator = merge_two(
                accumulator,
                contrib,
                strict_scalar_conflict=True,
                overlay_label=f"mixin:{mid}",
                base_label=f"previous-mixins({','.join(mixin_ids[:mixin_ids.index(mid)])})",
            )
    return accumulator


def apply_deny_list(effective: dict[str, Any]) -> dict[str, Any]:
    """packages.deny entries remove matching items from packages.{base,profile} and role.*.

    Deny matching uses exact-string match by default. A future enhancement
    could add glob patterns; for now operators write the full package name.
    """
    pkgs = effective.get("packages")
    if not isinstance(pkgs, dict):
        return effective
    deny: list[str] = pkgs.get("deny") or []
    if not deny:
        return effective
    deny_set = set(deny)

    def strip(lst: list[str]) -> list[str]:
        return [x for x in lst if x not in deny_set]

    if isinstance(pkgs.get("base"), list):
        pkgs["base"] = strip(pkgs["base"])
    if isinstance(pkgs.get("profile"), list):
        pkgs["profile"] = strip(pkgs["profile"])
    if isinstance(pkgs.get("role"), dict):
        for role_name, role_pkgs in list(pkgs["role"].items()):
            if isinstance(role_pkgs, list):
                pkgs["role"][role_name] = strip(role_pkgs)

    return effective


def resolve(profile_id: str, _seen: list[str] | None = None) -> dict[str, Any]:
    """Resolve a profile + parent chain + mixins → effective profile.

    Order: mixins (collected from this profile's mixins:) → parent
    (recursively resolved) → this profile.
    """
    seen = _seen or []
    if profile_id in seen:
        raise RuntimeError(f"profile inheritance cycle: {' → '.join(seen + [profile_id])}")

    profile = load_profile(profile_id)
    seen = seen + [profile_id]

    # Step 1: resolve mixins (this profile's mixins, in declaration order)
    mixins = profile.get("mixins") or []
    mixin_merged = merge_mixins(mixins) if mixins else {}

    # Step 2: resolve parent (recursive)
    parent_id = (profile.get("identity") or {}).get("parent")
    parent_effective: dict[str, Any] = {}
    if parent_id:
        parent_effective = resolve(parent_id, seen)

    # Step 3: merge order — mixin_merged → parent → child
    layered = merge_two(
        mixin_merged,
        parent_effective,
        strict_scalar_conflict=False,
        overlay_label=f"parent:{parent_id}",
        base_label="mixins",
    )
    effective = merge_two(
        layered,
        profile,
        strict_scalar_conflict=False,
        overlay_label=f"profile:{profile_id}",
        base_label="mixins+parent",
    )

    # Step 4: apply packages.deny
    effective = apply_deny_list(effective)

    return effective


def main() -> int:
    ap = argparse.ArgumentParser(description="sovereign-os profile mixin merger")
    ap.add_argument("profile", help="profile id (e.g. sain-01) or path to YAML")
    ap.add_argument("--format", choices=["yaml", "json"], default="yaml")
    args = ap.parse_args()

    # Accept either an id or a path
    arg = args.profile
    if "/" in arg or arg.endswith(".yaml"):
        profile_id = pathlib.Path(arg).stem
    else:
        profile_id = arg

    try:
        effective = resolve(profile_id)
    except (FileNotFoundError, RuntimeError, MergeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.format == "json":
        import json

        json.dump(effective, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        yaml.safe_dump(effective, sys.stdout, sort_keys=False, default_flow_style=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
