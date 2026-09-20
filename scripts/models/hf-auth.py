#!/usr/bin/env python3
"""Run HF commands with one canonical token, never a token command argument."""
import os
from pathlib import Path
import shlex
import stat
import sys

TOKEN_NAMES = ("HF_TOKEN", "SOVEREIGN_OS_HF_TOKEN", "HUGGINGFACE_HUB_TOKEN")


def token_environment(environ):
    env = dict(environ)
    token = next((env[k] for k in TOKEN_NAMES if env.get(k)), None)
    if not token:
        path = Path(env.get("SOVEREIGN_OS_HF_ENV_FILE", "/etc/sovereign-os/model.env"))
        try:
            info = path.stat()
        except FileNotFoundError:
            info = None
        if info:
            if not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o077:
                raise ValueError("HF credential file must be a private regular file (0600), owned by root or the current user")
            values = {}
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:]
                name, sep, value = line.partition("=")
                if sep and name.strip() in TOKEN_NAMES:
                    # Parse quotes/comments without ever executing shell code.
                    try:
                        words = shlex.split(value, comments=True)
                    except ValueError:
                        raise ValueError("invalid HF credential file syntax") from None
                    if len(words) > 1:
                        raise ValueError("HF credential must be one value")
                    values[name.strip()] = words[0] if words else ""
            token = next((values[k] for k in TOKEN_NAMES if values.get(k)), None)
    if token:
        env["HF_TOKEN"] = token
    return env


if __name__ == "__main__":
    command = sys.argv[1:]
    if not command:
        sys.exit("usage: hf-auth.py <command> [arguments]")
    try:
        env = token_environment(os.environ)
    except (OSError, ValueError):
        sys.exit("HF authentication setup failed: check /etc/sovereign-os/model.env ownership, permissions (0600), and token syntax; no credential was printed.")
    os.execvpe(command[0], command, env)
