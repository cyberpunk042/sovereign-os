#!/usr/bin/env python3
"""scripts/insights/synthesize.py — R234 (SDD-026 Z-10 expansion).

Operator-named (verbatim, 2026-05-17 expansion): "to see all the logs
files and need for log rotate, track files system usage and for each
partitions and global and such. Offer insights."

R222 (fs-insights) ships the RAW probes — `fs usage` and `fs
log-audit` return data, not opinions. R234 synthesizes them into
operator-readable INSIGHTS: prioritized findings + concrete next-step
recommendations + recent log-rotation telemetry, all in one report.

Synthesis sources:

  fs-insights usage --json        partition usage + global percent
  fs-insights log-audit --json    per-log-file size + rotate flag
  Layer B .prom files             last log-rotate run + counts
                                  (sovereign_os_log_rotation_*)

Insight model:

  Each insight has:
    severity   critical / attention / informational
    title      one-liner
    detail     1-3 sentence elaboration
    action     copy-pasteable command the operator runs to address it

  Recommendations are PRIORITIZED — critical first, then attention,
  then informational. The CLI default prints the top 10; --all shows
  every finding; --json drives the dashboard's "Insights" tab.

Exit codes:
  0  insights rendered (regardless of severity — informational only)
  1  at least one CRITICAL insight is active (operator alert signal)
  2  usage error / sub-probe unavailable
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR",
        "/var/lib/node_exporter/textfile_collector",
    )
)

SEVERITY_RANK = {"critical": 0, "attention": 1, "informational": 2}


def _bytes_h(n: float | int | None) -> str:
    """Compact human-readable bytes (mirrors fs-insights fmt_bytes)."""
    if n is None:
        return "?"
    units = ["B", "K", "M", "G", "T", "P"]
    f = float(n)
    for u in units:
        if abs(f) < 1024.0 or u == units[-1]:
            return f"{f:.1f}{u}"
        f /= 1024.0
    return f"{f:.1f}P"


def _run_fs_insights(*args: str) -> dict[str, Any] | None:
    """Shell `scripts/hardware/fs-insights.py *args --json`. Returns dict."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / "fs-insights.py"
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    # rc 0 or 1 both yield valid JSON (1 = "flagged found"); other rcs are
    # genuine failure.
    if r.returncode not in (0, 1):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def _read_prom(name: str) -> dict[str, float]:
    """Parse a .prom file into {metric_name: value} (label-stripped)."""
    p = DEFAULT_METRICS_DIR / name
    out: dict[str, float] = {}
    if not p.exists():
        return out
    try:
        for line in p.read_text(errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            head, _, tail = line.rpartition(" ")
            head = head.split("{", 1)[0]  # strip labels
            try:
                out[head] = float(tail)
            except ValueError:
                continue
    except OSError:
        return {}
    return out


# --------------------------------------------------------- insight builders


def insight_fs_usage_partitions(usage: dict[str, Any]) -> list[dict[str, Any]]:
    """One insight per flagged partition + one global rollup if global high."""
    out: list[dict[str, Any]] = []
    for p in usage.get("partitions", []) or []:
        use_pct = p.get("use_pct")
        if use_pct is None:
            continue
        mp = p.get("mount") or p.get("mountpoint") or "?"
        total_h = _bytes_h(p.get("total_bytes"))
        used_h = _bytes_h(p.get("used_bytes"))
        if use_pct >= 90:
            out.append(
                {
                    "severity": "critical",
                    "title": f"partition {mp} at {use_pct}%",
                    "detail": (
                        f"Mountpoint {mp} is {use_pct}% full ({used_h}/{total_h}). "
                        "At this level logrotate, snapshots, or any package "
                        "install may fail. Free space NOW."
                    ),
                    "action": (
                        f"sovereign-osctl fs usage --json   # confirm; then prune"
                        f" /var/cache, /var/log, OR remove unused images"
                    ),
                    "source": "fs usage",
                }
            )
        elif use_pct >= 80:
            out.append(
                {
                    "severity": "attention",
                    "title": f"partition {mp} at {use_pct}%",
                    "detail": (
                        f"Mountpoint {mp} is {use_pct}% full ({used_h}/{total_h}) — "
                        "within the operator-set warning threshold. Schedule "
                        "cleanup before the partition crosses 90%."
                    ),
                    "action": "sovereign-osctl fs log-audit --json",
                    "source": "fs usage",
                }
            )
    global_pct = usage.get("global_use_pct")
    if isinstance(global_pct, (int, float)) and global_pct >= 75:
        out.append(
            {
                "severity": "attention" if global_pct < 85 else "critical",
                "title": f"global filesystem at {global_pct}%",
                "detail": (
                    f"Sum of all real partitions is {global_pct}% full. "
                    "Even if no single partition is critical, fleet-aggregate "
                    "headroom is shrinking."
                ),
                "action": "sovereign-osctl fs usage",
                "source": "fs usage (global)",
            }
        )
    return out


def insight_log_audit(audit: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    flagged = [f for f in (audit.get("files") or []) if f.get("flagged")]
    if not flagged:
        return out
    threshold = audit.get("threshold_bytes", 0)
    if len(flagged) >= 5:
        sev = "critical"
        title = f"{len(flagged)} log files unrotated (≥ {threshold} bytes)"
    else:
        sev = "attention"
        title = f"{len(flagged)} log file(s) over rotate threshold"
    examples = ", ".join(f["path"] for f in flagged[:3])
    out.append(
        {
            "severity": sev,
            "title": title,
            "detail": (
                f"{len(flagged)} log file(s) exceed the rotate threshold "
                f"of {threshold} bytes. Examples: {examples}. Add a "
                "logrotate.d entry or run rotate now."
            ),
            "action": (
                "sudo logrotate -f /etc/logrotate.conf  "
                "# or: sovereign-osctl maintenance log-rotate"
            ),
            "source": "fs log-audit",
        }
    )
    return out


def insight_log_rotation_health(prom: dict[str, float]) -> list[dict[str, Any]]:
    """Telemetry insight from the log-rotate hook's Layer B metrics."""
    out: list[dict[str, Any]] = []
    last_run = prom.get("sovereign_os_log_rotation_last_run_timestamp")
    rotated = prom.get("sovereign_os_log_rotation_files_rotated")
    purged = prom.get("sovereign_os_log_rotation_files_purged")
    if last_run is None:
        out.append(
            {
                "severity": "attention",
                "title": "log-rotate hook has never run",
                "detail": (
                    "No `sovereign_os_log_rotation_last_run_timestamp` "
                    "metric present. Enable the timer so log files don't "
                    "accumulate."
                ),
                "action": (
                    "sudo systemctl enable --now sovereign-log-rotate.timer"
                ),
                "source": "Layer B (log-rotation)",
            }
        )
    else:
        now = time.time()
        age_hours = (now - last_run) / 3600.0
        if age_hours > 48:
            out.append(
                {
                    "severity": "attention",
                    "title": f"log-rotate last ran {age_hours:.1f} hours ago",
                    "detail": (
                        f"Hook hasn't fired in {age_hours:.0f}+ hours. The "
                        "hourly timer may be masked or the unit may be "
                        "failing — inspect journal."
                    ),
                    "action": (
                        "systemctl status sovereign-log-rotate.timer "
                        "sovereign-log-rotate.service"
                    ),
                    "source": "Layer B (log-rotation)",
                }
            )
        else:
            # Informational — last run + counts. Tells operator the
            # hook IS healthy.
            out.append(
                {
                    "severity": "informational",
                    "title": (
                        f"log-rotate healthy "
                        f"(rotated={int(rotated or 0)}, purged={int(purged or 0)}, "
                        f"{age_hours:.1f}h ago)"
                    ),
                    "detail": "Most recent log-rotate run completed within 48 h.",
                    "action": "(no action)",
                    "source": "Layer B (log-rotation)",
                }
            )
    return out


# --------------------------------------------------------- entry


def synthesize(roots: list[str] | None = None, threshold_bytes: int = 104857600) -> dict[str, Any]:
    """Build the insights report."""
    usage = _run_fs_insights("usage") or {}
    audit_args: list[str] = ["log-audit", "--threshold-bytes", str(threshold_bytes)]
    if roots:
        for r in roots:
            audit_args += ["--root", r]
    audit = _run_fs_insights(*audit_args) or {}
    prom = _read_prom("sovereign-os-log-rotation.prom")

    insights: list[dict[str, Any]] = []
    insights.extend(insight_fs_usage_partitions(usage))
    insights.extend(insight_log_audit(audit))
    insights.extend(insight_log_rotation_health(prom))
    # Sort: critical first, then attention, then informational; stable within.
    insights.sort(key=lambda i: SEVERITY_RANK.get(i["severity"], 9))

    counts = {
        "critical": sum(1 for i in insights if i["severity"] == "critical"),
        "attention": sum(1 for i in insights if i["severity"] == "attention"),
        "informational": sum(1 for i in insights if i["severity"] == "informational"),
        "total": len(insights),
    }
    return {
        "round": "R234",
        "vector": "SDD-026 Z-10 (insights synthesizer)",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": {
            "fs_usage_partitions": len(usage.get("partitions") or []),
            "log_audit_files": len(audit.get("files") or []),
            "layer_b_log_rotation_present": bool(prom),
        },
        "counts": counts,
        "insights": insights,
        "needs_attention": counts["critical"] > 0 or counts["attention"] > 0,
    }


def render_human(report: dict[str, Any], limit: int) -> str:
    out: list[str] = []
    out.append(f"── R234 sovereign-os insights (SDD-026 Z-10) ──")
    out.append(f"  generated:    {report['generated_at']}")
    c = report["counts"]
    out.append(
        f"  totals:       critical={c['critical']}  attention={c['attention']}  "
        f"informational={c['informational']}  (total {c['total']})"
    )
    s = report["sources"]
    out.append(
        f"  sources:      partitions={s['fs_usage_partitions']}  "
        f"log_files={s['log_audit_files']}  "
        f"layer_b={'yes' if s['layer_b_log_rotation_present'] else 'no'}"
    )
    out.append("")
    insights = report["insights"][:limit]
    if not insights:
        out.append("  (no insights — system is healthy)")
        return "\n".join(out) + "\n"
    glyph = {"critical": "⛔", "attention": "⚠ ", "informational": "·"}
    for i in insights:
        g = glyph.get(i["severity"], "?")
        out.append(f"  {g} [{i['severity']:13s}] {i['title']}")
        for line in (i["detail"] or "").split("\n"):
            out.append(f"      {line}")
        out.append(f"      action: {i['action']}")
        out.append(f"      source: {i['source']}")
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="synthesize.py",
        description="R234 (SDD-026 Z-10) — fs + log + telemetry insights synthesizer.",
    )
    p.add_argument(
        "--threshold-bytes",
        type=int,
        default=104857600,  # 100 MiB
        help="log file size threshold (default 100 MiB)",
    )
    p.add_argument(
        "--root",
        action="append",
        default=None,
        help="log root to scan (repeatable; default: /var/log)",
    )
    p.add_argument("--limit", type=int, default=10, help="max rows in human render")
    p.add_argument(
        "--all",
        action="store_true",
        help="show every insight (overrides --limit)",
    )
    p.add_argument("--json", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    report = synthesize(roots=args.root, threshold_bytes=args.threshold_bytes)
    rc = 1 if report["counts"]["critical"] > 0 else 0
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        limit = 10**9 if args.all else args.limit
        print(render_human(report, limit), end="")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
