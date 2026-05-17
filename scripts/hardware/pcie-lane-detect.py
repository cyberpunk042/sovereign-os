#!/usr/bin/env python3
"""scripts/hardware/pcie-lane-detect.py — R301 (E1.M26).

Operator-named (§1b mandate row, verbatim): "pci lane splits and
whatever like virtualization or what we find relevant via search
online and such". Closes E1.M26.

R270 (pcie-policy) ships the ADVISORY layer (board-specific lane-
share map + degradation table). R301 adds the concrete MEASUREMENT
layer: parses `lspci -vv` for each PCIe device's LnkCap (max width
+ speed) vs LnkSta (currently negotiated width + speed) and surfaces
per-device degradation + dual-GPU split state.

CLI:
  pcie-lane-detect.py status [--json|--human]
                        all PCIe devices with LnkCap/LnkSta
  pcie-lane-detect.py gpu    [--json|--human]
                        filter to GPU class only
  pcie-lane-detect.py degraded [--json|--human]
                        only devices where current < cap (or speed
                        downgraded). rc=1 if any GPU is degraded.

Exit codes:
  0  all GPUs at full LnkCap (or no GPU at all)
  1  ≥1 GPU running below LnkCap (width or speed downgraded)
  2  lspci unavailable
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "1.0.0"
ROUND = "R301"
SDD_VECTOR = "E1.M26"

# Match LnkCap / LnkSta lines from lspci -vv.
# Example: "LnkCap: Port #0, Speed 32GT/s, Width x16, ..."
#          "LnkSta: Speed 32GT/s, Width x16"
_LNK_RE = re.compile(
    r"Lnk(?P<which>Cap|Sta):.*?Speed\s+([\d.]+)GT/s.*?Width\s+x(\d+)",
    re.IGNORECASE,
)

# Map GT/s → PCIe gen (informational).
_GEN_BY_GT = {
    "2.5": "Gen1",
    "5":   "Gen2",
    "5.0": "Gen2",
    "8":   "Gen3",
    "8.0": "Gen3",
    "16":  "Gen4",
    "16.0": "Gen4",
    "32":  "Gen5",
    "32.0": "Gen5",
    "64":  "Gen6",
    "64.0": "Gen6",
}


def _gen_label(gt_s: str) -> str:
    return _GEN_BY_GT.get(gt_s, f"{gt_s}GT/s")


def probe_lspci_vv() -> tuple[str | None, str | None]:
    """Run `lspci -vvnn`; return (stdout, error-or-None)."""
    bin_path = shutil.which("lspci")
    if not bin_path:
        return None, "lspci not on PATH"
    try:
        r = subprocess.run(
            [bin_path, "-vvnn"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"lspci invocation failed: {e}"
    if r.returncode != 0:
        # lspci often returns nonzero on unprivileged invocations
        # missing config-space access — we still take whatever stdout
        # it managed to produce.
        if not r.stdout.strip():
            return None, f"lspci rc={r.returncode}: {r.stderr.strip()[:200]}"
    return r.stdout, None


def parse_devices(body: str) -> list[dict[str, Any]]:
    """Split lspci -vvnn into per-device blocks, extract LnkCap/LnkSta."""
    devices: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in body.splitlines():
        if not line.startswith((" ", "\t")):
            # Header line: "00:01.0 PCI bridge: AMD ..."
            if current:
                devices.append(current)
            parts = line.split(" ", 1)
            current = {
                "bdf": parts[0] if parts else "",
                "header": line.strip(),
                "class": _extract_class(line),
                "lnk_cap_speed": None,
                "lnk_cap_width": None,
                "lnk_sta_speed": None,
                "lnk_sta_width": None,
            }
            continue
        if current is None:
            continue
        m = _LNK_RE.search(line)
        if m:
            which = m.group("which").lower()
            speed = m.group(2)
            width = int(m.group(3))
            if which == "cap":
                current["lnk_cap_speed"] = speed
                current["lnk_cap_width"] = width
            elif which == "sta":
                current["lnk_sta_speed"] = speed
                current["lnk_sta_width"] = width
    if current:
        devices.append(current)
    return devices


def _extract_class(header: str) -> str:
    # Header shape: "<bdf> <class>: <vendor> ..."
    m = re.match(r"\S+\s+([^:]+):", header)
    return m.group(1).strip() if m else ""


def classify_degradation(d: dict[str, Any]) -> dict[str, Any]:
    cap_w = d.get("lnk_cap_width")
    sta_w = d.get("lnk_sta_width")
    cap_s = d.get("lnk_cap_speed")
    sta_s = d.get("lnk_sta_speed")
    if cap_w is None or sta_w is None:
        return {"verdict": "no-link-data",
                "detail": "device exposes no PCIe link state (e.g. on-die)"}
    width_degraded = sta_w < cap_w
    speed_degraded = (cap_s is not None and sta_s is not None
                      and _gen_label(sta_s) != _gen_label(cap_s)
                      and _gt_to_float(sta_s) < _gt_to_float(cap_s))
    if width_degraded and speed_degraded:
        return {"verdict": "both",
                "detail": f"width x{sta_w}<x{cap_w} + speed "
                          f"{_gen_label(sta_s)}<{_gen_label(cap_s)}"}
    if width_degraded:
        return {"verdict": "width-degraded",
                "detail": f"width x{sta_w} (cap x{cap_w})"}
    if speed_degraded:
        return {"verdict": "speed-degraded",
                "detail": f"speed {_gen_label(sta_s)} (cap {_gen_label(cap_s)})"}
    return {"verdict": "full-lnk-cap",
            "detail": f"x{sta_w} @ {_gen_label(sta_s)} (matches cap)"}


def _gt_to_float(s: str) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def is_gpu(d: dict[str, Any]) -> bool:
    cls = (d.get("class") or "").lower()
    return ("vga" in cls or "3d controller" in cls or "display controller" in cls)


def render_human(devices: list[dict], filter_label: str) -> str:
    lines = [f"── R301 sovereign-os PCIe lane detection — {filter_label} (E1.M26) ──"]
    lines.append(f"  devices: {len(devices)}")
    lines.append("")
    for d in devices:
        deg = d.get("degradation") or {}
        mark = {"full-lnk-cap": "OK ", "width-degraded": "?? ",
                "speed-degraded": "?? ", "both": "!! ",
                "no-link-data": "-- "}.get(deg.get("verdict"), "?? ")
        bdf = d.get("bdf", "")
        cls = (d.get("class") or "")[:30]
        cap_w = d.get("lnk_cap_width")
        sta_w = d.get("lnk_sta_width")
        cap_s = d.get("lnk_cap_speed")
        sta_s = d.get("lnk_sta_speed")
        if cap_w is None:
            link = "(no link data)"
        else:
            link = (f"x{sta_w}/x{cap_w} @ {_gen_label(sta_s)}/{_gen_label(cap_s)}"
                    if sta_w is not None else f"x?/x{cap_w}")
        lines.append(f"  [{mark}] {bdf:8s}  {cls:30s}  {link}")
        if deg.get("detail"):
            lines.append(f"            {deg['detail']}")
    return "\n".join(lines) + "\n"


def build_report(filter_kind: str) -> dict[str, Any]:
    body, err = probe_lspci_vv()
    if body is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "filter": filter_kind,
            "devices": [],
            "device_count": 0,
            "lspci_error": err,
            "rc": 2,
        }
    devices = parse_devices(body)
    for d in devices:
        d["degradation"] = classify_degradation(d)
    if filter_kind == "gpu":
        devices = [d for d in devices if is_gpu(d)]
    elif filter_kind == "degraded":
        devices = [d for d in devices
                   if d["degradation"]["verdict"] in
                       ("width-degraded", "speed-degraded", "both")]
    # GPU degradation severity sets rc.
    gpu_devs = [d for d in devices if is_gpu(d)]
    if filter_kind == "gpu":
        gpu_devs = devices
    any_gpu_degraded = any(
        d["degradation"]["verdict"] in
            ("width-degraded", "speed-degraded", "both")
        for d in gpu_devs
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "filter": filter_kind,
        "device_count": len(devices),
        "any_gpu_degraded": any_gpu_degraded,
        "devices": devices,
        "rc": 1 if any_gpu_degraded else 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pcie-lane-detect.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "gpu", "degraded"):
        sp = sub.add_parser(verb)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    kind = {"status": "all", "gpu": "gpu", "degraded": "degraded"}[args.verb]
    doc = build_report(kind)

    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        if doc.get("lspci_error"):
            print(f"ERROR lspci unavailable: {doc['lspci_error']}", file=sys.stderr)
        else:
            print(render_human(doc["devices"], kind), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
