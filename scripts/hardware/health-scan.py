#!/usr/bin/env python3
"""scripts/hardware/health-scan.py — R226 (SDD-026 Z-6 doctor/autohealth).

Operator-named (verbatim): "With scans too. with autohealth and
doctor and analysis and event and notification and messaging."

Composite read-only scanner. Invokes every shipped Z-vector card's
--json mode + folds into one health rollup with operator-readable
severity (ok / attention / down) per probe + an aggregate verdict.

Probes (each is a SHIPPED script — no new state):

  gpu       R219 / Z-5  scripts/hardware/gpu-watch.py
  network   R220 / Z-7  scripts/hardware/network-status.py
  cpu_mode  R221 / Z-4  scripts/hardware/cpu-mode.py show
  fs_usage  R222 / Z-10 scripts/hardware/fs-insights.py usage
  raid      R223 / Z-9  scripts/hardware/raid-status.py status
  flex      R224 / Z-3  scripts/hardware/profile-flex.py show

A future round (Z-6 full) wires the NOTIFICATION FAN-OUT (matrix /
ntfy / tailscale-ping / webhook) on top of the rc=1 exit of this
script. Cycle-8 ships the SCAN; the notifier pulls from this
script's --json output via a separate hook.

CLI:
  health-scan.py             human-readable banner
  health-scan.py --json      machine-readable JSON for the dashboard
  health-scan.py --probe N   run only one probe (id from the table)

Exit codes:
  0  every probe reports ok (or "informational" — no operator action needed)
  1  at least one probe needs operator attention (the autohealth signal)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_probe(script: str, args: list[str]) -> tuple[int, str, str]:
    """Returns (rc, stdout, stderr) — capture-output on the sibling script."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / script
    if not bin_path.exists():
        return (127, "", f"{bin_path} missing")
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return (124, "", str(e))
    return (r.returncode, r.stdout, r.stderr)


