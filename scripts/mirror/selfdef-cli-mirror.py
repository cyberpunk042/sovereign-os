#!/usr/bin/env python3
"""scripts/mirror/selfdef-cli-mirror.py — READ-ONLY consumer of the
selfdef CLI schema mirror (MS007 typed-mirror crate selfdef-cli-mirror,
MS043 R10281 + R10297).

The selfdefctl binary's full subcommand tree projected as a wire-stable
JSON schema — used by sovereign-os for IPS-operator-surface
introspection, completion generation, "how do I do X" cross-links,
+ MCP-client tool-pickers showing the effect-class ladder.

CROSS-REPO MIRROR: the canonical schema is built by the selfdefctl
binary itself walking its live `clap::Command` tree
(selfdef-cli/cli_mirror_builder). The selfdef daemon shells out once
at startup, caches the bytes, and republishes them to
/run/sovereign-os/selfdef-mirror/cli.json on every export tick.
sovereign-os reads it READ-ONLY.

Doctrine surface preserved verbatim per MS043 R10297, dump 581:

  "Fullstack at the edges"

Mirror artifact (selfdef-cli-mirror::CliMirrorSnapshot 1.0.0):
  schema_version · cli_build_version · doctrine · captured_at ·
  summaries[{effect,count}] · subcommands[{path,help_summary,
  help_long,effect_class,min_authority,args,mirror,
  requires_signature,p95_target_ms,signature}] · signature

Sovereignty: stdlib-only. Absent artifact → empty subcommands +
offline mirror_status (graceful), NEVER a crash.

  selfdef-cli-mirror.py snapshot  [--json]    full schema
  selfdef-cli-mirror.py summaries [--json]    per-effect-class tiles
  selfdef-cli-mirror.py mutating  [--json]    only signature-required verbs
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# Verbatim doctrine surface — must NOT be paraphrased (R10297).
DOCTRINE = "Fullstack at the edges"

CLI_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_CLI_MIRROR",
    "/run/sovereign-os/selfdef-mirror/cli.json",
))

# 8 effect classes per the cli-mirror wire schema (MS039 authority ladder).
EFFECT_CLASSES = (
    "read_only", "diagnostic", "simulate", "prepare",
    "execute", "commit", "persist", "destructive",
)

# 4 ArgKind variants — see selfdef-cli-mirror::ArgKind.
ARG_KINDS = ("positional", "flag", "option", "multi_option")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _arg_specs(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        kind = a.get("kind", "option")
        if kind not in ARG_KINDS:
            kind = "option"
        out.append({
            "name":           str(a.get("name", "")),
            "kind":           kind,
            "required":       bool(a.get("required", False)),
            "help":           str(a.get("help", "")),
            "default":        a.get("default"),  # may be null
            "allowed_values": [str(v) for v in (a.get("allowed_values") or []) if isinstance(v, (str, int, float))],
        })
    return out


def _summaries(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        effect = s.get("effect", "")
        if effect not in EFFECT_CLASSES:
            continue
        out.append({"effect": effect, "count": int(s.get("count", 0))})
    return out


def _subcommands(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict) or not s.get("path"):
            continue
        effect = s.get("effect_class", "read_only")
        if effect not in EFFECT_CLASSES:
            effect = "read_only"
        out.append({
            "path":               str(s["path"]),
            "help_summary":       str(s.get("help_summary", "")),
            "help_long":          str(s.get("help_long", "")),
            "effect_class":       effect,
            "min_authority":      str(s.get("min_authority", "l0_observe")),
            "args":               _arg_specs(s.get("args")),
            "mirror":             str(s.get("mirror", "")),
            "requires_signature": bool(s.get("requires_signature", False)),
            "p95_target_ms":      int(s.get("p95_target_ms", 0)),
            "signature":          str(s.get("signature", "")),
        })
    return out


def snapshot() -> dict[str, Any]:
    """Full CLI-schema model projected from the selfdef mirror."""
    mirror = _read_mirror(CLI_MIRROR)
    return {
        "schema_version":    SCHEMA_VERSION,
        "mirror_status":     "online" if mirror else "offline",
        "mirror_source":     "selfdef-cli-mirror (MS007 typed mirror, read-only)",
        "cli_build_version": mirror.get("cli_build_version", ""),
        "doctrine":          mirror.get("doctrine", DOCTRINE),
        "captured_at":       mirror.get("captured_at"),
        "summaries":         _summaries(mirror.get("summaries")),
        "subcommands":       _subcommands(mirror.get("subcommands")),
        "signature":         mirror.get("signature"),  # MS003 sig
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef cli-mirror consumer (MS007)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "summaries", "mutating"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    snap = snapshot()
    if cmd == "summaries":
        _print(snap["summaries"])
    elif cmd == "mutating":
        # Filter to subcommands that require MS003 signature — these are
        # the operator-mutation verbs an MCP client should NEVER call
        # directly (R10212 + §17 boundary; clipboard-copy only).
        _print([s for s in snap["subcommands"] if s["requires_signature"]])
    else:
        _print(snap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
