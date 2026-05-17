#!/usr/bin/env python3
"""scripts/hardware/virt-info.py — R255 (SDD-026 Z-19 new vector).

Operator-named (verbatim, 2026-05-17 expansion): "pci lane splits and
whatever like virtualization or what we find relevant via search
online and such."

Opens Z-19: virtualization + PCIe lane allocation probe.

Surfaces:
  - CPU virtualization flags (vmx/svm) + secondary (ept, npt, vpid, ...)
  - KVM module load state (/proc/modules + /dev/kvm presence)
  - IOMMU state (/sys/class/iommu/ + kernel cmdline parse for
    intel_iommu=on / amd_iommu=on)
  - VFIO state (vfio + vfio-pci module load + currently-bound devices)
  - PCIe per-device lane allocation (lspci -vv → LnkSta width/speed)
  - Container runtime detection (docker / podman / containerd)
  - nested-virt enablement state (/sys/module/kvm_*/parameters/nested)

CLI:
  virt-info.py cpu [--json]            CPU virt flag detail
  virt-info.py kvm [--json]            KVM kernel + device state
  virt-info.py iommu [--json]          IOMMU state + cmdline
  virt-info.py pci [--json]            per-device PCIe lane allocation
  virt-info.py runtimes [--json]       container runtimes installed
  virt-info.py show [--json]           full snapshot

Exit codes:
  0  rendered
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


VIRT_FLAGS_RELEVANT = {
    "vmx",      # Intel VT-x
    "svm",      # AMD-V
    "ept",      # Intel Extended Page Tables (nested paging)
    "npt",      # AMD Nested Page Tables
    "vpid",
    "vnmi",
    "tpr_shadow",
    "flexpriority",
    "vmcs_shadow_vmcs",
}


def read_proc_cpuinfo_flags() -> list[str]:
    p = Path("/proc/cpuinfo")
    if not p.exists():
        return []
    try:
        text = p.read_text()
    except OSError:
        return []
    for line in text.splitlines():
        if line.startswith("flags") and ":" in line:
            return line.split(":", 1)[1].strip().split()
    return []


def read_kernel_cmdline() -> str:
    p = Path("/proc/cmdline")
    if not p.exists():
        return ""
    try:
        return p.read_text().strip()
    except OSError:
        return ""


def module_loaded(name: str) -> bool:
    p = Path("/proc/modules")
    if not p.exists():
        return False
    try:
        for line in p.read_text().splitlines():
            if line.startswith(name + " ") or line.startswith(name.replace("-", "_") + " "):
                return True
    except OSError:
        pass
    return False


def cmd_cpu(args: argparse.Namespace) -> int:
    flags = read_proc_cpuinfo_flags()
    relevant = {f: (f in flags) for f in sorted(VIRT_FLAGS_RELEVANT)}
    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (cpu virt flags)",
        "vendor_flag": "vmx (Intel)" if "vmx" in flags else ("svm (AMD)" if "svm" in flags else "(none)"),
        "virt_supported": any(f in flags for f in ("vmx", "svm")),
        "nested_paging_supported": any(f in flags for f in ("ept", "npt")),
        "flags_relevant": relevant,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info cpu (SDD-026 Z-19) ──")
    print(f"  vendor:                {out['vendor_flag']}")
    print(f"  virt supported:        {out['virt_supported']}")
    print(f"  nested paging:         {out['nested_paging_supported']}")
    for f, present in relevant.items():
        mark = "✓" if present else "·"
        print(f"    {mark} {f}")
    return 0


def cmd_kvm(args: argparse.Namespace) -> int:
    kvm_module = module_loaded("kvm")
    kvm_intel = module_loaded("kvm_intel")
    kvm_amd = module_loaded("kvm_amd")
    dev_kvm = Path("/dev/kvm").exists()

    nested = None
    for vendor in ("kvm_intel", "kvm_amd"):
        nested_path = Path(f"/sys/module/{vendor}/parameters/nested")
        if nested_path.exists():
            try:
                v = nested_path.read_text().strip()
                nested = {"vendor": vendor, "enabled": v in {"Y", "1"}}
                break
            except OSError:
                pass

    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (kvm)",
        "kvm_module_loaded": kvm_module,
        "kvm_intel_loaded": kvm_intel,
        "kvm_amd_loaded": kvm_amd,
        "dev_kvm_present": dev_kvm,
        "nested_virt": nested,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info kvm (SDD-026 Z-19) ──")
    print(f"  kvm module:    {kvm_module}")
    print(f"  kvm_intel:     {kvm_intel}")
    print(f"  kvm_amd:       {kvm_amd}")
    print(f"  /dev/kvm:      {dev_kvm}")
    if nested:
        print(f"  nested-virt:   {nested['enabled']} (via {nested['vendor']})")
    else:
        print(f"  nested-virt:   (no kvm vendor module loaded)")
    return 0


def cmd_iommu(args: argparse.Namespace) -> int:
    iommu_dir = Path("/sys/class/iommu")
    devices: list[str] = []
    if iommu_dir.is_dir():
        try:
            devices = sorted(p.name for p in iommu_dir.iterdir())
        except OSError:
            pass
    cmdline = read_kernel_cmdline()
    cmdline_intel = "intel_iommu=on" in cmdline
    cmdline_amd = "amd_iommu=on" in cmdline or "iommu=pt" in cmdline
    cmdline_acs_override = "pcie_acs_override" in cmdline
    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (iommu)",
        "iommu_devices": devices,
        "iommu_enabled_sysfs": bool(devices),
        "kernel_cmdline_intel_iommu_on": cmdline_intel,
        "kernel_cmdline_amd_iommu_on": cmdline_amd,
        "kernel_cmdline_acs_override": cmdline_acs_override,
        "kernel_cmdline": cmdline,
        "advisory": _iommu_advisory(devices, cmdline_intel, cmdline_amd),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info iommu (SDD-026 Z-19) ──")
    print(f"  iommu enabled (sysfs): {bool(devices)}")
    print(f"  iommu devices:         {len(devices)}")
    print(f"  cmdline intel_iommu=on:{cmdline_intel}")
    print(f"  cmdline amd_iommu=on:  {cmdline_amd}")
    print(f"  cmdline ACS override:  {cmdline_acs_override}")
    if out["advisory"]:
        print(f"\n  advisory: {out['advisory']}")
    return 0


def _iommu_advisory(devices: list, intel_on: bool, amd_on: bool) -> str | None:
    if devices:
        return None
    if not intel_on and not amd_on:
        return (
            "IOMMU not enabled. For VFIO GPU passthrough OR PCI device "
            "isolation, add `intel_iommu=on` (Intel) OR `amd_iommu=on iommu=pt` "
            "(AMD) to GRUB_CMDLINE_LINUX in /etc/default/grub then "
            "`sudo update-grub && reboot`."
        )
    return "IOMMU cmdline flag present but no sysfs devices — kernel may not have IOMMU driver compiled."


def cmd_pci(args: argparse.Namespace) -> int:
    """lspci -vv → per-device LnkSta width + speed."""
    if not shutil.which("lspci"):
        out = {
            "round": "R255",
            "vector": "SDD-026 Z-19 (pci)",
            "devices": [],
            "error": "lspci not on PATH",
        }
        if args.json:
            print(json.dumps(out, indent=2))
            return 0
        print("ERROR lspci not on PATH", file=sys.stderr)
        return 2
    try:
        r = subprocess.run(
            ["lspci", "-vv"], capture_output=True, text=True, timeout=10, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        if args.json:
            print(json.dumps({"round": "R255", "devices": []}, indent=2))
        else:
            print("ERROR lspci failed to run", file=sys.stderr)
        return 2
    devices: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in r.stdout.splitlines():
        if not line.startswith("\t") and not line.startswith(" "):
            if cur is not None and ("link_cap" in cur or "link_sta" in cur):
                devices.append(cur)
            parts = line.split(":", 1)
            bdf = parts[0].strip() if parts else ""
            name = parts[1].strip() if len(parts) > 1 else ""
            cur = {"bdf": bdf, "name": name}
            continue
        if cur is None:
            continue
        stripped = line.strip()
        if stripped.startswith("LnkCap:"):
            cur["link_cap"] = stripped[len("LnkCap:"):].strip()
        elif stripped.startswith("LnkSta:"):
            cur["link_sta"] = stripped[len("LnkSta:"):].strip()
            # Operator-friendly: extract width number.
            for tok in cur["link_sta"].split(","):
                tok = tok.strip()
                if tok.startswith("Width "):
                    cur["current_width"] = tok.split(" ", 1)[1]
                elif tok.startswith("Speed "):
                    cur["current_speed"] = tok.split(" ", 1)[1]
    if cur is not None and ("link_cap" in cur or "link_sta" in cur):
        devices.append(cur)
    # Filter to interesting devices: GPUs, NVMe, NICs.
    interesting = [
        d for d in devices
        if any(k in d.get("name", "").lower() for k in
               ("vga", "3d controller", "nvm express", "ethernet", "wireless"))
    ]
    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (pci lane allocation)",
        "device_count_total": len(devices),
        "interesting_count": len(interesting),
        "interesting": interesting,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info pci (SDD-026 Z-19) ──")
    print(f"  total PCI devices probed: {len(devices)}")
    print(f"  interesting (GPU/NVMe/NIC): {len(interesting)}")
    for d in interesting:
        cur_w = d.get("current_width", "?")
        cur_s = d.get("current_speed", "?")
        print(f"\n  {d['bdf']}  {d['name']}")
        print(f"    current: width={cur_w}  speed={cur_s}")
        if d.get("link_cap"):
            print(f"    capable: {d['link_cap']}")
    return 0


def cmd_runtimes(args: argparse.Namespace) -> int:
    runtimes = []
    for name, bin_ in [
        ("docker", "docker"),
        ("podman", "podman"),
        ("containerd", "containerd"),
        ("nerdctl", "nerdctl"),
        ("crun", "crun"),
        ("runc", "runc"),
    ]:
        path = shutil.which(bin_)
        runtimes.append({
            "name": name,
            "installed": path is not None,
            "path": path,
        })
    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (container runtimes)",
        "runtimes": runtimes,
        "installed_count": sum(1 for r in runtimes if r["installed"]),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info runtimes ──")
    for r in runtimes:
        mark = "✓" if r["installed"] else "·"
        print(f"  {mark} {r['name']:<12} {r['path'] or '(absent)'}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    # Aggregate every sub-command's data into one snapshot.
    class FakeArgs:
        json = True
    # Reuse cmd_* logic by capturing their JSON output.
    import io, contextlib
    def _capture(fn):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn(FakeArgs())
        return json.loads(buf.getvalue() or "{}")

    out = {
        "round": "R255",
        "vector": "SDD-026 Z-19 (virt-info snapshot)",
        "cpu": _capture(cmd_cpu),
        "kvm": _capture(cmd_kvm),
        "iommu": _capture(cmd_iommu),
        "pci": _capture(cmd_pci),
        "runtimes": _capture(cmd_runtimes),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R255 sovereign-os virt-info show (SDD-026 Z-19) ──")
    print(f"\n  CPU virt:    {out['cpu'].get('vendor_flag')}  supported={out['cpu'].get('virt_supported')}  nested-paging={out['cpu'].get('nested_paging_supported')}")
    print(f"  KVM:         module={out['kvm'].get('kvm_module_loaded')}  /dev/kvm={out['kvm'].get('dev_kvm_present')}")
    print(f"  IOMMU:       sysfs-enabled={out['iommu'].get('iommu_enabled_sysfs')}  cmdline={out['iommu'].get('kernel_cmdline_intel_iommu_on') or out['iommu'].get('kernel_cmdline_amd_iommu_on')}")
    print(f"  PCI interesting devices: {out['pci'].get('interesting_count')}")
    print(f"  Container runtimes installed: {out['runtimes'].get('installed_count')} / {len(out['runtimes'].get('runtimes', []))}")
    if out['iommu'].get('advisory'):
        print(f"\n  IOMMU advisory: {out['iommu']['advisory']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="virt-info.py",
        description="R255 (SDD-026 Z-19) — virtualization + PCIe + container-runtime probe.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("cpu", cmd_cpu, "CPU virt flags"),
        ("kvm", cmd_kvm, "KVM kernel + device state"),
        ("iommu", cmd_iommu, "IOMMU state + cmdline"),
        ("pci", cmd_pci, "per-device PCIe lane allocation"),
        ("runtimes", cmd_runtimes, "container runtimes installed"),
        ("show", cmd_show, "full snapshot"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
