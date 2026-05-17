#!/usr/bin/env python3
"""scripts/kernel/tuning.py — R239 (SDD-026 Z-14).

Operator-named (verbatim, 2026-05-17 expansion): "Kernel optimisation,
OS, Services, Modules, Tools, Dashboards, Configurations, Options.
Network, App, & In between."

Per-workload sysctl + cmdline tuning matrix. Operators declare named
presets in /etc/sovereign-os/kernel-tuning.toml; this script:

  list                       enumerate the named presets + summaries
  show [--preset NAME]       diff: declared values vs live /proc/sys
  apply <preset> [--dry-run] write the preset's sysctl values
  cmdline-hints <preset>     print GRUB_CMDLINE_LINUX additions

The script NEVER edits GRUB / kernel cmdline directly — operators paste
the hint output into /etc/default/grub by hand. Sysctl writes happen
in-process (root required) via `sysctl -w` per key for atomic accept/
reject.

Exit codes:
  0  command succeeded
  1  apply partially failed (some keys rejected by kernel)
  2  usage error / config missing / unknown preset / non-root for apply
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/kernel-tuning.toml")
DEV_CONFIG = REPO_ROOT / "config" / "kernel-tuning.toml.example"


def resolve_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("SOVEREIGN_OS_KERNEL_TUNING")
    if env:
        return Path(env)
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"presets": {}, "_source": "(missing)"}
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    if "presets" not in doc:
        doc["presets"] = {}
    doc["_source"] = str(path)
    return doc


def read_sysctl_live(key: str) -> str | None:
    """Read /proc/sys/<key>. Returns None if unreadable."""
    sub_path = Path("/proc/sys") / key.replace(".", "/")
    if not sub_path.exists():
        return None
    try:
        return sub_path.read_text().strip()
    except OSError:
        return None


def write_sysctl(key: str, value: str) -> tuple[bool, str]:
    """`sysctl -w KEY=VALUE`. Returns (ok, msg)."""
    if not shutil.which("sysctl"):
        return (False, "sysctl binary missing")
    try:
        r = subprocess.run(
            ["sysctl", "-w", f"{key}={value}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return (False, str(e))
    if r.returncode != 0:
        return (False, r.stderr.strip() or f"rc={r.returncode}")
    return (True, r.stdout.strip())


def cmd_list(args: argparse.Namespace) -> int:
    config = load_config(resolve_config_path(args.config))
    rows = []
    for name, preset in (config.get("presets") or {}).items():
        if not isinstance(preset, dict):
            continue
        sysctl = preset.get("sysctl") or {}
        cmdline = preset.get("cmdline_hints") or {}
        rows.append(
            {
                "preset": name,
                "summary": preset.get("summary", ""),
                "sysctl_keys": len(sysctl),
                "cmdline_hints_count": len(cmdline.get("hints") or []),
            }
        )
    rows.sort(key=lambda r: r["preset"])
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R239",
                    "vector": "SDD-026 Z-14 (kernel-tuning)",
                    "config_source": config.get("_source"),
                    "presets": rows,
                },
                indent=2,
            )
        )
        return 0
    print(f"── R239 sovereign-os kernel-tuning presets ({config.get('_source')}) ──")
    if not rows:
        print("  (no presets declared)")
        return 0
    for r in rows:
        print(
            f"  {r['preset']:<18}  {r['summary']}"
            f"  (sysctl={r['sysctl_keys']}, cmdline_hints={r['cmdline_hints_count']})"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    config = load_config(resolve_config_path(args.config))
    presets = config.get("presets") or {}
    if args.preset:
        if args.preset not in presets:
            print(f"ERROR unknown preset {args.preset!r}", file=sys.stderr)
            return 2
        target_presets = {args.preset: presets[args.preset]}
    else:
        target_presets = presets

    out: dict[str, Any] = {
        "round": "R239",
        "vector": "SDD-026 Z-14 (kernel-tuning show)",
        "config_source": config.get("_source"),
        "presets": {},
    }
    for name, preset in target_presets.items():
        sysctl = preset.get("sysctl") or {}
        diff_rows = []
        matches = 0
        diverges = 0
        unreadable = 0
        for key, declared in sysctl.items():
            live = read_sysctl_live(key)
            declared_s = str(declared)
            if live is None:
                state = "unreadable"
                unreadable += 1
            elif live == declared_s:
                state = "match"
                matches += 1
            else:
                state = "diverges"
                diverges += 1
            diff_rows.append(
                {
                    "key": key,
                    "declared": declared_s,
                    "live": live,
                    "state": state,
                }
            )
        out["presets"][name] = {
            "summary": preset.get("summary", ""),
            "counts": {
                "match": matches,
                "diverges": diverges,
                "unreadable": unreadable,
                "total": len(sysctl),
            },
            "diff": diff_rows,
        }

    if args.json:
        print(json.dumps(out, indent=2))
        # rc=1 if any preset has divergences (operator signal: re-apply
        # the preset to bring sysctl back to declared state).
        for p in out["presets"].values():
            if p["counts"]["diverges"] > 0:
                return 1
        return 0

    print(f"── R239 sovereign-os kernel-tuning show ({out['config_source']}) ──")
    any_diverge = False
    for name, p in out["presets"].items():
        c = p["counts"]
        print(
            f"\n  preset={name}  match={c['match']}  diverges={c['diverges']}  "
            f"unreadable={c['unreadable']}"
        )
        for d in p["diff"]:
            mark = {"match": "✓", "diverges": "≠", "unreadable": "?"}[d["state"]]
            print(f"    {mark} {d['key']}  declared={d['declared']}  live={d['live']}")
        if c["diverges"] > 0:
            any_diverge = True
    return 1 if any_diverge else 0


def cmd_apply(args: argparse.Namespace) -> int:
    config = load_config(resolve_config_path(args.config))
    presets = config.get("presets") or {}
    if args.preset not in presets:
        print(f"ERROR unknown preset {args.preset!r}", file=sys.stderr)
        return 2
    preset = presets[args.preset]
    sysctl = preset.get("sysctl") or {}
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")

    if not dry and os.geteuid() != 0:
        # Print actionable commands instead of failing per-key.
        cmds = [f"sudo sysctl -w {k}={v}" for k, v in sysctl.items()]
        print(
            f"# Not running as root — to apply preset {args.preset!r}:\n  "
            + "\n  ".join(cmds),
            file=sys.stderr,
        )
        return 2

    results: list[dict[str, Any]] = []
    failures = 0
    for key, value in sysctl.items():
        value_s = str(value)
        if dry:
            results.append(
                {"key": key, "value": value_s, "outcome": "dry-run", "detail": "would write"}
            )
            continue
        ok, msg = write_sysctl(key, value_s)
        results.append(
            {"key": key, "value": value_s, "outcome": "ok" if ok else "failed", "detail": msg}
        )
        if not ok:
            failures += 1

    report = {
        "round": "R239",
        "vector": "SDD-026 Z-14 (kernel-tuning apply)",
        "preset": args.preset,
        "dry_run": bool(dry),
        "summary": preset.get("summary", ""),
        "applied_count": sum(1 for r in results if r["outcome"] == "ok"),
        "failed_count": failures,
        "results": results,
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if failures else 0

    print(f"── R239 sovereign-os kernel-tuning apply ({args.preset}) ──")
    if dry:
        print("  DRY-RUN — no writes will happen")
    for r in results:
        mark = {"ok": "OK", "failed": "FAIL", "dry-run": "DRY"}.get(r["outcome"], "?")
        print(f"  [{mark}] {r['key']}={r['value']}  {r['detail']}")
    return 1 if failures else 0


def cmd_cmdline_hints(args: argparse.Namespace) -> int:
    config = load_config(resolve_config_path(args.config))
    presets = config.get("presets") or {}
    if args.preset not in presets:
        print(f"ERROR unknown preset {args.preset!r}", file=sys.stderr)
        return 2
    preset = presets[args.preset]
    cmdline = preset.get("cmdline_hints") or {}
    out = {
        "round": "R239",
        "preset": args.preset,
        "description": cmdline.get("description", ""),
        "hints": cmdline.get("hints") or [],
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R239 sovereign-os kernel-tuning cmdline-hints ({args.preset}) ──")
    if out["description"]:
        print(f"  {out['description']}")
    print()
    if not out["hints"]:
        print("  (no cmdline hints for this preset)")
        return 0
    for h in out["hints"]:
        print(f"    {h}")
    print()
    joined = " ".join(out["hints"])
    print(
        f"  # One-liner: append this to GRUB_CMDLINE_LINUX in\n"
        f"  # /etc/default/grub then `sudo update-grub && reboot`:\n"
        f"  {joined}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tuning.py",
        description="R239 (SDD-026 Z-14) — kernel-tuning preset matrix.",
    )
    p.add_argument("--config", type=Path, default=None)
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list", help="enumerate the named presets")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("show", help="diff declared vs live sysctl values")
    ps.add_argument("--preset", help="show only this preset")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_show)

    pa = sub.add_parser("apply", help="write a preset's sysctl values (root)")
    pa.add_argument("preset")
    pa.add_argument("--dry-run", action="store_true")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_apply)

    pc = sub.add_parser("cmdline-hints", help="print GRUB cmdline additions")
    pc.add_argument("preset")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_cmdline_hints)

    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
