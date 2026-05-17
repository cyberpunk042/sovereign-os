#!/usr/bin/env python3
"""scripts/install/install-mode-advisor.py — R310 (E2.M16).

Operator-named (§1b mandate row, verbatim): "non docker vs docker
install ? when possible ? container level vs system level". Closes
E2.M16.

For each installable sovereign-os / selfdef-side component, advises
container vs system install based on:
  - isolation_need        (high / medium / low)
  - dependency_footprint  (large / medium / small)
  - ipc_requirement       (root-shared / namespaced-ok / standalone)
  - root_required         (yes / no)
  - gpu_passthrough       (yes / no — GPU containers need toolkit)
  - kernel_module          (yes / no — needs kernel module load)

Each component carries default recommendation (system / container /
either) with rationale + per-mode tradeoffs.

CLI:
  install-mode-advisor.py list   [--axis X] [--config P] [--json|--human]
  install-mode-advisor.py show   <component> [--config P] [--json|--human]
  install-mode-advisor.py recommend [--config P] [--json|--human]
                                    full report — all components
                                    grouped by recommendation

Operator-overlay (R283/SDD-030): /etc/sovereign-os/install-mode-
advisor.toml — adds [[components]] entries OR overrides
[recommendation_override] per-component pinned mode.

Exit codes:
  0  rendered
  1  unknown component (show verb)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
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
ROUND = "R310"
SDD_VECTOR = "E2.M16"


DEFAULT_COMPONENTS: list[dict[str, Any]] = [
    {
        "name": "ollama",
        "axis": "inference",
        "isolation_need": "low",
        "dependency_footprint": "medium",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": True,
        "kernel_module": False,
        "recommendation": "either",
        "rationale": "Works both ways. System gives lowest GPU latency. "
                     "Container isolates CUDA libs from host but needs "
                     "nvidia-container-toolkit.",
        "system_tradeoff": "Pollutes host Python + CUDA libs; cleaner "
                            "uninstall via container.",
        "container_tradeoff": "Adds ~150 MB image; needs nvidia-container-"
                                "toolkit for GPU.",
    },
    {
        "name": "vllm",
        "axis": "inference",
        "isolation_need": "low",
        "dependency_footprint": "large",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": True,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "Heavy PyTorch + flash-attn + CUDA stack. Container "
                     "isolates the 5-10 GB dependency closure from the host "
                     "Python environment.",
        "system_tradeoff": "Massive host Python pollution; conflicts with "
                            "other PyTorch tools.",
        "container_tradeoff": "Larger pull (4-6 GB image); slower cold start.",
    },
    {
        "name": "selfdef-daemon",
        "axis": "selfdef",
        "isolation_need": "low",
        "dependency_footprint": "small",
        "ipc_requirement": "root-shared",
        "root_required": True,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "system",
        "rationale": "Reads /proc/* / journalctl / systemd-bus. Needs host "
                     "namespace + root. Container would need privileged + "
                     "host bind-mounts and lose isolation benefit anyway.",
        "system_tradeoff": "None — system is the right answer.",
        "container_tradeoff": "Loses observability, needs --privileged + "
                                "/proc + /sys host mounts.",
    },
    {
        "name": "selfdef-collector-auditd",
        "axis": "selfdef",
        "isolation_need": "low",
        "dependency_footprint": "small",
        "ipc_requirement": "root-shared",
        "root_required": True,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "system",
        "rationale": "auditd dispatcher binds to host audit subsystem; "
                     "container can't see kernel audit events.",
        "system_tradeoff": "None — system mandatory.",
        "container_tradeoff": "Won't work — auditd is host-only.",
    },
    {
        "name": "selfdef-collector-tetragon",
        "axis": "selfdef",
        "isolation_need": "low",
        "dependency_footprint": "medium",
        "ipc_requirement": "root-shared",
        "root_required": True,
        "gpu_passthrough": False,
        "kernel_module": True,
        "recommendation": "system",
        "rationale": "Loads eBPF programs into host kernel. Tetragon "
                     "officially supports container deploy but needs "
                     "privileged + host /sys/fs/bpf.",
        "system_tradeoff": "None — eBPF integration cleanest at system.",
        "container_tradeoff": "Needs --privileged + many host mounts.",
    },
    {
        "name": "suricata",
        "axis": "network",
        "isolation_need": "low",
        "dependency_footprint": "medium",
        "ipc_requirement": "root-shared",
        "root_required": True,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "system",
        "rationale": "AF_PACKET / NFQUEUE / inline mode all need host "
                     "network namespace + CAP_NET_ADMIN.",
        "system_tradeoff": "None.",
        "container_tradeoff": "Needs --net=host + privileged; isolation "
                                "lost.",
    },
    {
        "name": "tailscale",
        "axis": "network",
        "isolation_need": "low",
        "dependency_footprint": "small",
        "ipc_requirement": "root-shared",
        "root_required": True,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "system",
        "rationale": "Creates a host /dev/net/tun device + a host wireguard "
                     "interface. Container deploy is supported but "
                     "operator-side complexity isn't worth it.",
        "system_tradeoff": "None — apt install tailscale is the path.",
        "container_tradeoff": "Needs --net=host or sidecar + CAP_NET_ADMIN.",
    },
    {
        "name": "cloudflared",
        "axis": "network",
        "isolation_need": "medium",
        "dependency_footprint": "small",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "Pure userspace tunnel. Container isolates the cf-side "
                     "token + binary from host. Easy rotation.",
        "system_tradeoff": "Adds Cloudflare apt repo to host.",
        "container_tradeoff": "Trivial — official image is small.",
    },
    {
        "name": "traefik",
        "axis": "network",
        "isolation_need": "medium",
        "dependency_footprint": "small",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "Built for container-native deploy + Docker label "
                     "auto-discovery. System install loses most of that "
                     "convenience.",
        "system_tradeoff": "Single-binary on host works; loses label "
                            "auto-discovery.",
        "container_tradeoff": "Trivial — official image is small.",
    },
    {
        "name": "prometheus",
        "axis": "observability",
        "isolation_need": "low",
        "dependency_footprint": "small",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "Stateful disk usage but bind-mountable. Container "
                     "isolates version + storage path from host.",
        "system_tradeoff": "Operator manages apt package + systemd unit.",
        "container_tradeoff": "Easy upgrade rotations; explicit volume "
                                "mount required.",
    },
    {
        "name": "grafana",
        "axis": "observability",
        "isolation_need": "low",
        "dependency_footprint": "small",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "Web UI + stateful sqlite. Container isolates from "
                     "host runtime.",
        "system_tradeoff": "Adds grafana apt repo to host.",
        "container_tradeoff": "Trivial.",
    },
    {
        "name": "polarproxy",
        "axis": "network",
        "isolation_need": "high",
        "dependency_footprint": "small",
        "ipc_requirement": "namespaced-ok",
        "root_required": False,
        "gpu_passthrough": False,
        "kernel_module": False,
        "recommendation": "container",
        "rationale": "TLS-MITM proxy. Container isolates the CA private "
                     "key + intercept logs. Cleaner blast-radius for the "
                     "highest-risk component.",
        "system_tradeoff": "Host PKI surface widens; CA key lives in /etc.",
        "container_tradeoff": "Trivial; pair with restart policy.",
    },
]


def load_catalog(overlay_path: Path | None) -> tuple[list[dict], dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    catalog = list(DEFAULT_COMPONENTS)
    overrides: dict[str, str] = {}
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "install-mode-advisor",
            {"components": [], "recommendation_override": {}},
            explicit_path=overlay_path,
        )
        meta["_source"] = cfg.get("_source", meta["_source"])
        meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("components"):
            catalog = list(cfg["components"])
        if isinstance(cfg.get("recommendation_override"), dict):
            overrides = dict(cfg["recommendation_override"])
    # Apply per-component overrides.
    if overrides:
        for c in catalog:
            if isinstance(c, dict) and c.get("name") in overrides:
                c = dict(c)
                c["operator_pinned_recommendation"] = overrides[c["name"]]
        # Apply via index since list comprehension creates copies.
        for i, c in enumerate(catalog):
            if isinstance(c, dict) and c.get("name") in overrides:
                new = dict(c)
                new["operator_pinned_recommendation"] = overrides[c["name"]]
                catalog[i] = new
    return catalog, meta, overrides


def filter_axis(catalog: list[dict], axis: str | None) -> list[dict]:
    if axis is None:
        return list(catalog)
    return [d for d in catalog if isinstance(d, dict) and d.get("axis") == axis]


def resolve(catalog: list[dict], name: str) -> dict | None:
    for d in catalog:
        if isinstance(d, dict) and d.get("name") == name:
            return d
    return None


def effective_recommendation(c: dict) -> str:
    if c.get("operator_pinned_recommendation"):
        return c["operator_pinned_recommendation"]
    return c.get("recommendation", "either")


def render_list_human(entries: list[dict]) -> str:
    lines = [f"── R310 sovereign-os install-mode advisor (E2.M16) ──",
             f"  components: {len(entries)}", ""]
    axes = sorted({d.get("axis", "?") for d in entries if isinstance(d, dict)})
    for ax in axes:
        items = [d for d in entries if d.get("axis") == ax]
        if not items:
            continue
        lines.append(f"  ── {ax} ──")
        for d in items:
            rec = effective_recommendation(d)
            pin = ""
            if d.get("operator_pinned_recommendation"):
                pin = " [operator-pinned]"
            lines.append(f"    {d.get('name'):28s}  → {rec}{pin}")
        lines.append("")
    return "\n".join(lines)


def render_show_human(d: dict) -> str:
    rec = effective_recommendation(d)
    lines = [f"── R310 install-mode: {d.get('name')} (E2.M16) ──",
             f"  axis:                  {d.get('axis')}",
             f"  isolation_need:        {d.get('isolation_need')}",
             f"  dependency_footprint:  {d.get('dependency_footprint')}",
             f"  ipc_requirement:       {d.get('ipc_requirement')}",
             f"  root_required:         {d.get('root_required')}",
             f"  gpu_passthrough:       {d.get('gpu_passthrough')}",
             f"  kernel_module:         {d.get('kernel_module')}",
             "",
             f"  recommendation:        {rec}"]
    if d.get("operator_pinned_recommendation"):
        lines.append(f"    (operator-pinned via overlay; default was "
                     f"{d.get('recommendation')})")
    lines.append("")
    if d.get("rationale"):
        lines.append(f"  rationale: {d['rationale']}")
        lines.append("")
    lines.append(f"  system tradeoff:    {d.get('system_tradeoff')}")
    lines.append(f"  container tradeoff: {d.get('container_tradeoff')}")
    return "\n".join(lines) + "\n"


def render_recommend(catalog: list[dict]) -> dict[str, Any]:
    buckets: dict[str, list[dict]] = {"system": [], "container": [], "either": []}
    for d in catalog:
        if not isinstance(d, dict):
            continue
        rec = effective_recommendation(d)
        buckets.setdefault(rec, []).append({
            "name": d.get("name"),
            "axis": d.get("axis"),
            "operator_pinned": bool(d.get("operator_pinned_recommendation")),
        })
    return buckets


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install-mode-advisor.py")
    sub = p.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--axis")
    pl.add_argument("--config", type=Path)
    fl = pl.add_mutually_exclusive_group()
    fl.add_argument("--json", dest="fmt", action="store_const", const="json")
    fl.add_argument("--human", dest="fmt", action="store_const", const="human")
    pl.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("component")
    ps.add_argument("--config", type=Path)
    fs = ps.add_mutually_exclusive_group()
    fs.add_argument("--json", dest="fmt", action="store_const", const="json")
    fs.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pr = sub.add_parser("recommend")
    pr.add_argument("--config", type=Path)
    fr = pr.add_mutually_exclusive_group()
    fr.add_argument("--json", dest="fmt", action="store_const", const="json")
    fr.add_argument("--human", dest="fmt", action="store_const", const="human")
    pr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    catalog, meta, overrides = load_catalog(args.config)

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
                "components": entries,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(entries), end="")
        return 0

    if args.verb == "show":
        d = resolve(catalog, args.component)
        if d is None:
            print(json.dumps({
                "error": f"unknown component: {args.component}",
                "known": [x.get("name") for x in catalog if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "component": d,
                "effective_recommendation": effective_recommendation(d),
                "overlay": meta,
            }, indent=2))
        else:
            print(render_show_human(d), end="")
        return 0

    if args.verb == "recommend":
        buckets = render_recommend(catalog)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "total_components": len(catalog),
                "recommendations": buckets,
                "operator_pinned_count": len([
                    d for d in catalog
                    if isinstance(d, dict) and d.get("operator_pinned_recommendation")
                ]),
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R310 install-mode recommendation report (E2.M16) ──")
            print(f"  total components: {len(catalog)}")
            for bucket in ("system", "container", "either"):
                items = buckets.get(bucket, [])
                print(f"")
                print(f"  ── {bucket} ({len(items)}) ──")
                for c in items:
                    pin = " [pinned]" if c.get("operator_pinned") else ""
                    print(f"    {c['name']:28s} ({c['axis']}){pin}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