def _parse_or(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------- per-probe analysers


def probe_gpu() -> dict[str, Any]:
    rc, stdout, _ = _run_probe("gpu-watch.py", [])
    d = _parse_or(stdout) or {}
    flagged = [
        g for g in d.get("gpus", []) if g.get("policed") and g.get("flags")
    ]
    sev = "attention" if flagged else "ok"
    detail = (
        f"{len(flagged)} GPU(s) flagged"
        if flagged
        else f"{len(d.get('gpus', []))} GPU(s) within policy"
    )
    return {
        "probe": "gpu",
        "round": "R219",
        "vector": "Z-5",
        "rc": rc,
        "severity": sev,
        "detail": detail,
        "flagged_items": [
            {"id": g.get("name"), "idx": g.get("idx"), "flags": g.get("flags")}
            for g in flagged
        ],
    }


def probe_network() -> dict[str, Any]:
    rc, stdout, _ = _run_probe("network-status.py", [])
    d = _parse_or(stdout) or {"components": []}
    flagged = [
        c for c in d.get("components", []) if c.get("status") in {"warn", "down"}
    ]
    sev = "attention" if flagged else "ok"
    detail = (
        f"{len(flagged)} component(s) in warn/down"
        if flagged
        else f"{len(d.get('components', []))} component(s) ok or not-installed"
    )
    return {
        "probe": "network",
        "round": "R220",
        "vector": "Z-7",
        "rc": rc,
        "severity": sev,
        "detail": detail,
        "flagged_items": [
            {"id": c.get("component"), "status": c.get("status"), "detail": c.get("detail")}
            for c in flagged
        ],
    }


def probe_cpu_mode() -> dict[str, Any]:
    rc, stdout, _ = _run_probe("cpu-mode.py", ["show"])
    d = _parse_or(stdout) or {}
    matched = d.get("matched_mode")
    note = d.get("note") or ""
    if "cpufreq subsystem unavailable" in note:
        sev = "informational"
        detail = "cpufreq absent (typical for VMs / containers)"
    elif matched is None and d.get("cpus"):
        sev = "attention"
        detail = "CPUs are running mixed governors — no single named mode matches"
    else:
        sev = "ok"
        detail = f"matched mode: {matched or 'none'}"
    return {
        "probe": "cpu_mode",
        "round": "R221",
        "vector": "Z-4",
        "rc": rc,
        "severity": sev,
        "detail": detail,
        "flagged_items": [],
    }


def probe_fs_usage(threshold_pct: int) -> dict[str, Any]:
    rc, stdout, _ = _run_probe(
        "fs-insights.py", ["usage", "--threshold-pct", str(threshold_pct)]
    )
    d = _parse_or(stdout) or {"partitions": []}
    flagged = [
        p for p in d.get("partitions", []) if p.get("use_pct", 0) >= threshold_pct
    ]
    sev = "attention" if flagged else "ok"
    detail = (
        f"{len(flagged)} partition(s) ≥ {threshold_pct}% (global "
        f"{d.get('global_use_pct', 0)}%)"
    )
    return {
        "probe": "fs_usage",
        "round": "R222",
        "vector": "Z-10",
        "rc": rc,
        "severity": sev,
        "detail": detail,
        "flagged_items": [
            {"id": p.get("mount"), "use_pct": p.get("use_pct")} for p in flagged
        ],
    }


def probe_raid() -> dict[str, Any]:
    rc, stdout, _ = _run_probe("raid-status.py", ["status"])
    d = _parse_or(stdout) or {"arrays": []}
    flagged = [a for a in d.get("arrays", []) if a.get("health") != "ok"]
    sev = (
        "attention" if flagged
        else ("informational" if not d.get("arrays") else "ok")
    )
    detail = (
        f"{len(flagged)} array(s) need attention"
        if flagged
        else (
            f"{d.get('count', 0)} array(s) healthy"
            if d.get("arrays")
            else "no md arrays present"
        )
    )
    return {
        "probe": "raid",
        "round": "R223",
        "vector": "Z-9",
        "rc": rc,
        "severity": sev,
        "detail": detail,
        "flagged_items": [
            {"id": a.get("name"), "health": a.get("health")} for a in flagged
        ],
    }


def probe_flex() -> dict[str, Any]:
    rc, stdout, _ = _run_probe("profile-flex.py", ["show"])
    d = _parse_or(stdout) or {}
    deltas = d.get("deltas") or []
    return {
        "probe": "flex",
        "round": "R224",
        "vector": "Z-3",
        "rc": 0,  # show is always informational
        "severity": "informational",
        "detail": (
            f"{len(deltas)} flex delta(s) active"
            if deltas
            else "profile at YAML baseline (no flex deltas)"
        ),
        "flagged_items": [
            {"id": d_.get("key"), "value": d_.get("value")} for d_ in deltas
        ],
    }


def probe_compat() -> dict[str, Any]:
    """Cross-system compatibility verdict (2026-07-20) — the compat
    registry's live-state check joins the health scan, so an
    incompatible box becomes a MONITORED condition: the R228 dispatcher
    picks up the ok→attention transition and notifies (incl. the
    notifykit bridge) instead of waiting for someone to open the ⚖ pane.
    Severity: force finding → attention · warn → attention ·
    suggest-only → informational · clean → ok · registry unavailable →
    informational (the scan never dies with the gate)."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "compat", Path(__file__).resolve().parents[1] / "operator" / "compat.py")
        compat = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compat)
        rep = compat.state_report()
    except Exception as e:  # noqa: BLE001 — degrade to informational
        rep = {"available": False, "error": str(e)}
    if not rep.get("available"):
        return {
            "probe": "compat", "round": "R226+", "vector": "Z-6",
            "rc": 0, "severity": "informational",
            "detail": f"compat registry unavailable — {rep.get('error', '?')}",
            "flagged_items": [],
        }
    findings = rep.get("findings") or []
    worst = ("force" if any(f["severity"] == "force" for f in findings)
             else "warn" if any(f["severity"] == "warn" for f in findings)
             else "suggest" if findings else None)
    sev = ("attention" if worst in ("force", "warn")
           else "informational" if worst == "suggest" else "ok")
    nsys = len(rep.get("current") or {})
    if not findings:
        detail = f"clean — no rules tripped ({nsys} readable system(s))"
    else:
        detail = (f"{len(findings)} finding(s), worst={worst}: "
                  + ", ".join(f"{f['rule_id']} ({f['severity']})"
                              for f in findings))
        plan = (rep.get("resolution") or {}).get("plan") or []
        if plan:
            detail += f" — {len(plan)}-step verified fix plan available (⚖ pane / compat check --current --resolve)"
    return {
        "probe": "compat", "round": "R226+", "vector": "Z-6",
        "rc": 0 if sev != "attention" else 1,
        "severity": sev,
        "detail": detail,
        "flagged_items": [
            {"id": f["rule_id"], "severity": f["severity"]} for f in findings
        ],
    }


def probe_avx_mode() -> dict[str, Any]:
    """M002 AVX execution-mode posture (2026-07-21). avx-mode is a live mode
    like cpu_mode — surface which execution path is active, and when the
    bit-machine (custom/hybrid) is engaged, whether the host actually carries
    the AVX-512 F floor. If not, the ZMM round kernels fall back to scalar:
    the operator believes they have hardware-speed bit-routing but do not — a
    grounded attention signal, the parallel to cpu_mode's mixed-governor
    mismatch. Severity: bit-machine engaged w/o AVX-512 → attention · engaged
    w/ AVX-512 → ok · math/scalar path → informational · unreadable →
    informational (the scan never dies with the mode tool)."""
    _, mstdout, _ = _run_probe("avx-mode.py", ["show"])
    m = _parse_or(mstdout) or {}
    active = m.get("active")
    base = {"probe": "avx_mode", "round": "R226+", "vector": "Z-4"}
    if not active:
        return {**base, "rc": 0, "severity": "informational",
                "detail": "avx-mode unreadable — execution posture unknown",
                "flagged_items": []}
    if active not in ("custom", "hybrid"):
        path = "stock AVX-512 math path" if active == "builtin" else "scalar baseline"
        return {**base, "rc": 0, "severity": "informational",
                "detail": f"{active} — {path}; the M002 bit-machine is not engaged",
                "flagged_items": []}
    # bit-machine engaged — is the AVX-512 floor actually present on this host?
    _, astdout, _ = _run_probe("avx512-advisor.py", ["probe"])
    supported = (_parse_or(astdout) or {}).get("avx512_supported")
    if supported is False:
        return {**base, "rc": 1, "severity": "attention",
                "detail": (f"{active}: bit-machine engaged but this host lacks the "
                           "AVX-512 F floor — the ZMM round kernels fall back to "
                           "scalar (no hardware-speed bit-routing). INSTEAD: "
                           "avx-mode set builtin/off, or run on an AVX-512 host."),
                "flagged_items": [{"id": "avx512f", "present": False}]}
    return {**base, "rc": 0,
            "severity": "ok" if supported else "informational",
            "detail": (f"{active}: bit-machine engaged"
                       + (" (AVX-512 F present)" if supported
                          else " (AVX-512 presence unknown)")),
            "flagged_items": []}


PROBES: dict[str, Any] = {
    "gpu": probe_gpu,
    "network": probe_network,
    "cpu_mode": probe_cpu_mode,
    "fs_usage": lambda: probe_fs_usage(80),
    "raid": probe_raid,
    "flex": probe_flex,
    "compat": probe_compat,
    "avx_mode": probe_avx_mode,
}


def run_all() -> dict[str, Any]:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = [fn() for fn in PROBES.values()]
    any_attention = any(r["severity"] == "attention" for r in rows)
    return {
        "round": "R226",
        "vector": "SDD-026 Z-6 (scan layer)",
        "started_at": started_at,
        "probes": rows,
        "summary": {
            "total":         len(rows),
            "ok":            sum(1 for r in rows if r["severity"] == "ok"),
            "attention":     sum(1 for r in rows if r["severity"] == "attention"),
            "informational": sum(1 for r in rows if r["severity"] == "informational"),
        },
        "needs_attention": any_attention,
    }


def render_text(rep: dict[str, Any]) -> str:
    lines = []
    lines.append("── R226 sovereign-os health scan (SDD-026 Z-6) ──")
    s = rep["summary"]
    lines.append(
        f"  probes: {s['total']}  ok={s['ok']}  "
        f"attention={s['attention']}  informational={s['informational']}"
    )
    lines.append(f"  started_at: {rep['started_at']}")
    lines.append("")
    glyph = {"ok": "✓", "attention": "⚠", "informational": "◌"}
    for p in rep["probes"]:
        g = glyph.get(p["severity"], "?")
        lines.append(
            f"  {g} {p['probe']:<9} [{p['vector']:<4} {p['round']}] "
            f"{p['severity']:<13} — {p['detail']}"
        )
        for item in p.get("flagged_items") or []:
            short = ", ".join(
                f"{k}={v}" for k, v in item.items() if v is not None and v != []
            )
            lines.append(f"      → {short}")
    if rep["needs_attention"]:
        lines.append("")
        lines.append(
            "⚠ At least one probe needs operator attention. Drill in via the "
            "per-vector verb (sovereign-osctl gpu-watch / network status / "
            "fs usage / raid status / etc.)."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="R226 (SDD-026 Z-6) composite health scan.")
    p.add_argument("--json", action="store_true", help="machine-readable JSON")
    p.add_argument(
        "--probe",
        choices=list(PROBES.keys()),
        help="run only this probe instead of all eight",
    )
    args = p.parse_args()
    if args.probe:
        single = PROBES[args.probe]()
        if args.json:
            print(json.dumps(single, indent=2))
        else:
            sys.stdout.write(render_text({
                "round": "R226",
                "vector": "SDD-026 Z-6 (scan layer)",
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "probes": [single],
                "summary": {
                    "total": 1,
                    "ok": 1 if single["severity"] == "ok" else 0,
                    "attention": 1 if single["severity"] == "attention" else 0,
                    "informational": 1 if single["severity"] == "informational" else 0,
                },
                "needs_attention": single["severity"] == "attention",
            }))
        return 1 if single["severity"] == "attention" else 0
    rep = run_all()
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        sys.stdout.write(render_text(rep))
    return 1 if rep["needs_attention"] else 0


if __name__ == "__main__":
    sys.exit(main())
