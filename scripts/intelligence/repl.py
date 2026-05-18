#!/usr/bin/env python3
"""scripts/intelligence/repl.py — R366 (E2.M21 close).

Operator-named (hook drop 2026-05-17 verbatim): "Everything via
dashboard/UInterface or terminal tools OR AI. Python, System and
GPU and LLM and multiple level and REPL". Closes A-14 partial → ✓.

Multi-level REPL with 4 operator-named modes:
  python  — interactive Python interpreter with sovereign-os
            scripts/ on sys.path; pre-imports operator_overlay +
            inventory_consult helpers
  system  — shell passthrough with operator-pull command reference
            (lspci / nvidia-smi / zpool status / ip / journalctl)
  gpu     — GPU-focused: nvidia-smi loop primitives + gpu-card-advisor
            + gpu-wattage shortcuts
  llm     — LLM-focused: inference router query primitives +
            model-adapt + model-build shortcuts (read-only by default)

CLI:
  repl.py modes                          [--config P] [--json|--human]
  repl.py show <mode>                    [--config P] [--json|--human]
                                          render mode's command reference
                                          (operator-pull verb catalog)
  repl.py exec <mode> <cmd>              [--config P] [--json|--human]
                                          non-interactive one-shot:
                                          executes <cmd> in the mode's
                                          context + returns output;
                                          NEVER raises (caught + reported)
  repl.py shell <mode>                   [--config P]
                                          interactive shell (operator-
                                          runnable; not test-driven)

Operator-overlay (R283/SDD-030): /etc/sovereign-os/repl.toml
  - add custom modes
  - override mode env vars / pre-imports / command reference

Exit codes:
  0  rendered / executed cleanly
  1  unknown mode / command failed
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R366"
SDD_VECTOR = "E2.M21"


# ── Default mode catalog ─────────────────────────────────────────
DEFAULT_MODES: list[dict[str, Any]] = [
    {
        "mode": "python",
        "title": "Python REPL with sovereign-os helpers pre-loaded",
        "rationale": ("Operator-pull Python interpreter access with "
                       "scripts/lib/ on sys.path. Pre-imports the SDD-032 "
                       "helper-library trio (operator_overlay + apply_audit "
                       "+ safe_apply) + R348 inventory_consult."),
        "spawn_command": "python3 -i",
        "preamble_lines": [
            "import sys",
            f"sys.path.insert(0, '{REPO_ROOT / 'scripts' / 'lib'}')",
            "from operator_overlay import load_with_overlay",
            "import apply_audit",
            "from safe_apply import run_apply_safe",
            "from inventory_consult import find_advisor_caveats",
            "print('# sovereign-os Python REPL — R366')",
            "print('#  pre-loaded: load_with_overlay, apply_audit, '"
                  "'run_apply_safe, find_advisor_caveats')",
        ],
        "reference_commands": [
            "load_with_overlay('<verb>', {}, explicit_path=None)",
            "find_advisor_caveats('R315')  # 4-DIMM XMP warning",
            "apply_audit.query()",
        ],
        "env_vars": {
            "PYTHONPATH": str(REPO_ROOT / "scripts" / "lib"),
            "PYTHONSTARTUP": "",
        },
    },
    {
        "mode": "system",
        "title": "System-level shell with operator-pull pre-arms",
        "rationale": ("Operator-pull shell access with a curated "
                       "command reference for the operator's exact rig. "
                       "Pre-prints the most-used probes (PCIe / "
                       "ZFS / network / journal) so operator doesn't have "
                       "to recall syntax."),
        "spawn_command": os.environ.get("SHELL", "/bin/bash"),
        "preamble_lines": [
            "# sovereign-os System REPL — R366",
            "# Pre-arms (copy-paste ready):",
            "#   lspci -vvv -s <bdf>           # PCIe link state",
            "#   nvidia-smi -L                  # GPU enumeration",
            "#   zpool status -v                # ZFS pool health",
            "#   ip -j addr show               # network state",
            "#   journalctl -u tetragon -n 50   # auditor recent",
            "#   systemctl list-units --type=service --state=failed",
        ],
        "reference_commands": [
            "lspci -vvv -s <bdf>",
            "nvidia-smi -L",
            "zpool status -v",
            "ip -j addr show",
            "journalctl -u tetragon -n 50",
            "systemctl list-units --type=service --state=failed",
            "cat /proc/cpuinfo | grep -E 'avx512|model name' | head -5",
        ],
        "env_vars": {
            "PS1": ("\\[\\033[1;33m\\]sovereign-os/system\\[\\033[0m\\] "
                     "\\W $ "),
        },
    },
    {
        "mode": "gpu",
        "title": "GPU-focused REPL (nvidia-smi + sovereign verbs)",
        "rationale": ("Operator-pull interactive GPU probing. Combines "
                       "nvidia-smi commands with sovereign-osctl gpu-* "
                       "verbs (gpu-card-advisor / gpu-wattage / gpu-mode "
                       "/ gpu-remediate)."),
        "spawn_command": os.environ.get("SHELL", "/bin/bash"),
        "preamble_lines": [
            "# sovereign-os GPU REPL — R366",
            "# Pre-arms (copy-paste ready):",
            "#   nvidia-smi                        # full GPU state",
            "#   nvidia-smi dmon -s pucvmet         # streaming utilization",
            "#   nvidia-smi -q -d POWER             # power detail per-GPU",
            "#   nvidia-smi -q -d TEMPERATURE       # temp detail per-GPU",
            "#   sovereign-osctl gpu-card-advisor --json",
            "#   sovereign-osctl gpu-wattage --json",
            "#   sovereign-osctl gpu-mode --json",
            "#   sovereign-osctl xmp-oc-room status --json",
        ],
        "reference_commands": [
            "nvidia-smi",
            "nvidia-smi dmon -s pucvmet",
            "nvidia-smi -q -d POWER",
            "nvidia-smi -q -d TEMPERATURE",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl gpu-wattage --json",
            "sovereign-osctl gpu-mode --json",
            "sovereign-osctl xmp-oc-room status --json",
            "sovereign-osctl thermal-oc-budget status --json",
        ],
        "env_vars": {
            "PS1": ("\\[\\033[1;32m\\]sovereign-os/gpu\\[\\033[0m\\] "
                     "\\W $ "),
        },
    },
    {
        "mode": "llm",
        "title": "LLM-focused REPL (inference router + model lifecycle)",
        "rationale": ("Operator-pull interactive LLM access. Routes "
                       "queries through the R161 inference router "
                       "(pulse / logic-engine / oracle-core / router); "
                       "model-adapt + model-build + model-eval shortcuts."),
        "spawn_command": os.environ.get("SHELL", "/bin/bash"),
        "preamble_lines": [
            "# sovereign-os LLM REPL — R366",
            "# Pre-arms (copy-paste ready):",
            "#   sovereign-osctl inference status",
            "#   sovereign-osctl inference start <tier>",
            "#   sovereign-osctl inference query <tier> '<prompt>'",
            "#   sovereign-osctl models list",
            "#   sovereign-osctl models adapt suggest <base-model>",
            "#   sovereign-osctl models build plan <base> --recipe X",
            "#   sovereign-osctl models eval <model> <task>",
            "#   sovereign-osctl trinity profile show <id>",
        ],
        "reference_commands": [
            "sovereign-osctl inference status",
            "sovereign-osctl inference query pulse '<prompt>'",
            "sovereign-osctl inference query oracle '<prompt>'",
            "sovereign-osctl models list",
            "sovereign-osctl models adapt suggest <base-model>",
            "sovereign-osctl models build plan <base> --recipe X",
            "sovereign-osctl models eval <model> <task>",
            "sovereign-osctl trinity profile show ultra-sovereign-efficiency",
            "sovereign-osctl trinity profile show high-concurrency-burst",
            "sovereign-osctl trinity profile show deep-context-synthesis",
        ],
        "env_vars": {
            "PS1": ("\\[\\033[1;36m\\]sovereign-os/llm\\[\\033[0m\\] "
                     "\\W $ "),
        },
    },
]


# ── Loading ────────────────────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    modes = list(DEFAULT_MODES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "repl", {"modes": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("modes"):
            modes = list(loaded["modes"])
    return modes, meta


def resolve_mode(modes: list[dict], name: str) -> dict | None:
    for m in modes:
        if isinstance(m, dict) and m.get("mode") == name:
            return m
    return None


# ── Renderers ──────────────────────────────────────────────────────
def render_modes_human(modes: list[dict]) -> str:
    lines = [f"── R366 sovereign-os multi-level REPL ({len(modes)} modes) ──"]
    lines.append("")
    for m in modes:
        lines.append(f"  {m.get('mode'):<8}  {m.get('title')}")
        lines.append(f"            → sovereign-osctl repl show {m.get('mode')}")
        lines.append(f"            → sovereign-osctl repl shell {m.get('mode')}")
    return "\n".join(lines) + "\n"


def render_show_human(m: dict) -> str:
    lines = [f"── R366 REPL mode: {m.get('mode')} ──"]
    lines.append(f"  title:     {m.get('title')}")
    lines.append("")
    lines.append("  RATIONALE:")
    body = m.get("rationale") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append(f"  spawn command: {m.get('spawn_command')}")
    lines.append("")
    lines.append("  Preamble:")
    for line in m.get("preamble_lines") or []:
        lines.append(f"    {line}")
    lines.append("")
    lines.append("  Reference commands (operator-pull catalog):")
    for cmd in m.get("reference_commands") or []:
        lines.append(f"    $ {cmd}")
    return "\n".join(lines) + "\n"


# ── Exec ──────────────────────────────────────────────────────────
def exec_in_mode(mode: dict, cmd: str) -> dict[str, Any]:
    """Execute <cmd> in the mode's env. NEVER raises."""
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (mode.get("env_vars") or {}).items()})
    try:
        cp = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=30, env=env,
        )
        return {
            "mode": mode.get("mode"),
            "command": cmd,
            "rc": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "mode": mode.get("mode"),
            "command": cmd,
            "rc": 124,
            "stdout": "",
            "stderr": "(timeout > 30s — repl exec is one-shot only)",
        }
    except Exception as e:
        return {
            "mode": mode.get("mode"),
            "command": cmd,
            "rc": 1,
            "stdout": "",
            "stderr": f"(exception: {e!r})",
        }


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="repl.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("modes")
    pm.add_argument("--config", type=Path)
    pmg = pm.add_mutually_exclusive_group()
    pmg.add_argument("--json", dest="fmt", action="store_const", const="json")
    pmg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pm.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("mode_name")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pe = sub.add_parser("exec")
    pe.add_argument("mode_name")
    pe.add_argument("repl_cmd")
    pe.add_argument("--config", type=Path)
    peg = pe.add_mutually_exclusive_group()
    peg.add_argument("--json", dest="fmt", action="store_const", const="json")
    peg.add_argument("--human", dest="fmt", action="store_const", const="human")
    pe.set_defaults(fmt="json")

    psh = sub.add_parser("shell")
    psh.add_argument("mode_name")
    psh.add_argument("--config", type=Path)

    args = p.parse_args(argv)
    modes, meta = load_state(getattr(args, "config", None))

    if args.cmd == "modes":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mode_count": len(modes),
                "modes": [{"mode": m.get("mode"),
                            "title": m.get("title"),
                            "rationale": m.get("rationale")} for m in modes],
                "overlay": meta,
            }, indent=2))
        else:
            print(render_modes_human(modes), end="")
        return 0

    if args.cmd == "show":
        m = resolve_mode(modes, args.mode_name)
        if m is None:
            print(json.dumps({
                "error": f"unknown mode: {args.mode_name}",
                "known_modes": [x.get("mode") for x in modes if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "mode_detail": m,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(m), end="")
        return 0

    if args.cmd == "exec":
        m = resolve_mode(modes, args.mode_name)
        if m is None:
            print(json.dumps({
                "error": f"unknown mode: {args.mode_name}",
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        result = exec_in_mode(m, args.repl_cmd)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                **result,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R366 repl exec ({result.get('mode')}) rc={result['rc']} ──")
            if result.get("stdout"):
                print(result["stdout"], end="")
            if result.get("stderr"):
                print(result["stderr"], end="", file=sys.stderr)
        return result["rc"] if result["rc"] in (0, 1, 2, 124) else 1

    if args.cmd == "shell":
        m = resolve_mode(modes, args.mode_name)
        if m is None:
            print(f"error: unknown mode: {args.mode_name}", file=sys.stderr)
            return 1
        # Operator-runnable interactive shell — write the preamble
        # to a temp file the shell sources at startup.
        import tempfile
        env = os.environ.copy()
        env.update({k: str(v) for k, v in (m.get("env_vars") or {}).items()})
        spawn = m.get("spawn_command") or "/bin/bash"
        if "python" in spawn.lower():
            # Python: pass -c with the preamble + drop to interactive
            preamble = "\n".join(m.get("preamble_lines") or [])
            code_file = tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False)
            code_file.write(preamble)
            code_file.close()
            os.execvpe("python3", ["python3", "-i", code_file.name], env)
        else:
            # Shell: print preamble to stderr, then exec interactively
            sys.stderr.write("\n".join(m.get("preamble_lines") or []) + "\n")
            sys.stderr.flush()
            os.execvpe(spawn, [spawn], env)
        return 0  # unreachable (execvpe replaces process)

    return 2


if __name__ == "__main__":
    sys.exit(main())
