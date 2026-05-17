#!/usr/bin/env python3
"""scripts/hardening/base-catalog.py — R306 (E2.M13).

Operator-named (§1b mandate row, verbatim): "Debian 13 Base ,
Sovereign OS and vision, why non-GUI by default. server, dashboard
or API and modules and tools vision". Closes E2.M13 — fills the
stop-hook-flagged "no comprehensive Debian 13 base-system hardening
catalog beyond BIOS directives" gap.

R299 ships the BIOS-side directives. R171 (E2.M8 partial) ships
systemd unit hardening lint. R306 closes the OS-LEVEL gap: a
structured catalog of Debian 13 base-system hardening items the
operator should verify on the SAIN-01 reference build:

  - sysctl hardening      (kernel.dmesg_restrict, kptr_restrict, etc.)
  - LSM state             (AppArmor / SELinux presence + enforcement)
  - update posture        (unattended-upgrades, apt source pinning)
  - auditd presence       (auditctl available + rules loaded)
  - fail2ban presence     (sshd jail active)
  - sshd config           (PermitRootLogin, PasswordAuthentication)

CLI:
  base-catalog.py list   [--axis X] [--config P] [--json|--human]
  base-catalog.py show   <item> [--config P] [--json|--human]
  base-catalog.py check  [--config P] [--json|--human]
                            run can_probe commands + report match
                            rate; rc=1 if any mismatch

Operator-overlay (R283/SDD-030): /etc/sovereign-os/hardening-catalog.toml
adds/replaces items. Lists REPLACE.

Exit codes:
  0  all probable items match recommended
  1  ≥1 mismatch (operator action recommended)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
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
ROUND = "R306"
SDD_VECTOR = "E2.M13"


DEFAULT_CATALOG: list[dict[str, Any]] = [
    # ── sysctl hardening ────────────────────────────────────
    {
        "name": "kernel.dmesg_restrict",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "1",
        "rationale": "Restrict dmesg to root-only — non-root can't "
                     "leak kernel pointers or sensitive boot messages.",
        "can_probe": True,
        "probe_command": "sysctl -n kernel.dmesg_restrict",
        "probe_match": "1",
        "operator_caveat": "Some monitoring agents need dmesg read; "
                           "operator may need to grant CAP_SYS_ADMIN "
                           "selectively.",
    },
    {
        "name": "kernel.kptr_restrict",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "2",
        "rationale": "Hide kernel pointers in /proc/* (=1) or hide "
                     "for ALL (=2). Mitigates info-leaks for exploit "
                     "chains.",
        "can_probe": True,
        "probe_command": "sysctl -n kernel.kptr_restrict",
        "probe_match": "2",
        "operator_caveat": "=2 may break some perf tooling that walks "
                           "/proc/kallsyms.",
    },
    {
        "name": "net.ipv4.conf.all.rp_filter",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "1",
        "rationale": "Strict reverse-path filtering — drops packets "
                     "with source addresses not reachable via the same "
                     "interface. Anti-spoofing baseline.",
        "can_probe": True,
        "probe_command": "sysctl -n net.ipv4.conf.all.rp_filter",
        "probe_match": "1",
        "operator_caveat": "Multi-homed routing setups may need "
                           "=2 (loose) instead.",
    },
    {
        "name": "net.ipv4.tcp_syncookies",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "1",
        "rationale": "SYN cookies — survive SYN-flood attacks without "
                     "dropping legitimate connections.",
        "can_probe": True,
        "probe_command": "sysctl -n net.ipv4.tcp_syncookies",
        "probe_match": "1",
        "operator_caveat": None,
    },
    {
        "name": "kernel.unprivileged_bpf_disabled",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "1",
        "rationale": "Block non-root from loading BPF programs — "
                     "major hardening for the eBPF attack surface.",
        "can_probe": True,
        "probe_command": "sysctl -n kernel.unprivileged_bpf_disabled",
        "probe_match": "1",
        "operator_caveat": "Conflicts with rootless eBPF observability "
                           "tooling — operator chooses.",
    },
    {
        "name": "kernel.yama.ptrace_scope",
        "axis": "sysctl",
        "scope": "sysctl",
        "recommended": "2",
        "rationale": "Restrict ptrace to root-only (=2) so non-root "
                     "processes can't snoop each other's memory.",
        "can_probe": True,
        "probe_command": "sysctl -n kernel.yama.ptrace_scope",
        "probe_match": "2",
        "operator_caveat": "Debugging tools like gdb/strace from non-root "
                           "require =0 or =1.",
    },

    # ── LSM / mandatory access control ────────────────────
    {
        "name": "apparmor",
        "axis": "lsm",
        "scope": "package",
        "recommended": "installed + active",
        "rationale": "AppArmor MAC — operator-pull mandatory access "
                     "control. Debian 13 ships AppArmor by default; "
                     "verify it's enforcing.",
        "can_probe": True,
        "probe_command": "aa-status --enabled && aa-status --profiled",
        "probe_match": "(any output indicates installed + active)",
        "operator_caveat": "Custom profiles for selfdef agent-guard / "
                           "modules ship via R171 doctrine.",
    },

    # ── Update posture ────────────────────────────────────
    {
        "name": "unattended-upgrades",
        "axis": "updates",
        "scope": "package",
        "recommended": "installed + enabled",
        "rationale": "Automatic Debian security upgrades — operator "
                     "doesn't manually run apt update for CVE patches.",
        "can_probe": True,
        "probe_command": "systemctl is-active unattended-upgrades",
        "probe_match": "active",
        "operator_caveat": "Operator chooses what to auto-upgrade in "
                           "/etc/apt/apt.conf.d/50unattended-upgrades.",
    },

    # ── Audit ─────────────────────────────────────────────
    {
        "name": "auditd",
        "axis": "audit",
        "scope": "service",
        "recommended": "installed + active",
        "rationale": "Linux audit framework — captures syscall events "
                     "for forensics + compliance. Cross-refs with "
                     "selfdef-collector-auditd.",
        "can_probe": True,
        "probe_command": "systemctl is-active auditd",
        "probe_match": "active",
        "operator_caveat": "Default rules light; operator-pull custom "
                           "rules via /etc/audit/rules.d/.",
    },

    # ── Network defense ───────────────────────────────────
    {
        "name": "fail2ban",
        "axis": "network",
        "scope": "service",
        "recommended": "installed + sshd jail active",
        "rationale": "Brute-force jail — auto-bans IPs that fail sshd "
                     "auth N times. Baseline for any internet-exposed "
                     "host.",
        "can_probe": True,
        "probe_command": "systemctl is-active fail2ban",
        "probe_match": "active",
        "operator_caveat": "Operator-pinned config under /etc/fail2ban/"
                           "jail.local — see sshd jail.",
    },

    # ── SSH config ────────────────────────────────────────
    {
        "name": "sshd.PermitRootLogin",
        "axis": "ssh",
        "scope": "config",
        "recommended": "no",
        "rationale": "Disable root SSH login — operator uses sudo from "
                     "named accounts. Reduces attack surface.",
        "can_probe": True,
        "probe_command": "sshd -T 2>/dev/null | grep '^permitrootlogin' | head -1",
        "probe_match": "permitrootlogin no",
        "operator_caveat": "Set to prohibit-password if operator wants "
                           "root via key-only fallback.",
    },
    {
        "name": "sshd.PasswordAuthentication",
        "axis": "ssh",
        "scope": "config",
        "recommended": "no",
        "rationale": "Disable password auth — keys only. Mitigates "
                     "credential-stuffing + brute-force attempts.",
        "can_probe": True,
        "probe_command": "sshd -T 2>/dev/null | grep '^passwordauthentication' | head -1",
        "probe_match": "passwordauthentication no",
        "operator_caveat": "Requires operator to have SSH key set up "
                           "BEFORE flipping this — otherwise lockout.",
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_CATALOG)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "hardening-catalog",
            {"items": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("items"):
            catalog = list(cfg["items"])
    return catalog, meta


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [d for d in catalog if isinstance(d, dict) and d.get("axis") == axis]


def resolve_item(catalog: list[dict], name: str) -> dict | None:
    for d in catalog:
        if isinstance(d, dict) and d.get("name") == name:
            return d
    return None


def run_probe(item: dict) -> dict[str, Any]:
    if not item.get("can_probe") or not item.get("probe_command"):
        return {"probable": False, "match": None,
                "detail": "not runtime-probable"}
    cmd = item["probe_command"]
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=8, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"probable": True, "match": None, "detail": f"probe failed: {e}"}
    output = (r.stdout or "").strip()
    expected = item.get("probe_match", "")
    if expected.startswith("(") and expected.endswith(")"):
        # heuristic: nonzero output means probe-passed
        match = bool(output)
    else:
        match = expected in output
    return {
        "probable": True,
        "match": match,
        "stdout_preview": output[:200],
        "detail": ("match" if match else f"expected `{expected}` not found"),
    }


def render_list_human(entries: list[dict], meta: dict) -> str:
    lines = ["── R306 sovereign-os Debian 13 hardening catalog (E2.M13) ──"]
    lines.append(f"  source:  {meta.get('_source')}")
    lines.append(f"  items:   {len(entries)}")
    lines.append("")
    axes = sorted({d.get("axis", "?") for d in entries if isinstance(d, dict)})
    for ax in axes:
        ax_items = [d for d in entries if d.get("axis") == ax]
        if not ax_items:
            continue
        lines.append(f"  ── {ax} ──")
        for d in ax_items:
            mark = "✓" if d.get("can_probe") else "  "
            lines.append(f"    [{mark}] {d.get('name'):40s}  recommended: {d.get('recommended')}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(d: dict) -> str:
    lines = [f"── R306 hardening item: {d.get('name')} (E2.M13) ──"]
    lines.append(f"  axis:           {d.get('axis')}")
    lines.append(f"  scope:          {d.get('scope')}")
    lines.append(f"  recommended:    {d.get('recommended')}")
    lines.append(f"  can_probe:      {d.get('can_probe')}")
    if d.get("probe_command"):
        lines.append(f"  probe cmd:      {d['probe_command']}")
        lines.append(f"  probe match:    {d.get('probe_match')}")
    if d.get("operator_caveat"):
        lines.append(f"  caveat:         {d['operator_caveat']}")
    lines.append("")
    lines.append(f"  rationale: {d.get('rationale')}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="base-catalog.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("item")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pc = sub.add_parser("check")
    pc.add_argument("--config", type=Path)
    fc = pc.add_mutually_exclusive_group()
    fc.add_argument("--json", dest="fmt", action="store_const", const="json")
    fc.add_argument("--human", dest="fmt", action="store_const", const="human")
    pc.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta = load_catalog(args.config)

    if args.verb == "list":
        entries = filter_axis(catalog, args.axis)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "axis_filter": args.axis,
                "total_count": len(catalog),
                "filtered_count": len(entries),
                "items": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries, meta), end="")
        return 0

    if args.verb == "show":
        d = resolve_item(catalog, args.item)
        if d is None:
            print(json.dumps({
                "error": f"unknown item: {args.item}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "item": d,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(d), end="")
        return 0

    if args.verb == "check":
        results = []
        any_mismatch = False
        for d in catalog:
            if not isinstance(d, dict):
                continue
            probe = run_probe(d)
            row = {
                "name": d.get("name"),
                "axis": d.get("axis"),
                "recommended": d.get("recommended"),
                "can_probe": d.get("can_probe"),
                "probe_result": probe,
            }
            results.append(row)
            if probe.get("match") is False:
                any_mismatch = True
        rc = 1 if any_mismatch else 0
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "any_mismatch": any_mismatch,
                "results": results,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R306 hardening check (E2.M13) ──")
            for r in results:
                p_ = r["probe_result"]
                if not r["can_probe"]:
                    mark = "--"
                elif p_.get("match"):
                    mark = "OK"
                elif p_.get("match") is False:
                    mark = "!!"
                else:
                    mark = "??"
                print(f"  [{mark}] {r['name']:40s}  {p_.get('detail', '')[:60]}")
            print()
            print(f"  any_mismatch: {any_mismatch}")
        return rc

    return 2


if __name__ == "__main__":
    sys.exit(main())
