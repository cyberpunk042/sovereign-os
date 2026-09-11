#!/usr/bin/env python3
"""Resolve a sovereign-os project write target without shadow-workspace drift.

OpenClaw keeps an agent scratch tree at ``~/.openclaw/workspace``.  A matching
relative path in that tree is not the checked-out sovereign-os repository.  This
tool establishes a small, serializable identity record that integrations can
require before they read or write project files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class WorkspaceError(ValueError):
    """A requested project or write path fails the authority contract."""


def _absolute(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _git_toplevel(path: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise WorkspaceError(f"git is unavailable: {exc}") from exc
    if result.returncode:
        raise WorkspaceError(f"project root is not inside a git checkout: {path}")
    return _absolute(result.stdout.strip())


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _shadow_root() -> Path:
    return _absolute(os.environ.get("OPENCLAW_WORKSPACE", "~/.openclaw/workspace"))


def workspace_identity(project_root: str | Path) -> dict[str, str]:
    """Return the canonical identity for a selected sovereign-os checkout."""
    requested = _absolute(project_root)
    git_root = _git_toplevel(requested)
    if requested != git_root:
        # A subdirectory is a valid selection, but writes must still use the
        # checkout root so sibling profile/config changes cannot escape policy.
        requested = git_root
    if requested == _shadow_root():
        raise WorkspaceError(
            "shadow-workspace: ~/.openclaw/workspace is agent scratch, not an authoritative project checkout"
        )
    digest = hashlib.sha256(str(git_root).encode("utf-8")).hexdigest()
    return {
        "repo_root": str(git_root),
        "git_toplevel": str(git_root),
        "origin": "local-checkout",
        "write_root": str(git_root),
        "identity_digest": digest,
    }


def resolve_write(project_root: str | Path, requested_path: str | Path) -> dict[str, Any]:
    """Resolve a write candidate and return an auditable, non-mutating preflight."""
    identity = workspace_identity(project_root)
    root = Path(identity["write_root"])
    candidate = _absolute(requested_path)
    if not _is_below(candidate, root):
        kind = "shadow-workspace" if _is_below(candidate, _shadow_root()) else "outside-write-root"
        raise WorkspaceError(
            f"{kind}: refusing {candidate}; sovereign-os writes are confined to {root}"
        )
    try:
        stat = candidate.stat()
    except FileNotFoundError:
        before = {"exists": False, "sha256": None, "size_bytes": 0}
    else:
        if not candidate.is_file():
            raise WorkspaceError(f"write target is not a regular file: {candidate}")
        before = {
            "exists": True,
            "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            "size_bytes": stat.st_size,
        }
    return {"workspace_identity": identity, "resolved_path": str(candidate), "prewrite": before}


def _emit(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True))
        return
    for key, item in value.items():
        print(f"{key}: {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    identity = sub.add_parser("identity", help="emit canonical project identity")
    identity.add_argument("--project-root", required=True)
    identity.add_argument("--json", action="store_true")
    resolve = sub.add_parser("resolve-write", help="preflight a project write target")
    resolve.add_argument("--project-root", required=True)
    resolve.add_argument("--path", required=True)
    resolve.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "identity":
            _emit(workspace_identity(args.project_root), args.json)
        else:
            _emit(resolve_write(args.project_root, args.path), args.json)
    except WorkspaceError as exc:
        print(f"workspace identity error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
