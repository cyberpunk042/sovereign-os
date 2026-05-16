#!/usr/bin/env python3
"""scripts/hardware/lib/module-recommendations.py — single source of
truth for the selfdef-module recommendation matrix.

Closes SDD-019 T-5: R185 (osctl install suggest-modules) + R186
(wizard) previously hard-coded the SAME matrix in two places. This
module factors it out so a future cycle-3 change to the matrix
needs to land in ONE file.

Used as both a library (import the function) AND as a CLI:

  Library:
    from scripts.hardware.lib.module_recommendations \
        import recommend_modules
    mods = recommend_modules(profile="sain-01", has_avx512=True, gpu_count=2)
    # → ["hardware-tune-cache", "bitnet-gpu-inference"]

  CLI:
    $ scripts/hardware/lib/module-recommendations.py \
        --profile sain-01 --has-avx512 --gpu-count 2
    hardware-tune-cache
    bitnet-gpu-inference
"""

from __future__ import annotations

import argparse
import sys


# The matrix itself: explicit + auditable + operator-readable.
# Cross-referenced by SDD-018 D-9 (D-13 + R185 + R186 are the
# downstream consumers).
def recommend_modules(
    profile: str,
    *,
    has_avx512: bool,
    gpu_count: int,
) -> list[str]:
    """Return the recommended selfdef modules for a given profile +
    probed hardware. Returns an empty list when no modules are
    recommended (minimal / old-workstation profiles, or hardware
    that doesn't unlock cycle-2 features).

    Raises ValueError on unknown profile.
    """
    if profile == "sain-01":
        mods: list[str] = []
        if has_avx512:
            mods.append("hardware-tune-cache")
        if has_avx512 and gpu_count >= 1:
            mods.append("bitnet-gpu-inference")
        return mods
    if profile in ("developer", "headless"):
        return ["hardware-tune-cache"] if has_avx512 else []
    if profile in ("minimal", "old-workstation"):
        return []
    raise ValueError(
        f"unknown profile {profile!r};"
        " valid: sain-01, developer, headless, minimal, old-workstation"
    )


VALID_PROFILES = ("sain-01", "developer", "headless", "minimal", "old-workstation")


def _main_cli() -> int:
    p = argparse.ArgumentParser(
        description="Print recommended selfdef modules for a profile + hardware"
    )
    p.add_argument("--profile", required=True, choices=VALID_PROFILES)
    p.add_argument("--has-avx512", action="store_true")
    p.add_argument("--gpu-count", type=int, default=0)
    args = p.parse_args()
    try:
        mods = recommend_modules(
            args.profile,
            has_avx512=args.has_avx512,
            gpu_count=args.gpu_count,
        )
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2
    for m in mods:
        print(m)
    return 0


if __name__ == "__main__":
    sys.exit(_main_cli())
