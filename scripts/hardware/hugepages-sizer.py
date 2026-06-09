#!/usr/bin/env python3
"""scripts/hardware/hugepages-sizer.py — R552 (E11.M15) HugePages sizer.

Operator §1g (verbatim, sacrosanct):
  "AVX-512 + 256GB RAM"  /  "Wasm-to-AVX-512 AOT"
  "1-bit / ternary models in ZMM"

The sain-01 baseline (256GB DDR5 + RTX PRO 6000 96GB + RTX 3090 24GB)
runs llama.cpp / vllm / bitnet inference on huge weight tensors. The
Linux page allocator's 4KB pages cause TLB pressure that costs 5-15%
throughput on CPU-side inference; 2MB hugepages cut the working-set
TLB entries by 512×. Gigantic 1GB pages eliminate them entirely
for the static weight regions.

This sizer ships THREE verbs:

  show         current /proc/meminfo HugePages_* counters per page-size.
  recommend    take --target-gb N (or --models <path>) and compute the
               nr_hugepages_2mb / nr_hugepages_1gb that should be
               reserved given total RAM + working-set demand.
  apply        write the recommended nr_hugepages via sysctl (transient)
               AND persist to /etc/sysctl.d/99-sovereign-hugepages.conf
               (sticks across reboots). Requires root.

Read-mostly philosophy (mirrors cpu-mode.py / nvidia-mps.py):
  show / recommend  NEVER write.
  apply             writes + persists, requires root.

Gigantic (1GB) pages need to be reserved AT BOOT (kernel cmdline
hugepagesz=1G hugepages=N) — they cannot be allocated post-boot
because no contiguous 1GB physical region remains. `apply --gigantic`
WRITES the recommended cmdline fragment to a file the operator can
copy into GRUB, but does NOT modify GRUB directly (sovereignty
boundary; bootloader edits are operator-signed only).

Exit codes:
  0  ok (or show on hosts without hugepages support — graceful)
  1  apply rc partial (sysctl ok, persistence write failed; or vice
     versa)
  2  usage error / requires root / invalid recommendation inputs
  3  apply requested but no hugepages backing in /proc/meminfo
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PROC_MEMINFO = Path("/proc/meminfo")
HUGEPAGES_SYS = Path("/sys/kernel/mm/hugepages")
PERSIST_PATH = Path("/etc/sysctl.d/99-sovereign-hugepages.conf")
GIGANTIC_CMDLINE_PATH = Path(
    "/etc/sovereign-os/hugepages-gigantic.cmdline"
)


# ── Probes ──────────────────────────────────────────────────────────


def read_meminfo() -> dict[str, int]:
    """Return /proc/meminfo as kB-valued ints. Empty dict on failure."""
    if not PROC_MEMINFO.is_file():
        return {}
    out: dict[str, int] = {}
    try:
        for line in PROC_MEMINFO.read_text().splitlines():
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            v = v.strip()
            if v.endswith(" kB"):
                v = v[:-3].strip()
            try:
                out[k.strip()] = int(v)
            except ValueError:
                # AnonHugePages_ may be a string in odd kernels;
                # skip non-numeric.
                continue
    except OSError:
        return {}
    return out


def enumerate_hugepage_sizes() -> list[dict[str, Any]]:
    """For each /sys/kernel/mm/hugepages/hugepages-NkB dir, report
    size_kb, nr_pages, free_pages, surplus, reserved."""
    out: list[dict[str, Any]] = []
    if not HUGEPAGES_SYS.is_dir():
        return out
    for entry in sorted(HUGEPAGES_SYS.iterdir()):
        m = re.match(r"hugepages-(\d+)kB", entry.name)
        if not m:
            continue
        size_kb = int(m.group(1))
        rec: dict[str, Any] = {"size_kb": size_kb}
        for f in ("nr_hugepages", "free_hugepages", "surplus_hugepages",
                  "resv_hugepages"):
            p = entry / f
            if p.is_file():
                try:
                    rec[f] = int(p.read_text().strip())
                except (OSError, ValueError):
                    rec[f] = None
        out.append(rec)
    return out


# ── State assembly ──────────────────────────────────────────────────


def gather_state() -> dict[str, Any]:
    mi = read_meminfo()
    sizes = enumerate_hugepage_sizes()
    return {
        "mem_total_kb": mi.get("MemTotal"),
        "mem_available_kb": mi.get("MemAvailable"),
        "hugepages_total_count": mi.get("HugePages_Total"),
        "hugepages_free_count": mi.get("HugePages_Free"),
        "hugepagesize_kb": mi.get("Hugepagesize"),
        "anon_hugepages_kb": mi.get("AnonHugePages"),
        "transparent_hugepage": _read_thp_state(),
        "per_size": sizes,
        "persist_path": str(PERSIST_PATH),
        "persist_exists": PERSIST_PATH.is_file(),
        "gigantic_cmdline_path": str(GIGANTIC_CMDLINE_PATH),
        "gigantic_cmdline_exists": GIGANTIC_CMDLINE_PATH.is_file(),
    }


def _read_thp_state() -> str | None:
    p = Path("/sys/kernel/mm/transparent_hugepage/enabled")
    if not p.is_file():
        return None
    try:
        return p.read_text().strip()
    except OSError:
        return None


# ── Recommendation ──────────────────────────────────────────────────


def recommend(target_gb: int, total_mem_kb: int | None,
              size_kb: int = 2048) -> dict[str, Any]:
    """Compute nr_hugepages for a target_gb backing, given total RAM.

    Caps the reservation at 75% of total RAM (HARD limit; reserving
    more risks OOM-kill of system processes). Returns rec + warnings.
    """
    warnings: list[str] = []
    # A negative target is nonsensical — a typo in the operator-set
    # /etc/sovereign-os/hugepages.target-gb file, or a bad CLI arg. Never
    # let it propagate into a negative nr_pages: that would be written
    # verbatim into /proc/sys/vm/nr_hugepages, the persisted sysctl.d
    # file (`vm.nr_hugepages = -N`), or a GRUB `hugepages=-N` cmdline
    # fragment (a broken boot parameter). Clamp to 0 and surface it. The
    # CLI additionally hard-rejects negatives with exit 2 ("invalid
    # recommendation inputs") before reaching here.
    if target_gb < 0:
        warnings.append(
            f"target_gb={target_gb} is negative; clamping to 0 "
            f"(negative reservations are invalid)"
        )
        target_gb = 0
    target_kb = target_gb * 1024 * 1024
    nr_pages = (target_kb + size_kb - 1) // size_kb
    if total_mem_kb is not None:
        cap_kb = (total_mem_kb * 75) // 100
        if target_kb > cap_kb:
            capped_pages = cap_kb // size_kb
            warnings.append(
                f"target {target_gb} GiB exceeds 75% of {total_mem_kb//1024//1024} "
                f"GiB total RAM; capping to {capped_pages} pages "
                f"({capped_pages * size_kb // 1024 // 1024} GiB)"
            )
            nr_pages = capped_pages
    if size_kb == 1048576 and target_gb < 1:
        warnings.append(
            "gigantic 1GiB pages require target_gb >= 1 to be useful"
        )
    return {
        "target_gb": target_gb,
        "page_size_kb": size_kb,
        "nr_pages": nr_pages,
        "reserved_kb": nr_pages * size_kb,
        "reserved_gb": (nr_pages * size_kb) // (1024 * 1024),
        "warnings": warnings,
    }


# ── Mutators ────────────────────────────────────────────────────────


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "[hugepages-sizer] this verb requires root. Re-run with sudo.",
            file=sys.stderr,
        )
        sys.exit(2)


def apply_2mb(nr_pages: int) -> int:
    """Write vm.nr_hugepages via sysctl AND persist."""
    if not Path("/proc/sys/vm/nr_hugepages").is_file():
        print(
            "[hugepages-sizer] /proc/sys/vm/nr_hugepages absent — "
            "kernel built without hugepages support.",
            file=sys.stderr,
        )
        return 3
    require_root()
    # 1) transient apply
    try:
        Path("/proc/sys/vm/nr_hugepages").write_text(f"{nr_pages}\n")
    except OSError as e:
        print(
            f"[hugepages-sizer] sysctl write failed: {e}", file=sys.stderr,
        )
        return 1
    # 2) persist
    try:
        PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        PERSIST_PATH.write_text(
            "# sovereign-os R552 (E11.M15) — managed by hugepages-sizer.py\n"
            "# Do not edit by hand; run `sovereign-osctl hugepages apply` instead.\n"
            f"vm.nr_hugepages = {nr_pages}\n"
        )
    except OSError as e:
        print(
            f"[hugepages-sizer] persist write failed: {e}", file=sys.stderr,
        )
        return 1
    print(
        f"[hugepages-sizer] applied vm.nr_hugepages={nr_pages} "
        f"(persisted to {PERSIST_PATH})"
    )
    return 0


def emit_gigantic_cmdline(nr_pages: int) -> int:
    """Write the GRUB cmdline fragment for gigantic 1GB hugepages.
    Does NOT modify GRUB itself (sovereignty boundary)."""
    require_root()
    try:
        GIGANTIC_CMDLINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        GIGANTIC_CMDLINE_PATH.write_text(
            "# sovereign-os R552 (E11.M15) — gigantic 1GB hugepage cmdline\n"
            "# Append to GRUB_CMDLINE_LINUX in /etc/default/grub then\n"
            "# run `update-grub`. Boot-time only; cannot be applied live.\n"
            f"hugepagesz=1G hugepages={nr_pages} default_hugepagesz=1G\n"
        )
    except OSError as e:
        print(
            f"[hugepages-sizer] cmdline emit failed: {e}", file=sys.stderr,
        )
        return 1
    print(
        f"[hugepages-sizer] gigantic cmdline written to "
        f"{GIGANTIC_CMDLINE_PATH} — copy into GRUB_CMDLINE_LINUX + "
        f"`update-grub` to take effect on next boot."
    )
    return 0


# ── Renderers ───────────────────────────────────────────────────────


def render_show_human(state: dict[str, Any]) -> str:
    lines = ["── sovereign-os HugePages state (R552 / E11.M15) ──"]
    mt = state.get("mem_total_kb")
    ma = state.get("mem_available_kb")
    lines.append(
        f"RAM       : total={_kb_to_gib(mt)} GiB  "
        f"available={_kb_to_gib(ma)} GiB"
    )
    hps = state.get("hugepagesize_kb")
    lines.append(
        f"page size : {hps if hps is not None else '(unknown)'} kB  "
        f"(default)"
    )
    lines.append(
        f"reserved  : total={state.get('hugepages_total_count')}  "
        f"free={state.get('hugepages_free_count')}"
    )
    anon = state.get("anon_hugepages_kb")
    if anon is not None:
        lines.append(f"THP usage : {_kb_to_gib(anon)} GiB (AnonHugePages)")
    thp = state.get("transparent_hugepage")
    if thp:
        lines.append(f"THP state : {thp}")
    per = state.get("per_size") or []
    if per:
        lines.append("by size :")
        for rec in per:
            sz = rec["size_kb"]
            lines.append(
                f"   {sz:>7} kB  nr={rec.get('nr_hugepages')}  "
                f"free={rec.get('free_hugepages')}  "
                f"resv={rec.get('resv_hugepages')}"
            )
    lines.append(
        f"persist   : {state['persist_path']}  "
        f"{'(exists)' if state['persist_exists'] else '(absent)'}"
    )
    lines.append(
        f"gigantic  : {state['gigantic_cmdline_path']}  "
        f"{'(exists)' if state['gigantic_cmdline_exists'] else '(absent)'}"
    )
    return "\n".join(lines)


def _kb_to_gib(kb: int | None) -> str:
    if kb is None:
        return "?"
    return f"{kb / 1024 / 1024:.1f}"


def render_recommend_human(rec: dict[str, Any]) -> str:
    sz_kb = rec["page_size_kb"]
    sz_label = "2MB" if sz_kb == 2048 else (
        "1GB" if sz_kb == 1048576 else f"{sz_kb}kB"
    )
    lines = [
        f"── HugePages recommendation ({sz_label}) ──",
        f"target          : {rec['target_gb']} GiB",
        f"nr_pages        : {rec['nr_pages']}",
        f"reserved        : {rec['reserved_gb']} GiB "
        f"({rec['reserved_kb']} kB)",
    ]
    for w in rec.get("warnings", []):
        lines.append(f"warning         : {w}")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="hugepages-sizer",
        description=(
            "Sovereign-os HugePages sizer (R552 / E11.M15). Inference "
            "engines (llama.cpp / vllm / bitnet) gain 5-15% throughput "
            "from huge-page-backed weight tensors."
        ),
    )
    p.add_argument("--json", action="store_true", help="JSON output")
    sub = p.add_subparsers(dest="verb")
    sp_show = sub.add_parser("show")
    sp_show.add_argument("--json", action="store_true", dest="json_sub")
    sp_status = sub.add_parser("status")
    sp_status.add_argument("--json", action="store_true", dest="json_sub")
    sp_rec = sub.add_parser("recommend")
    sp_rec.add_argument("--target-gb", type=int, required=True,
                        help="target reserved hugepage memory in GiB")
    sp_rec.add_argument("--gigantic", action="store_true",
                        help="recommend 1GiB pages instead of 2MiB")
    sp_rec.add_argument("--json", action="store_true", dest="json_sub")
    sp_apply = sub.add_parser("apply")
    sp_apply.add_argument("--target-gb", type=int, required=True)
    sp_apply.add_argument("--gigantic", action="store_true")
    args = p.parse_args(argv)
    verb = args.verb or "show"
    json_out = bool(args.json or getattr(args, "json_sub", False))

    # Enforce the documented exit-2 contract ("invalid recommendation
    # inputs"). A negative target is a typo, never an intent — reject it
    # before any /proc or persistence write can be reached. 0 is allowed
    # (it frees all reservations).
    if verb in ("recommend", "apply") and args.target_gb < 0:
        print(
            f"[hugepages-sizer] invalid --target-gb {args.target_gb}: "
            f"must be >= 0 (0 frees all reservations).",
            file=sys.stderr,
        )
        return 2

    if verb in ("show", "status"):
        state = gather_state()
        if json_out:
            print(json.dumps(state, indent=2))
        else:
            print(render_show_human(state))
        return 0
    if verb == "recommend":
        mi = read_meminfo()
        size_kb = 1048576 if args.gigantic else 2048
        rec = recommend(args.target_gb, mi.get("MemTotal"), size_kb)
        if json_out:
            print(json.dumps(rec, indent=2))
        else:
            print(render_recommend_human(rec))
        return 0
    if verb == "apply":
        mi = read_meminfo()
        size_kb = 1048576 if args.gigantic else 2048
        rec = recommend(args.target_gb, mi.get("MemTotal"), size_kb)
        if args.gigantic:
            return emit_gigantic_cmdline(rec["nr_pages"])
        return apply_2mb(rec["nr_pages"])
    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
