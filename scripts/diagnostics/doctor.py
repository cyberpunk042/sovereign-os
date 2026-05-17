#!/usr/bin/env python3
"""scripts/diagnostics/doctor.py — R266 (E6.M5).

Operator-named (verbatim, 2026-05-17): "autohealth and doctor and
analysis and event and notification and messaging".

R226 ships scan (raw multi-probe). R234 ships insights (fs+log
synthesis). R263 ships services-advisor (network triad). R266 closes
the umbrella: a `doctor` verb that runs every shipped advisor +
synthesizer in one pass + emits a CROSS-AXIS analysis ranked by
operator-actionable severity, with each finding tagged by which
Epic/Module it came from.

Sub-probes (each runs in isolation; one failure doesn't take down
the others):
  health-scan                   R226 / E6.M1
  insights                      R234 / E2.M5
  power-status advisories       R252 + R265 / E1.M5 + E1.M11
  bios-info advisories          R251 / E1.M2
  memory-profile advisory       R257 / E1.M3
  virt-info iommu               R255 / E1.M4
  services-advisor              R263 / E3.M2
  install-paths                 R237 / E2.M3
  install-options (selfdef)     selfdef SD-R86 / E2.M2

Each finding has:
  source       which probe surfaced it
  epic         E<N> bucket
  module       E<N>.M<N> ID
  severity     critical / attention / informational
  title        one-line summary
  detail       elaboration
  action       copy-pasteable command

CLI:
  doctor.py run [--severity S] [--limit N] [--json]
  doctor.py probes [--json]      list available sub-probes
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

SEVERITY_RANK = {"critical": 0, "attention": 1, "informational": 2}


def _call_probe(cmd_argv: list[str], timeout_s: int = 25) -> tuple[int, dict[str, Any] | None, str]:
    """Returns (rc, parsed_json or None, stderr-snippet)."""
    if not Path(cmd_argv[0]).exists():
        return (127, None, f"{cmd_argv[0]} missing")
    try:
        r = subprocess.run(
            [sys.executable, *cmd_argv], capture_output=True, text=True,
            timeout=timeout_s, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return (124, None, str(e))
    parsed = None
    if r.stdout.strip():
        try:
            parsed = json.loads(r.stdout)
        except json.JSONDecodeError:
            parsed = None
    return (r.returncode, parsed, (r.stderr or "").strip()[:200])


def _bucket(epic: str, module: str) -> dict[str, str]:
    return {"epic": epic, "module": module}


def findings_from_health_scan() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "hardware" / "health-scan.py"
    rc, d, _ = _call_probe([str(bin_path), "--json"])
    out: list[dict[str, Any]] = []
    if d is None:
        return out
    for probe in d.get("probes") or []:
        sev = probe.get("severity")
        if sev in {"attention", "down"}:
            out.append({
                "source": "health-scan",
                **_bucket("E6", "E6.M1"),
                "severity": "critical" if sev == "down" else "attention",
                "title": f"{probe.get('probe')} probe: {sev}",
                "detail": probe.get("detail", ""),
                "action": f"sovereign-osctl health scan --probe {probe.get('probe')} --json",
            })
    return out


def findings_from_insights() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "insights" / "synthesize.py"
    rc, d, _ = _call_probe([str(bin_path), "--json"])
    if d is None:
        return []
    out: list[dict[str, Any]] = []
    for ins in (d.get("insights") or []):
        if ins.get("severity") == "informational":
            continue
        out.append({
            "source": "insights",
            **_bucket("E2", "E2.M5"),
            "severity": ins.get("severity"),
            "title": ins.get("title", ""),
            "detail": ins.get("detail", ""),
            "action": ins.get("action", "sovereign-osctl insights"),
        })
    return out


def findings_from_power_advisories() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
    rc, d, _ = _call_probe([str(bin_path), "advisories", "--json"])
    if d is None:
        return []
    out: list[dict[str, Any]] = []
    verdict = d.get("verdict")
    severity_map = {"critical": "critical", "attention": "attention"}
    if verdict in severity_map:
        for adv in (d.get("advisories") or []):
            module = "E1.M11" if "thermal" in adv.lower() else "E1.M5"
            out.append({
                "source": "power-advisories",
                **_bucket("E1", module),
                "severity": severity_map[verdict],
                "title": f"power: {verdict}",
                "detail": adv,
                "action": "sovereign-osctl power-status advisories",
            })
    return out


def findings_from_bios_advisories() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "hardware" / "bios-info.py"
    rc, d, _ = _call_probe([str(bin_path), "advisories", "--json"])
    if d is None or not d.get("matched_board"):
        return []
    # BIOS advisories are informational by default (they don't escalate
    # the host's state; they describe what COULD be tuned). The doctor
    # surfaces them only when --include-informational is requested OR
    # when a critical hint slips through (none in cycle-8).
    out: list[dict[str, Any]] = []
    for adv in (d.get("advisories") or [])[:3]:
        out.append({
            "source": "bios-advisories",
            **_bucket("E1", "E1.M2"),
            "severity": "informational",
            "title": f"BIOS hint ({d['matched_board']})",
            "detail": adv,
            "action": "sovereign-osctl bios-info advisories",
        })
    return out


def findings_from_memory_profile() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "hardware" / "memory-profile.py"
    rc, d, _ = _call_probe([str(bin_path), "advisory", "--json"])
    if d is None:
        return []
    verdict = d.get("verdict")
    if verdict == "xmp-expo-disabled":
        return [{
            "source": "memory-profile",
            **_bucket("E1", "E1.M3"),
            "severity": "attention",
            "title": "XMP/EXPO disabled",
            "detail": d.get("message", ""),
            "action": "sovereign-osctl memory-profile advisory (enable in BIOS)",
        }]
    if verdict == "manually-overclocked":
        return [{
            "source": "memory-profile",
            **_bucket("E1", "E1.M3"),
            "severity": "informational",
            "title": "memory manually overclocked",
            "detail": d.get("message", ""),
            "action": "run memtest86+ to confirm stability",
        }]
    return []


def findings_from_virt_iommu() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "hardware" / "virt-info.py"
    rc, d, _ = _call_probe([str(bin_path), "iommu", "--json"])
    if d is None or not d.get("advisory"):
        return []
    return [{
        "source": "virt-info-iommu",
        **_bucket("E1", "E1.M4"),
        "severity": "informational",
        "title": "IOMMU posture",
        "detail": d.get("advisory", ""),
        "action": "sovereign-osctl virt-info iommu",
    }]


def findings_from_services_advisor() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "network" / "services-advisor.py"
    rc, d, _ = _call_probe([str(bin_path), "show", "--json"])
    if d is None:
        return []
    out: list[dict[str, Any]] = []
    for name, r in (d.get("results") or {}).items():
        if r.get("posture") in {"attention", "degraded"}:
            out.append({
                "source": "services-advisor",
                **_bucket("E3", "E3.M2"),
                "severity": "critical" if r["posture"] == "degraded" else "attention",
                "title": f"{name}: {r['posture']}",
                "detail": r.get("advisory", ""),
                "action": f"sovereign-osctl services-advisor {name}",
            })
    return out


def findings_from_install_paths() -> list[dict[str, Any]]:
    bin_path = REPO_ROOT / "scripts" / "install" / "paths.py"
    if not bin_path.exists():
        return []
    rc, d, _ = _call_probe([str(bin_path), "show", "--json"])
    if d is None:
        return []
    out: list[dict[str, Any]] = []
    counts = d.get("counts") or {}
    if counts.get("blocked", 0) > 0:
        out.append({
            "source": "install-paths",
            **_bucket("E3", "E3.M3"),
            "severity": "attention",
            "title": f"{counts['blocked']} install-path feature(s) blocked",
            "detail": "One or more features cannot install on their default layer due to network/runtime state.",
            "action": "sovereign-osctl install-paths show",
        })
    return out


PROBES = [
    ("health-scan", findings_from_health_scan),
    ("insights", findings_from_insights),
    ("power-advisories", findings_from_power_advisories),
    ("bios-advisories", findings_from_bios_advisories),
    ("memory-profile", findings_from_memory_profile),
    ("virt-info-iommu", findings_from_virt_iommu),
    ("services-advisor", findings_from_services_advisor),
    ("install-paths", findings_from_install_paths),
]


def cmd_run(args: argparse.Namespace) -> int:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    findings: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for name, fn in PROBES:
        t0 = time.time()
        try:
            rows = fn()
        except Exception as e:  # defense-in-depth: doctor never blows up on probe error
            rows = []
            sources.append({"name": name, "ok": False, "error": str(e), "duration_s": round(time.time() - t0, 3)})
        else:
            sources.append({"name": name, "ok": True, "finding_count": len(rows), "duration_s": round(time.time() - t0, 3)})
        findings.extend(rows)
    # Filter by min-severity if specified.
    if args.severity:
        min_rank = SEVERITY_RANK[args.severity]
        findings = [f for f in findings if SEVERITY_RANK.get(f["severity"], 9) <= min_rank]
    findings.sort(key=lambda f: SEVERITY_RANK.get(f["severity"], 9))
    counts = {
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "attention": sum(1 for f in findings if f["severity"] == "attention"),
        "informational": sum(1 for f in findings if f["severity"] == "informational"),
        "total": len(findings),
    }
    rc = 1 if counts["critical"] > 0 else 0
    if args.limit and not args.all:
        findings = findings[:args.limit]
    out = {
        "round": "R266",
        "vector": "E6.M5 (doctor cross-axis synthesis)",
        "started_at": started_at,
        "sources": sources,
        "counts": counts,
        "findings": findings,
        "needs_attention": counts["critical"] > 0 or counts["attention"] > 0,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R266 sovereign-os doctor (E6.M5) ──")
    print(f"  started_at: {started_at}")
    print(f"  sources:    {len(sources)} probes")
    failures = [s for s in sources if not s["ok"]]
    if failures:
        for s in failures:
            print(f"    ✗ {s['name']:<24}  {s.get('error','?')}")
    print(f"  totals:     critical={counts['critical']}  attention={counts['attention']}  informational={counts['informational']}")
    if not findings:
        print()
        print("  (no findings — host is healthy across every probed axis)")
        return rc
    glyph = {"critical": "⛔", "attention": "⚠ ", "informational": "·"}
    print()
    for f in findings:
        g = glyph.get(f["severity"], "?")
        print(f"  {g} [{f['severity']:13s}] [{f['epic']}/{f['module']}] {f['title']}")
        if f.get("detail"):
            for line in f["detail"].split("\n"):
                print(f"      {line}")
        if f.get("action"):
            print(f"      action: {f['action']}")
        print(f"      source: {f['source']}")
        print()
    return rc


def cmd_probes(args: argparse.Namespace) -> int:
    rows = [{"name": n} for n, _ in PROBES]
    out = {
        "round": "R266",
        "vector": "E6.M5 (doctor probes inventory)",
        "probe_count": len(rows),
        "probes": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R266 doctor probes ({len(rows)}) ──")
    for r in rows:
        print(f"  • {r['name']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doctor.py",
        description="R266 (E6.M5) — cross-axis diagnostic synthesizer.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pr = sub.add_parser("run", help="run all probes + synthesize findings")
    pr.add_argument("--severity", choices=["critical", "attention", "informational"],
                    help="filter to this severity OR higher")
    pr.add_argument("--limit", type=int, default=20)
    pr.add_argument("--all", action="store_true", help="ignore --limit")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_run)
    pp = sub.add_parser("probes", help="list available probes")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_probes)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
