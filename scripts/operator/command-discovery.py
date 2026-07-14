#!/usr/bin/env python3
"""Registry-backed discovery, contextual man help, and shell completions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import NoReturn


TOPIC_PREFIX = "sovereign-osctl-"
BUILTIN_TOPICS = {"help": None, "version": None}


def _registry_candidates(explicit: str | None) -> list[Path]:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("SOVEREIGN_OS_COMMAND_REGISTRY"):
        candidates.append(Path(os.environ["SOVEREIGN_OS_COMMAND_REGISTRY"]))
    candidates.extend(
        (
            here.parents[2] / "docs/man/sovereign-osctl-command-topics.json",
            here.parent.parent / "share/sovereign-osctl-command-topics.json",
            Path("/usr/local/lib/sovereign-os/share/sovereign-osctl-command-topics.json"),
            Path("/usr/lib/sovereign-os/share/sovereign-osctl-command-topics.json"),
            Path("/opt/sovereign-os/share/sovereign-osctl-command-topics.json"),
        )
    )
    return candidates


def load_registry(explicit: str | None) -> tuple[Path, dict[str, list[str]]]:
    tried: list[Path] = []
    for path in _registry_candidates(explicit):
        path = path.expanduser()
        if path in tried:
            continue
        tried.append(path)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"error: invalid command registry {path}: {exc}") from exc
        pages = data.get("pages")
        if data.get("schema_version") != 1 or not isinstance(pages, dict):
            raise SystemExit(f"error: unsupported command registry schema in {path}")
        seen: set[str] = set()
        for topic, commands in pages.items():
            if not isinstance(topic, str) or not isinstance(commands, list) or not commands:
                raise SystemExit(f"error: invalid topic {topic!r} in {path}")
            if not all(isinstance(command, str) and command for command in commands):
                raise SystemExit(f"error: invalid command in topic {topic!r} in {path}")
            duplicates = seen.intersection(commands)
            if duplicates:
                raise SystemExit(f"error: commands owned more than once: {', '.join(sorted(duplicates))}")
            seen.update(commands)
        return path, pages
    attempted = "\n  ".join(str(path) for path in tried)
    raise SystemExit(f"error: sovereign-osctl command registry not found; tried:\n  {attempted}")


def command_index(pages: dict[str, list[str]]) -> dict[str, str]:
    return {command: topic for topic, commands in pages.items() for command in commands}


def all_commands(pages: dict[str, list[str]]) -> list[str]:
    return list(BUILTIN_TOPICS) + [
        command for commands in pages.values() for command in commands
    ]


def cmd_commands(args: argparse.Namespace, pages: dict[str, list[str]]) -> int:
    if args.json:
        payload = {
            "schema_version": 1,
            "command_count": len(all_commands(pages)),
            "builtins": list(BUILTIN_TOPICS),
            "topics": pages,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.format == "words":
        print(" ".join(all_commands(pages)))
    else:
        total = len(all_commands(pages))
        print(f"sovereign-osctl commands — {total} commands across {len(pages)} topics")
        print("\nbuiltins (2):\n  help  version")
        for topic, commands in pages.items():
            print(f"\n{topic} ({len(commands)}):")
            print("  " + "  ".join(commands))
        print("\nUse `sovereign-osctl help <command-or-topic>` for the owning manual page.")
    return 0


def _fail_unknown(target: str, pages: dict[str, list[str]]) -> NoReturn:
    known = sorted(set(pages) | set(command_index(pages)) | set(BUILTIN_TOPICS))
    import difflib

    suggestions = difflib.get_close_matches(target, known, n=3, cutoff=0.5)
    suffix = f"; did you mean: {', '.join(suggestions)}" if suggestions else ""
    print(f"error: unknown command or topic {target!r}{suffix}", file=sys.stderr)
    raise SystemExit(2)


def _local_manpage(topic: str | None) -> Path | None:
    here = Path(__file__).resolve()
    name = "sovereign-osctl.1" if topic is None else f"{TOPIC_PREFIX}{topic}.1"
    candidate = here.parents[2] / "docs/man" / name
    return candidate if candidate.is_file() else None


def cmd_help(args: argparse.Namespace, pages: dict[str, list[str]]) -> int:
    target = args.target
    index = command_index(pages)
    if target in BUILTIN_TOPICS:
        topic = None
    elif target in pages:
        topic = target
    elif target in index:
        topic = index[target]
    else:
        _fail_unknown(target, pages)

    page = "sovereign-osctl" if topic is None else f"{TOPIC_PREFIX}{topic}"
    local_page = _local_manpage(topic)
    man = shutil.which("man")
    if man and not args.print_target:
        argv = [man, "-l", str(local_page)] if local_page else [man, page]
        completed = subprocess.run(argv, check=False)
        if completed.returncode == 0:
            return 0
        print(f"warning: man could not open {page}(1)", file=sys.stderr)
    print(page)
    if target in BUILTIN_TOPICS:
        print(f"{target} is documented in sovereign-osctl(1).")
    elif target in index:
        print(f"{target} is documented in {page}(1).")
    elif not args.print_target:
        print(f"Topic contains {len(pages[topic])} commands.")
    return 0


def cmd_completion(args: argparse.Namespace, pages: dict[str, list[str]]) -> int:
    words = " ".join(all_commands(pages))
    if args.shell == "bash":
        print("""# bash completion for sovereign-osctl (registry-backed)
_sovereign_osctl_complete() {
  local cur
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  if (( COMP_CWORD == 1 )); then
    COMPREPLY=( $(compgen -W "$(sovereign-osctl commands --format words 2>/dev/null)" -- "$cur") )
  fi
}
complete -F _sovereign_osctl_complete sovereign-osctl sosctl""")
    elif args.shell == "zsh":
        print(f"""#compdef sovereign-osctl sosctl
_sovereign_osctl() {{
  local -a commands
  commands=({words})
  _describe 'sovereign-osctl command' commands
}}
compdef _sovereign_osctl sovereign-osctl sosctl""")
    else:
        print("# fish completion for sovereign-osctl (registry-backed)")
        print("complete -c sovereign-osctl -f -n '__fish_use_subcommand' -a '%s'" % words)
        print("complete -c sosctl -f -n '__fish_use_subcommand' -a '%s'" % words)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--registry", help="explicit command-topic registry path")
    sub = root.add_subparsers(dest="action", required=True)

    commands = sub.add_parser("commands", help="list every top-level command")
    commands.add_argument("--json", action="store_true")
    commands.add_argument("--format", choices=("grouped", "words"), default="grouped")

    help_parser = sub.add_parser("help", help="resolve a command/topic to its man page")
    help_parser.add_argument("target")
    help_parser.add_argument("--print-target", action="store_true", help=argparse.SUPPRESS)

    completion = sub.add_parser("completion", help="emit shell completion")
    completion.add_argument("shell", choices=("bash", "zsh", "fish"))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    _, pages = load_registry(args.registry)
    return {
        "commands": cmd_commands,
        "help": cmd_help,
        "completion": cmd_completion,
    }[args.action](args, pages)


if __name__ == "__main__":
    raise SystemExit(main())
