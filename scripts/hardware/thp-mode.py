#!/usr/bin/env python3
"""scripts/hardware/thp-mode.py — R553 (E11.M16) Transparent HugePage mode.

Operator §1g (verbatim, sacrosanct):
  "AVX-512 + 256GB RAM"  /  "1-bit / ternary models in ZMM"

Orthogonal to R552 (HugePages sizer, which reserves *static*
hugepages). THP is the *opportunistic* path — kernel-collapsed
2MiB pages whenever a memory region is contiguous and large enough.

THP mode is a global Linux knob with three values exposed via
/sys/kernel/mm/transparent_hugepage/enabled:

  always   — THP for ALL anonymous mappings. Highest TLB win,
             but the daemon (khugepaged) sometimes stalls userspace
             during compaction → unpredictable inference latency.

  madvise  — THP ONLY for mappings tagged with MADV_HUGEPAGE.
             llama.cpp / vllm / bitnet inference does NOT issue
             MADV_HUGEPAGE today; with `madvise` mode they get
             plain 4KiB pages but no compaction stalls. Predictable.
             This is the operator-default for sustained-burst / peak-
             inference workload-modes.

  never    — no THP at all. Predictable + lowest TLB hit rate.
             Used for benchmarking baselines.

A separate knob /sys/kernel/mm/transparent_hugepage/defrag controls
when khugepaged collapses pages (`always` → eager + can stall;
`defer` → background only; `madvise` → only for tagged mappings;
`never` → no compaction).

Verbs:
  show / status   — print current enabled + defrag state.
  set <mode>      — write enabled. Requires root.
  set-defrag <mode> — write defrag. Requires root.
  policy <slug>   — operator-defined presets:
                    inference     enabled=madvise  defrag=defer
                    bench         enabled=never    defrag=never
                    aggressive    enabled=always   defrag=defer

Read-mostly philosophy: show/status NEVER write.

Exit codes:
  0  ok
  1  partial write (enabled wrote, defrag didn't, or vice versa)
  2  usage / not-root / invalid mode / kernel without THP
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

THP_BASE = Path("/sys/kernel/mm/transparent_hugepage")
ENABLED = THP_BASE / "enabled"
DEFRAG = THP_BASE / "defrag"

VALID_ENABLED = {"always", "madvise", "never"}
VALID_DEFRAG = {"always", "defer", "defer+madvise", "madvise", "never"}

POLICIES: dict[str, dict[str, str]] = {
    "inference": {
        "enabled": "madvise",
        "defrag": "defer",
        "rationale": (
            "predictable inference latency — no compaction stalls; "
            "engines without MADV_HUGEPAGE fall back to R552 reserved "
            "hugepages"
        ),
    },
    "bench": {
        "enabled": "never",
        "defrag": "never",
        "rationale": "benchmarking baseline — 4KiB pages, no THP at all",
    },
    "aggressive": {
        "enabled": "always",
        "defrag": "defer",
        "rationale": (
            "highest TLB hit rate; tolerable when latency-jitter is "
            "acceptable (batch fine-tune / data prep / build pipelines)"
        ),
    },
}


def _read_bracket(p: Path) -> str | None:
    """THP sysctl files have a /value [active] / value/ shape. Pluck
    the bracketed active value."""
    if not p.is_file():
        return None
    try:
        raw = p.read_text().strip()
    except OSError:
        return None
    m = re.search(r"\[([^\]]+)\]", raw)
    if m:
        return m.group(1)
    # Some kernels emit a plain value with no brackets.
    return raw.split()[0] if raw else None


def gather_state() -> dict[str, Any]:
    return {
        "thp_available": THP_BASE.is_dir(),
        "enabled": _read_bracket(ENABLED),
        "defrag": _read_bracket(DEFRAG),
        "policies": list(POLICIES),
    }


def render_human(state: dict[str, Any]) -> str:
    lines = ["── sovereign-os Transparent HugePage state (R553 / E11.M16) ──"]
    if not state["thp_available"]:
        lines.append("THP: NOT AVAILABLE (kernel built without THP support)")
        return "\n".join(lines)
    lines.append(f"enabled : {state['enabled']}")
    lines.append(f"defrag  : {state['defrag']}")
    lines.append(f"policies: {', '.join(state['policies'])}")
    return "\n".join(lines)


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "[thp-mode] this verb requires root. Re-run with sudo.",
            file=sys.stderr,
        )
        sys.exit(2)


def write_sysctl(path: Path, value: str) -> int:
    require_root()
    if not path.is_file():
        print(
            f"[thp-mode] {path} not present — kernel lacks THP support.",
            file=sys.stderr,
        )
        return 2
    try:
        path.write_text(f"{value}\n")
    except OSError as e:
        print(f"[thp-mode] write failed: {e}", file=sys.stderr)
        return 1
    print(f"[thp-mode] {path.name} = {value}")
    return 0


def set_enabled(mode: str) -> int:
    if mode not in VALID_ENABLED:
        print(
            f"[thp-mode] invalid enabled mode {mode!r}; "
            f"valid: {sorted(VALID_ENABLED)}",
            file=sys.stderr,
        )
        return 2
    return write_sysctl(ENABLED, mode)


def set_defrag(mode: str) -> int:
    if mode not in VALID_DEFRAG:
        print(
            f"[thp-mode] invalid defrag mode {mode!r}; "
            f"valid: {sorted(VALID_DEFRAG)}",
            file=sys.stderr,
        )
        return 2
    return write_sysctl(DEFRAG, mode)


def apply_policy(slug: str) -> int:
    if slug not in POLICIES:
        print(
            f"[thp-mode] unknown policy {slug!r}; "
            f"valid: {sorted(POLICIES)}",
            file=sys.stderr,
        )
        return 2
    pol = POLICIES[slug]
    rc_e = set_enabled(pol["enabled"])
    rc_d = set_defrag(pol["defrag"])
    if rc_e != 0 and rc_d == 0:
        return 1
    if rc_d != 0 and rc_e == 0:
        return 1
    return rc_e or rc_d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="thp-mode",
        description="Transparent HugePage controller (R553 / E11.M16).",
    )
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_set = sub.add_parser("set")
    sp_set.add_argument("mode", choices=sorted(VALID_ENABLED))
    sp_defrag = sub.add_parser("set-defrag")
    sp_defrag.add_argument("mode", choices=sorted(VALID_DEFRAG))
    sp_pol = sub.add_parser("policy")
    sp_pol.add_argument("slug", choices=sorted(POLICIES))
    sp_pol_list = sub.add_parser("list-policies")
    sp_pol_list.add_argument("--json", action="store_true", dest="json_sub")
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    if verb in ("show", "status"):
        state = gather_state()
        if json_out:
            print(json.dumps(state, indent=2))
        else:
            print(render_human(state))
        return 0
    if verb == "list-policies":
        if json_out:
            print(json.dumps(POLICIES, indent=2))
        else:
            for slug, pol in POLICIES.items():
                print(
                    f"  {slug:14s} enabled={pol['enabled']:8s} "
                    f"defrag={pol['defrag']:14s} — {pol['rationale']}"
                )
        return 0
    if verb == "set":
        return set_enabled(args.mode)
    if verb == "set-defrag":
        return set_defrag(args.mode)
    if verb == "policy":
        return apply_policy(args.slug)
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
