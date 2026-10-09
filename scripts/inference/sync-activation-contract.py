#!/usr/bin/env python3
"""sync-activation-contract.py — the ONE implementation of the runtime
activation-contract sync (was inline bash in `sovereign-osctl trinity profile
switch`; promoted to a shared script 2026-10-09 after the image-companion
activator was found restarting chat tiers WITHOUT syncing, leaving the /opt
payload unable to resolve the selected profile — the launcher then silently
served its start-script default (gpt-oss-120b) while D-21 declared
Qwen3-Coder-Next. The operator re-applied switches three times because every
"successful" activation activated the wrong weights.)

The control rail runs from the developer checkout, whereas systemd inference
units execute the packaged /opt payload. A profile marker alone is therefore
insufficient when /opt predates the checkout: the service would restart and
silently retain its previous model. This syncs exactly the runtime activation
contract — the profile resolver lib, the two tier launchers, and the selected
profile YAML — and nothing else. This is intentionally NOT a general
source-tree deployment (that remains converge's job).

No-op when the payload root is absent (dev-only hosts) or IS the source tree
(linked installs). The route reconciler is installed by IaC, never by profile
activation, and is deliberately left alone.

Usage: sync-activation-contract.py <family> <profile-yaml> [--repo R] [--payload P]
family: runtime | orchestration | user (user drafts carry the orchestration
shape at runtime, so they land in the orchestration family for the resolver).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SYNCED_SCRIPTS = [
    "scripts/build/lib/runtime-profile.sh",
    "scripts/inference/start-logic-engine.sh",
    "scripts/inference/start-oracle-core.sh",
]
# Payload family per source family (user drafts resolve as orchestration).
FAMILY_DIR = {
    "runtime": "profiles/runtime",
    "orchestration": "profiles/orchestration",
    "user": "profiles/orchestration",
}


def sync(repo_root: Path, payload_root: Path, family: str,
         profile_file: Path) -> tuple[int, list[str], list[str]]:
    """Return (exit_code, info_lines, error_lines). Never raises."""
    if not payload_root.is_dir():
        return 0, [f"payload root absent ({payload_root}); nothing to sync"], []
    try:
        if payload_root.resolve() == repo_root.resolve():
            return 0, ["payload is the source tree (linked install); nothing to sync"], []
    except OSError:
        pass
    fam_rel = FAMILY_DIR.get(family)
    if not fam_rel:
        return 1, [], [f"unknown profile family: {family}"]
    if not profile_file.is_file():
        return 1, [], [f"profile file missing: {profile_file}"]
    infos: list[str] = []
    for rel in SYNCED_SCRIPTS:
        source = repo_root / rel
        if not source.is_file():
            return 1, infos, [f"runtime activation source missing: {source}"]
        destination = payload_root / rel
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(0o755)
        except OSError as exc:
            return 1, infos, [f"could not synchronize runtime activation file: {destination}: {exc}"]
    destination = payload_root / fam_rel / profile_file.name
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(profile_file, destination)
        destination.chmod(0o644)
    except OSError as exc:
        return 1, infos, [f"could not synchronize selected profile into runtime payload: {destination}: {exc}"]
    infos.append(f"synchronized runtime activation contract into {payload_root} "
                 f"({len(SYNCED_SCRIPTS)} scripts + {profile_file.name})")
    return 0, infos, []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("family")
    ap.add_argument("profile_yaml")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--payload", default="/opt/sovereign-os")
    args = ap.parse_args(argv)
    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parents[2]
    code, infos, errors = sync(repo, Path(args.payload), args.family, Path(args.profile_yaml))
    for line in infos:
        print(line)
    for line in errors:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
