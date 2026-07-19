#!/usr/bin/env python3
"""operator-rules — retain + re-apply the operator's Claude Code interaction
rules across a fresh flash / new build.

The rules are the operator-behaviour memory the AI agent must obey — the
operator is always the driver, their words are sacrosanct, do not minimize,
ask when unclear, no random side-quests, mid-work messages are interrupts,
etc. They live in Claude Code's PER-PROJECT memory at
``~/.claude/projects/<project>/memory/``, which a fresh flash would wipe.

This module versions them inside sovereign-os (``assets/operator-memory/``)
and re-applies them on provision / on demand, so the OS RETAINS them with
NO dependency on any other project. If the operator never opts into
root-modules, this alone keeps the rules intact.

Verbs:
  status    show drift between the versioned store and the live memory dir
  apply     copy store -> live memory dir (the fresh-flash re-apply; idempotent)
  capture   copy live memory dir -> store (version new / edited rules)
  compat    check cross-module path-disjointness vs root-modules

Cross-module boundary (why the two never collide):
  root-modules (optional, endpoint mode) owns ~/.claude/ GLOBAL config —
  settings.json / CLAUDE.md / hooks/ / rules/ / skills/. THIS module owns
  ONLY ~/.claude/projects/<project>/memory/. Disjoint paths => no clobber.

Paths:
  store   <repo>/assets/operator-memory/
  live    ~/.claude/projects/<repo-path with '/'->'-'>/memory/
          (override via SOVEREIGN_OS_CLAUDE_MEMORY_DIR — used by tests /
          relocation)
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Versioned store (override via env for tests / relocation).
STORE = Path(os.environ.get(
    "SOVEREIGN_OS_OPERATOR_MEMORY_STORE",
    str(REPO_ROOT / "assets" / "operator-memory"),
))

# Claude Code keys per-project memory by the absolute project path with
# '/' replaced by '-'. For /home/jfortin/sovereign-os that is
# '-home-jfortin-sovereign-os'. Derive from the repo root so a fresh flash
# (same path, /home is retained) resolves to the same project key.
PROJECT_KEY = str(REPO_ROOT).replace("/", "-")
_DEFAULT_LIVE = Path.home() / ".claude" / "projects" / PROJECT_KEY / "memory"
LIVE = Path(os.environ.get("SOVEREIGN_OS_CLAUDE_MEMORY_DIR", str(_DEFAULT_LIVE)))

# root-modules GLOBAL-config surfaces under ~/.claude/ (NOT under
# projects/). Our LIVE dir must stay disjoint from every one of these so the
# two modules can both be installed without clobbering each other.
_GLOBAL_CLAUDE = Path.home() / ".claude"
GHOSTPROXY_OWNED = [
    _GLOBAL_CLAUDE / "settings.json",
    _GLOBAL_CLAUDE / "CLAUDE.md",
    _GLOBAL_CLAUDE / "hooks",
    _GLOBAL_CLAUDE / "rules",
    _GLOBAL_CLAUDE / "skills",
    _GLOBAL_CLAUDE / "agents",
    _GLOBAL_CLAUDE / "commands",
    _GLOBAL_CLAUDE / "modes",
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _store_files() -> list[Path]:
    return sorted(STORE.glob("*.md")) if STORE.is_dir() else []


def _live_files() -> list[Path]:
    return sorted(LIVE.glob("*.md")) if LIVE.is_dir() else []


def _classify() -> dict:
    """Compare store vs live -> {only_store, only_live, changed, identical}."""
    store = {p.name for p in _store_files()}
    live = {p.name for p in _live_files()}
    changed = sorted(
        n for n in (store & live)
        if not filecmp.cmp(STORE / n, LIVE / n, shallow=False)
    )
    identical = sorted(
        n for n in (store & live)
        if filecmp.cmp(STORE / n, LIVE / n, shallow=False)
    )
    return {
        "only_store": sorted(store - live),   # would be installed by apply
        "only_live": sorted(live - store),    # would be versioned by capture
        "changed": changed,
        "identical": identical,
    }


def cmd_status(args) -> int:
    c = _classify()
    if args.json:
        print(json.dumps({
            "store": str(STORE), "live": str(LIVE),
            "project_key": PROJECT_KEY, **c,
            "in_sync": not (c["only_store"] or c["only_live"] or c["changed"]),
        }, indent=2))
        return 0
    print(f"store: {STORE}")
    print(f"live:  {LIVE}")
    print(f"project: {PROJECT_KEY}")
    print(f"  {len(_store_files())} versioned rule(s), {len(_live_files())} live")
    if c["only_store"]:
        print(f"  apply would INSTALL (absent live): {', '.join(c['only_store'])}")
    if c["changed"]:
        print(f"  apply would UPDATE (differs): {', '.join(c['changed'])}")
    if c["only_live"]:
        print(f"  capture would VERSION (live-only): {', '.join(c['only_live'])}")
    if not (c["only_store"] or c["only_live"] or c["changed"]):
        print("  ✓ in sync")
    return 0


def _copy_set(src_dir: Path, dst_dir: Path, dry_run: bool,
              backup: bool, label: str) -> int:
    """Copy every *.md from src_dir into dst_dir, idempotently. Backs up a
    differing destination first (when backup=True). Returns changed count."""
    srcs = sorted(src_dir.glob("*.md"))
    if not srcs:
        print(f"  (no *.md in {src_dir} — nothing to {label})")
        return 0
    if not dry_run:
        dst_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    for s in srcs:
        d = dst_dir / s.name
        existed = d.exists()
        if existed and filecmp.cmp(s, d, shallow=False):
            continue
        if dry_run:
            print(f"  would {'update' if existed else 'install'}: {s.name}")
            changed += 1
            continue
        if backup and existed:
            bdir = dst_dir / ".backups"
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(d, bdir / f"{s.name}.{_utc_stamp()}.bak")
        shutil.copy2(s, d)
        print(f"  {'updated' if existed else 'installed'}: {s.name}")
        changed += 1
    if changed == 0:
        print(f"  ✓ already current ({label} no-op)")
    return changed


def cmd_apply(args) -> int:
    """Re-apply the versioned rules into the live memory dir (fresh-flash
    re-apply). Idempotent; backs up any differing live file first."""
    if not _store_files():
        print(f"ERROR: no versioned rules at {STORE}", file=sys.stderr)
        return 2
    print(f"apply: {STORE} -> {LIVE}"
          + ("  (dry-run)" if args.dry_run else ""))
    n = _copy_set(STORE, LIVE, args.dry_run, backup=True, label="apply")
    print(f"  {n} file(s) {'would change' if args.dry_run else 'changed'}")
    return 0


def cmd_capture(args) -> int:
    """Version live rule edits back into the repo store (so new / edited
    rules become part of sovereign-os and survive the next flash)."""
    if not _live_files():
        print(f"ERROR: no live rules at {LIVE}", file=sys.stderr)
        return 2
    print(f"capture: {LIVE} -> {STORE}"
          + ("  (dry-run)" if args.dry_run else ""))
    n = _copy_set(LIVE, STORE, args.dry_run, backup=False, label="capture")
    print(f"  {n} file(s) {'would change' if args.dry_run else 'changed'}")
    if not args.dry_run and n:
        print("  → commit assets/operator-memory/ to retain across flashes")
    return 0


def cmd_compat(args) -> int:
    """Verify the cross-module boundary: our live memory dir must live under
    ~/.claude/projects/<project>/memory/ and be disjoint from every
    root-modules-owned ~/.claude/ global surface — so both modules can be
    installed without clobbering one another."""
    problems: list[str] = []
    live_resolved = LIVE.resolve() if LIVE.exists() else LIVE
    projects_root = (_GLOBAL_CLAUDE / "projects").resolve()
    # (1) our dir must be under ~/.claude/projects/ (unless test-overridden)
    overridden = "SOVEREIGN_OS_CLAUDE_MEMORY_DIR" in os.environ
    under_projects = str(live_resolved).startswith(str(projects_root))
    if not overridden and not under_projects:
        problems.append(
            f"live memory dir {live_resolved} is NOT under {projects_root}"
        )
    # (2) our dir must not BE or be inside any ghostproxy-owned surface
    for owned in GHOSTPROXY_OWNED:
        o = owned.resolve() if owned.exists() else owned
        if live_resolved == o or str(live_resolved).startswith(str(o) + os.sep):
            problems.append(f"COLLISION: our dir overlaps ghostproxy-owned {owned}")
    gp_present = (Path.home() / "root-modules").is_dir() or (Path.home() / "root-ghostproxy").is_dir()
    if args.json:
        print(json.dumps({
            "live": str(LIVE),
            "ghostproxy_checkout_present": gp_present,
            "ghostproxy_owned_global_surfaces": [str(p) for p in GHOSTPROXY_OWNED],
            "disjoint": not problems,
            "problems": problems,
        }, indent=2))
        return 0 if not problems else 1
    print(f"cross-module compat (sovereign-os operator-rules ⟷ root-modules)")
    print(f"  our memory dir:        {LIVE}")
    print(f"  ghostproxy owns:       ~/.claude/{{settings.json,CLAUDE.md,hooks,rules,skills,agents,commands,modes}}")
    print(f"  root-modules here:     {'yes (~/root-modules or legacy ~/root-ghostproxy)' if gp_present else 'no'}")
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("  ✓ disjoint paths — both modules coexist without clobbering")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="operator-rules",
        description="Retain + re-apply the operator's Claude Code interaction "
                    "rules across a fresh flash (sovereign-os-owned).",
    )
    sub = ap.add_subparsers(dest="verb", required=True)
    p_status = sub.add_parser("status", help="show store↔live drift")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)
    p_apply = sub.add_parser("apply", help="store → live (fresh-flash re-apply)")
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.set_defaults(func=cmd_apply)
    p_capture = sub.add_parser("capture", help="live → store (version edits)")
    p_capture.add_argument("--dry-run", action="store_true")
    p_capture.set_defaults(func=cmd_capture)
    p_compat = sub.add_parser("compat", help="check disjointness vs root-modules")
    p_compat.add_argument("--json", action="store_true")
    p_compat.set_defaults(func=cmd_compat)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
