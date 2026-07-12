#!/usr/bin/env python3
"""
scripts/operator/lib/permission_classifier.py — the Auto-mode safety classifier
for the Plan Mode + User Approval framework
(docs/standing-directives/2026-07-11-plan-mode-user-approval.md).

Given a proposed action (a shell command, or a cockpit control's change_cli), it
classifies it as destructive / routine / unknown, and then decides
allow / block / confirm under the active permission mode:

  - manual  — pause for explicit approval on anything that mutates (the sovereign
              default). Reads proceed; everything else needs confirm; destructive
              needs confirm + is flagged DANGER.
  - auto    — a safety classifier auto-BLOCKS destructive ops, lets routine
              (read-only) ops proceed, and asks to confirm the unknown middle.
  - bypass  — skip all gates (the --dangerously-skip-permissions analogue).

IMPORTANT — this is a BEST-EFFORT UX HEURISTIC, not a security boundary. It
reduces footguns for a cooperative caller; it does NOT contain an adversary.
Its pattern/flag matching is deliberately conservative and fails SAFE (an
unrecognized or obfuscated mutation lands in `unknown` → confirm, never a silent
allow), but quoting / `$IFS` / variable / base64 obfuscation can still evade the
`destructive` classification. The ACTUAL boundary is the allowlisted execute
daemon (control-exec-api: allowlisted control-id + dry-run default + audit) and
the fs sandbox around the execution paths — not this regex. Treat a `block`
verdict as "spared the operator a likely mistake", never as "an attacker was
stopped".

Sovereignty-clean: stdlib only (re + os). Patterns default in-code and may be
extended from config/permission-modes.yaml (no PyYAML dependency — a tiny
list-reader). This never executes anything; it only judges.

Env:
  SOVEREIGN_OS_PERMISSION_MODE   manual | auto | bypass   (default manual)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

MODES = ("manual", "auto", "bypass")

# ── destructive: irreversible data / device / OS damage. Auto BLOCKS these. ──
# Deliberately conservative (better to over-flag → confirm than to auto-run a
# wipe). Ordered most-specific first; the first match wins with its reason.
_DESTRUCTIVE = [
    # NOTE: `rm` is handled by _rm_recursive_or_force() (flag normalization),
    # NOT a regex — a single combined-token pattern missed split (`rm -r -f`)
    # and uppercase (`-R`) flags (F-2026-092).
    (r"\bdd\b.*\bof=/dev/(sd|nvme|vd|mmcblk|disk)", "dd writing to a raw block device"),
    (r"\b(mkfs|wipefs|blkdiscard|sgdisk|fdisk|parted|cfdisk)\b", "filesystem/partition table operation"),
    (r"\bnvme\s+(format|sanitize)\b", "nvme format/sanitize (device wipe)"),
    (r"\bcryptsetup\s+luks(Format|Erase)\b", "LUKS format/erase (destroys the volume)"),
    (r">\s*/dev/(sd|nvme|vd|mmcblk)", "redirect into a raw block device"),
    (r"\bzpool\s+(destroy|labelclear)\b", "ZFS pool destroy"),
    (r"\bzfs\s+destroy\b", "ZFS dataset/snapshot destroy"),
    (r"\bgit\s+push\s+(-\w+\s+)*(--force\b|-f\b|--force-with-lease\b)", "force-push (rewrites remote history)"),
    (r"\bgit\s+(reset\s+--hard|clean\s+-\w*[dfx])", "git hard reset / clean (discards work)"),
    (r"\bchmod\s+(-R\s+)*0*777\s+/", "world-writable on a root path"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b|\binit\s+0\b", "host power-state change"),
    (r"\btruncate\s+-s\s*0\b", "truncate a file to zero"),
    (r"\b(curl|wget)\b.*\|\s*(sudo\s+)?(sh|bash|zsh)\b", "pipe-to-shell (remote code execution)"),
    (r"\bmv\s+/\S+\s+/dev/null\b", "move into /dev/null (data loss)"),
]

# ── routine: read-only / inspection. Auto ALLOWS these without a prompt. ──
_ROUTINE_HEADS = {
    "ls", "cat", "head", "tail", "less", "more", "grep", "rg", "egrep", "fgrep",
    "pwd", "whoami", "id", "date", "uptime", "echo", "printf", "which", "type",
    "stat", "file", "wc", "sort", "uniq", "cut", "awk", "sed", "diff", "cmp",
    "df", "du", "free", "ps", "top", "htop", "lsblk", "lscpu", "lspci", "lsusb",
    "env", "printenv", "hostname", "uname", "nproc", "readlink", "realpath", "basename", "dirname",
}
# read-only subverb heads (git/systemctl/journalctl/sovereign-osctl inspection)
_ROUTINE_SUBVERBS = {
    "git": {"status", "log", "diff", "show", "branch", "remote", "rev-parse", "describe", "blame", "config"},
    "systemctl": {"status", "is-active", "is-enabled", "list-units", "list-timers", "show", "cat"},
    "journalctl": None,      # journalctl is read-only
    "docker": {"ps", "images", "logs", "inspect"},
    "podman": {"ps", "images", "logs", "inspect"},
}
# read-only sovereign-osctl subverbs (inspection verbs never mutate)
_ROUTINE_OSCTL = {"status", "list", "show", "info", "metrics", "gateway", "power-status",
                  "audit", "surface-map", "help", "version", "snapshot"}


def _config_extra_destructive() -> list[tuple[str, str]]:
    """Optional operator-supplied destructive patterns from
    config/permission-modes.yaml under `destructive_extra: ["<regex> | <reason>"]`.
    Tiny list-reader — no PyYAML dependency; absent/malformed → []."""
    repo = Path(__file__).resolve().parents[3]
    path = repo / "config" / "permission-modes.yaml"
    out: list[tuple[str, str]] = []
    try:
        in_block = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if re.match(r"^\s*destructive_extra\s*:", line):
                in_block = True
                continue
            if in_block:
                m = re.match(r"^\s*-\s*['\"]?(.+?)['\"]?\s*$", line)
                if m and "|" in m.group(1):
                    rx, reason = m.group(1).split("|", 1)
                    out.append((rx.strip(), reason.strip()))
                elif not line.startswith((" ", "\t", "-")) and line:
                    in_block = False
    except OSError:
        pass
    return out


def _rm_recursive_or_force(cmd: str) -> str | None:
    """Flag-normalized `rm` danger check. Returns a reason when an `rm` in `cmd`
    carries recursive (`-r` / `-R` / `--recursive`) or force (`-f` / `--force`)
    semantics in ANY flag arrangement — combined (`-rf`), split (`-r -f`),
    reordered (`-fr`), uppercase (`-R`), or long (`--recursive --force`) — else
    None.

    Replaces the single combined-token regex that only matched flags written
    together, so `rm -r -f /x` and `rm -R -f /x` escaped to `confirm`
    (F-2026-092). Best-effort UX, NOT a security boundary: quoting / `$IFS` /
    variable obfuscation still evade it and fall through to `unknown` → confirm
    (never a silent allow); the real boundary is the allowlisted execute daemon
    + fs sandbox, not this heuristic.
    """
    toks = cmd.split()
    for i, tok in enumerate(toks):
        if tok.rsplit("/", 1)[-1] != "rm":
            continue
        recursive = force = False
        for opt in toks[i + 1:]:
            if opt == "--":
                break  # end of options; only operands (paths) follow
            if opt == "--recursive":
                recursive = True
            elif opt == "--force":
                force = True
            elif re.fullmatch(r"-[A-Za-z]+", opt):  # a short-flag cluster
                if "r" in opt or "R" in opt:
                    recursive = True
                if "f" in opt:
                    force = True
        if recursive or force:
            what = "/".join(
                w for w, on in (("recursive", recursive), ("force", force)) if on
            )
            return f"{what} file delete (rm)"
    return None


def default_mode() -> str:
    m = os.environ.get("SOVEREIGN_OS_PERMISSION_MODE", "manual").strip().lower()
    return m if m in MODES else "manual"


def _first_word(cmd: str) -> str:
    for tok in cmd.strip().split():
        if "=" in tok and not tok.startswith("-"):
            continue  # skip leading VAR=val env assignments
        if tok in ("sudo", "command", "env", "nohup", "time", "exec"):
            continue  # skip wrappers
        return tok.rsplit("/", 1)[-1]
    return ""


def classify(command: str) -> dict:
    """Classify a command → {verdict: destructive|routine|unknown, reason, matched}."""
    cmd = (command or "").strip()
    if not cmd:
        return {"verdict": "routine", "reason": "empty", "matched": None}
    rm_reason = _rm_recursive_or_force(cmd)
    if rm_reason:
        return {"verdict": "destructive", "reason": rm_reason, "matched": "rm-flag-normalized"}
    for rx, reason in _DESTRUCTIVE + _config_extra_destructive():
        if re.search(rx, cmd):
            return {"verdict": "destructive", "reason": reason, "matched": rx}

    head = _first_word(cmd)
    words = cmd.split()
    # env-only wrappers stripped in _first_word; find the subverb after the head
    idx = next((i for i, w in enumerate(words) if w.rsplit("/", 1)[-1] == head), 0)
    sub = words[idx + 1].rsplit("/", 1)[-1] if idx + 1 < len(words) else ""

    if head in _ROUTINE_HEADS:
        # `find … -delete`/`-exec rm` is NOT routine — caught above only if rm; guard find
        if head == "find" and re.search(r"-delete\b|-exec\b", cmd):
            return {"verdict": "unknown", "reason": "find with -delete/-exec", "matched": None}
        return {"verdict": "routine", "reason": f"read-only ({head})", "matched": None}
    if head in _ROUTINE_SUBVERBS:
        allowed = _ROUTINE_SUBVERBS[head]
        if allowed is None or sub in allowed:
            return {"verdict": "routine", "reason": f"read-only ({head} {sub})".strip(), "matched": None}
    if head in ("sovereign-osctl", "osctl") and (sub in _ROUTINE_OSCTL or "--dry-run" in words or "--json" in words):
        return {"verdict": "routine", "reason": f"inspection ({head} {sub})".strip(), "matched": None}

    return {"verdict": "unknown", "reason": f"unrecognized action ({head or '?'})", "matched": None}


def decide(command: str, mode: str | None = None) -> dict:
    """Decide allow / block / confirm for `command` under `mode`."""
    mode = (mode or default_mode()).strip().lower()
    if mode not in MODES:
        mode = "manual"
    c = classify(command)
    verdict = c["verdict"]

    if mode == "bypass":
        action = "allow"
    elif mode == "auto":
        action = {"destructive": "block", "routine": "allow", "unknown": "confirm"}[verdict]
    else:  # manual
        action = "allow" if verdict == "routine" else "confirm"

    danger = verdict == "destructive"
    return {
        "action": action, "mode": mode, "verdict": verdict, "danger": danger,
        "reason": c["reason"],
        "message": {
            "allow": "routine — proceeds without a prompt",
            "block": f"BLOCKED by Auto mode — {c['reason']}. Switch to manual/bypass or run it yourself.",
            "confirm": ("requires approval" + (f" — DANGER: {c['reason']}" if danger else f" ({c['reason']})")),
        }[action],
    }


def main() -> int:
    import json
    import sys
    argv = sys.argv[1:]
    mode = None
    if "--mode" in argv:
        i = argv.index("--mode")
        mode = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    cmd = " ".join(argv)
    if not cmd or cmd in ("-h", "--help"):
        print(__doc__)
        return 0
    print(json.dumps(decide(cmd, mode), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
