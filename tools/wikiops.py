#!/usr/bin/env python3
"""tools/wikiops.py — the wiki-operability AI mode (2026-07-19).

Operator directive (verbatim, sacrosanct — full text at
docs/standing-directives/2026-07-19-notification-wiki-operability-mode.md):
"the ai will have a mode where it uses the wiki through python which
calls make changes, insertions, deletions or whatever operability to
the wiki aimed at or default one and it will allow to sent
notifications [...]"

Operator-confirmed resolution of the READ-ONLY tension (2026-07-19
evaluation): mutations dispatch through the TARGET WIKI'S OWN validated
tool chain — never direct file writes. For the info-hub that means its
tools (pipeline scaffold/post/crossref, gateway contribute/archive/move,
view search) with their quality gates intact; READ-ONLY narrows to "the
wiki's tools are the only mutation channel".

"aimed at or default one": a target-wiki registry (config/wikis.toml)
with a default — the project-maintainer --project/--target shape.

Discipline (project-maintainer precedent): mutating ops are DRY-RUN by
default; --apply executes. Outcomes emit a notifykit Event so the
operator's channel stack (ntfy/resend/twilio, gated by priority x
urgency) hears about applied mutations.

Verbs:
  targets                       list registered wikis (default flagged)
  run --op OP [--wiki W] [--apply] [--json] [args...]
                                dispatch OP to the target wiki's own
                                tools; DRY-RUN unless --apply
  ops [--wiki W]                the op->tool map for a target's kind

Ops per kind:
  info-hub  : scaffold post crossref contribute archive move search status
  generic   : (none yet — registered targets must declare kind info-hub;
              future kinds land with their own tool maps)

Exit codes: 0 ok/dry-run · 1 op failed · 2 usage/registry error
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "wikis.toml"

# The info-hub op → its OWN tool invocation (module, verb...). Mutations
# ONLY through these (operator-confirmed). {args} appends CLI args.
INFO_HUB_OPS: dict[str, dict[str, Any]] = {
    "scaffold":   {"module": "tools.pipeline", "verb": ["scaffold"], "mutates": True,
                   "what": "insert — scaffold a new page of a type"},
    "post":       {"module": "tools.pipeline", "verb": ["post"], "mutates": True,
                   "what": "change — run the 6-step validation chain (MANDATORY after wiki changes)"},
    "crossref":   {"module": "tools.pipeline", "verb": ["crossref"], "mutates": True,
                   "what": "change — discover + write cross-references"},
    "contribute": {"module": "tools.gateway", "verb": ["contribute"], "mutates": True,
                   "what": "insert — lesson/remark/correction through the contribute channel"},
    "archive":    {"module": "tools.gateway", "verb": ["archive"], "mutates": True,
                   "what": "delete — archive a page (the wiki's own deletion verb)"},
    "move":       {"module": "tools.gateway", "verb": ["move"], "mutates": True,
                   "what": "change — relocate a page"},
    "search":     {"module": "tools.view", "verb": ["search"], "mutates": False,
                   "what": "read — search wiki content"},
    "status":     {"module": "tools.pipeline", "verb": ["status"], "mutates": False,
                   "what": "read — wiki state report"},
}

OPS_BY_KIND: dict[str, dict[str, dict[str, Any]]] = {
    "info-hub": INFO_HUB_OPS,
}


def load_registry(path: Path) -> dict[str, Any]:
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib unavailable (python >= 3.11 required)")
    if not path.is_file():
        raise FileNotFoundError(
            f"wiki registry missing: {path} — copy config/wikis.toml.example")
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def resolve_target(reg: dict[str, Any], name: str | None) -> tuple[str, dict[str, Any]]:
    wikis = reg.get("wikis") or {}
    target = name or reg.get("default", "")
    if target not in wikis:
        raise KeyError(
            f"wiki {target!r} not in registry (have: {sorted(wikis)}; "
            f"default={reg.get('default')!r})")
    return target, wikis[target]


def build_command(wiki: dict[str, Any], op_spec: dict[str, Any],
                  args: list[str]) -> tuple[list[str], Path]:
    root = Path(os.path.expanduser(str(wiki["root"])))
    python = str(wiki.get("python", ".venv/bin/python"))
    py = root / python if not os.path.isabs(python) else Path(python)
    cmd = [str(py), "-m", op_spec["module"], *op_spec["verb"], *args]
    return cmd, root


def notify_outcome(op: str, target: str, ok: bool, applied: bool) -> None:
    """Emit the outcome through notifykit when a notify config exists.
    Priority/urgency defaults: applied mutations normal/normal; failures
    high/high. Silent no-op without a config — notification is opt-in."""
    cfg_path = os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG", "/etc/sovereign-os/notifykit.toml")
    if not os.path.isfile(cfg_path):
        return
    try:
        from tools.notifykit import ChannelRegistry, Event, NotifyConfig
        registry = ChannelRegistry(NotifyConfig.load(cfg_path))
        registry.dispatch(Event(
            title=f"wikiops {op} on {target}: {'ok' if ok else 'FAILED'}",
            message=(f"{'applied' if applied else 'dry-run'} "
                     f"{'succeeded' if ok else 'failed'}"),
            priority="normal" if ok else "high",
            urgency="normal" if ok else "high",
            source="wikiops",
        ))
    except Exception as e:  # notification must never break the op
        print(f"WARN notify failed: {e}", file=sys.stderr)


def cmd_targets(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    default = reg.get("default", "")
    rows = []
    for name, wiki in (reg.get("wikis") or {}).items():
        rows.append({
            "name": name, "kind": wiki.get("kind", "?"),
            "root": wiki.get("root", "?"), "default": name == default,
        })
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print("── wikiops targets ──")
    for r in rows:
        star = " (default)" if r["default"] else ""
        print(f"  {r['name']:16s} kind={r['kind']:10s} root={r['root']}{star}")
    return 0


def cmd_ops(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    target, wiki = resolve_target(reg, args.wiki)
    kind = str(wiki.get("kind", ""))
    ops = OPS_BY_KIND.get(kind)
    if ops is None:
        print(f"ERROR no op map for kind {kind!r}", file=sys.stderr)
        return 2
    print(f"── ops for {target} (kind={kind}) ──")
    for op, spec in ops.items():
        mark = "MUTATES" if spec["mutates"] else "read   "
        print(f"  {op:11s} [{mark}] {spec['what']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    reg = load_registry(args.registry)
    target, wiki = resolve_target(reg, args.wiki)
    kind = str(wiki.get("kind", ""))
    ops = OPS_BY_KIND.get(kind)
    if ops is None or args.op not in ops:
        known = sorted(ops) if ops else []
        print(f"ERROR unknown op {args.op!r} for kind {kind!r} "
              f"(known: {known})", file=sys.stderr)
        return 2
    spec = ops[args.op]
    # argparse.REMAINDER swallows flags that follow positionals — honor
    # --apply anywhere, and strip a leading "--" separator.
    passthrough = [a for a in args.args if a != "--"]
    apply_flag = bool(args.apply)
    if "--apply" in passthrough:
        apply_flag = True
        passthrough = [a for a in passthrough if a != "--apply"]
    cmd, cwd = build_command(wiki, spec, passthrough)

    apply_now = apply_flag or not spec["mutates"]
    if not apply_now:
        print("── wikiops DRY-RUN (mutating op; pass --apply to execute) ──")
        print(f"  target: {target} (kind={kind})")
        print(f"  cwd:    {cwd}")
        print(f"  would run: {' '.join(cmd)}")
        return 0

    if not cwd.is_dir():
        print(f"ERROR wiki root not present: {cwd}", file=sys.stderr)
        return 2
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    ok = r.returncode == 0
    if spec["mutates"]:
        notify_outcome(args.op, target, ok, applied=True)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wikiops.py",
        description="Wiki-operability mode — mutations only through the "
        "target wiki's own tool chain; DRY-RUN by default.",
    )
    p.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = p.add_subparsers(dest="verb", required=True)

    pt = sub.add_parser("targets", help="list registered wikis")
    pt.add_argument("--json", action="store_true")
    pt.set_defaults(func=cmd_targets)

    po = sub.add_parser("ops", help="op → tool map for a target")
    po.add_argument("--wiki")
    po.set_defaults(func=cmd_ops)

    pr = sub.add_parser("run", help="dispatch an op (dry-run unless --apply)")
    pr.add_argument("--op", required=True)
    pr.add_argument("--wiki")
    pr.add_argument("--apply", action="store_true",
                    help="execute a MUTATING op (read ops always run)")
    pr.add_argument("args", nargs=argparse.REMAINDER,
                    help="passed through to the wiki's own tool")
    pr.set_defaults(func=cmd_run)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    try:
        return args.func(args)
    except (FileNotFoundError, KeyError, RuntimeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
