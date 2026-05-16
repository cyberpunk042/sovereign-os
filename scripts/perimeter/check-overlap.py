#!/usr/bin/env python3
"""Master spec § 10 + selfdef SDD-015 Q15-C: perimeter check-overlap.

Mirror of selfdef's `selfdefctl perimeter check-overlap` — same logic,
sovereign-os side, so operators can invoke from either repo.

Detects:
  1. Two policies sharing the same metadata.name (Tetragon ambiguity)
  2. A NON-sovereign-os policy that asserts on a syscall
     sovereign-os fences host-wide (sys_execve / sys_execveat /
     tcp_connect / tcp_sendmsg) without container scope
     (matchNamespaces with operator=In and "container" in values)

Exit codes:
  0  no overlap detected (or empty policies dir)
  1  at least one finding (operator action needed)
  2  usage error

CLI:
  check-overlap.py                       # scan /etc/tetragon/tracing-policies
  check-overlap.py --policies-dir <p>    # scan custom dir
  check-overlap.py --json                # machine-readable
  check-overlap.py --warn-only           # downgrade exit to 0

The script is dependency-free except for PyYAML (stdlib otherwise).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    sys.stderr.write(
        "ERROR python3-yaml not installed: apt install python3-yaml\n"
    )
    sys.exit(2)


# Syscalls sovereign-kernel-fence (or any sovereign-os-authored policy)
# asserts on host-wide. Non-sovereign policies touching these without
# container scope are flagged.
HOST_FENCED_SYSCALLS = {
    "sys_execve",
    "sys_execveat",
    "tcp_connect",
    "tcp_sendmsg",
}

# Filename-prefix author classification — matches selfdef's
# perimeter.rs classify_author().
SOVEREIGN_PREFIX = "sovereign-"
SELFDEF_PREFIX = "agent-guard-"


def classify_author(filename: str) -> str:
    if filename.startswith(SOVEREIGN_PREFIX):
        return "sovereign-os"
    if filename.startswith(SELFDEF_PREFIX):
        return "selfdef"
    return "third-party"


def kprobe_scope(kprobe: dict) -> str:
    """Returns 'container' iff at least one selector has matchNamespaces
    with operator=In and 'container' in values; otherwise 'host'."""
    for sel in kprobe.get("selectors", []) or []:
        for mn in sel.get("matchNamespaces", []) or []:
            if mn.get("operator") == "In" and "container" in (mn.get("values") or []):
                return "container"
    return "host"


def parse_policy(path: Path) -> dict | None:
    """Parse one YAML; returns a summary dict or None on bad YAML."""
    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError) as e:
        sys.stderr.write(f"WARN  {path}: {e}; skipping\n")
        return None
    if not isinstance(doc, dict):
        sys.stderr.write(f"WARN  {path}: not a YAML map; skipping\n")
        return None
    return {
        "filename": path.name,
        "metadata_name": (doc.get("metadata") or {}).get("name", ""),
        "author": classify_author(path.name),
        "kprobes": [
            {"call": kp.get("call", ""), "scope": kprobe_scope(kp)}
            for kp in (doc.get("spec") or {}).get("kprobes", []) or []
        ],
    }


def read_policies(policies_dir: Path) -> list[dict]:
    if not policies_dir.exists():
        return []
    out: list[dict] = []
    for entry in sorted(policies_dir.iterdir()):
        if entry.suffix not in (".yaml", ".yml"):
            continue
        if not entry.is_file():
            continue
        summary = parse_policy(entry)
        if summary:
            out.append(summary)
    return out


def check_overlap(policies: list[dict]) -> list[dict]:
    """Returns the list of findings (each a dict with 'kind' + detail).

    Same shape as selfdef perimeter.rs `OverlapFinding` enum, but as
    JSON-serializable dicts for the --json mode.
    """
    findings: list[dict] = []

    # 1. Duplicate metadata.name
    by_name: dict[str, list[str]] = {}
    for p in policies:
        n = p["metadata_name"]
        if not n:
            continue
        by_name.setdefault(n, []).append(p["filename"])
    for name, files in sorted(by_name.items()):
        if len(files) > 1:
            findings.append({
                "kind": "duplicate_metadata_name",
                "name": name,
                "files": sorted(files),
            })

    # 2. NON-sovereign-os policy host-scoped on fenced syscall
    for p in policies:
        if p["author"] == "sovereign-os":
            continue  # sovereign-os ITSELF authors the host-scoped fences
        for kp in p["kprobes"]:
            if kp["scope"] == "host" and kp["call"] in HOST_FENCED_SYSCALLS:
                findings.append({
                    "kind": "non_sovereign_host_scoped_on_fenced_syscall",
                    "filename": p["filename"],
                    "metadata_name": p["metadata_name"],
                    "author": p["author"],
                    "syscall": kp["call"],
                })
    return findings


def render_finding_human(f: dict) -> str:
    if f["kind"] == "duplicate_metadata_name":
        return (
            f"duplicate metadata.name {f['name']!r}: appears in "
            f"{', '.join(f['files'])}"
        )
    if f["kind"] == "non_sovereign_host_scoped_on_fenced_syscall":
        return (
            f"{f['filename']} (author={f['author']}, metadata.name="
            f"{f['metadata_name']}) asserts on {f['syscall']} without "
            f"matchNamespaces=container scope — would conflict with "
            f"sovereign-os's host-scoped allowlist. "
            f"Fix: add 'matchNamespaces: {{ operator: In, values: "
            f"[container] }}' to the selector"
        )
    return json.dumps(f)


def render_human(policies: list[dict], findings: list[dict]) -> tuple[str, int]:
    out = ["# sovereign-osctl perimeter check-overlap (selfdef SDD-015 mirror)", ""]
    out.append("## Loaded policies")
    if not policies:
        out.append("  (no policies present)")
    else:
        for p in policies:
            out.append(
                f"  {p['filename']:<48} author={p['author']:<13} "
                f"metadata.name={p['metadata_name']}"
            )
            for kp in p["kprobes"]:
                out.append(f"      kprobe call={kp['call']} scope={kp['scope']}")
    out.append("")
    out.append("## Findings")
    if not findings:
        out.append("  PASS — no host-wide kprobe overlap detected")
        out.append("  PASS — all policies have distinct metadata.name")
        return ("\n".join(out) + "\n", 0)
    for f in findings:
        out.append(f"  FAIL — {render_finding_human(f)}")
    out.append("")
    out.append(
        "Exit 1. Fix the violations above, or pass --warn-only to "
        "downgrade exit to 0."
    )
    return ("\n".join(out) + "\n", 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Perimeter coexistence check (mirror of selfdef SDD-015)"
    )
    parser.add_argument(
        "--policies-dir",
        default="/etc/tetragon/tracing-policies",
        help="Directory with Tetragon TracingPolicy YAMLs",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="downgrade FAIL exit to 0 (find but don't block)",
    )
    args = parser.parse_args()

    policies_dir = Path(args.policies_dir)
    policies = read_policies(policies_dir)
    findings = check_overlap(policies)

    if args.json:
        body = {
            "policies_dir": str(policies_dir),
            "policies": policies,
            "findings": findings,
            "pass": len(findings) == 0,
        }
        print(json.dumps(body, indent=2))
    else:
        text, _exit = render_human(policies, findings)
        sys.stdout.write(text)

    if findings and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
