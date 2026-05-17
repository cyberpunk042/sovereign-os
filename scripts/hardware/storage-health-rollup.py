#!/usr/bin/env python3
"""scripts/hardware/storage-health-rollup.py — R298 (E2.M12).

Operator-named (§1b mandate row, verbatim): "logs, log rotate, system
usage, partitions and global and such. insights". Closes E2.M12.

ONE operator-pull "is my storage layer healthy?" report. Composes the
4 existing probes (R222 logs, R223 RAID, R228 fs / partitions, R234
insights) into a single combined verdict + per-axis breakdown. Each
axis surfaces:

  - log-rotate posture     — /etc/logrotate.d/ population, last-run
                              timestamp, journal Storage= setting
  - RAID state             — /proc/mdstat parse (degraded? syncing?)
  - partition free space   — operator-pinned warn/critical thresholds
  - journal size           — journalctl --disk-usage vs SystemMaxUse=

Combined verdict ∈ {healthy, watch, degraded}. Operator-pull "act-NOW"
(degraded) lights up the dashboard storage card.

CLI:
  storage-health-rollup.py status   [--config P] [--json|--human]
  storage-health-rollup.py advisory [--config P] [--json|--human]
  storage-health-rollup.py inputs   [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/storage-health.toml

Exit codes:
  0  healthy
  1  watch
  2  degraded
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

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R298"
SDD_VECTOR = "E2.M12"


DEFAULTS = {
    # Partition-free-space thresholds (percent of capacity).
    "partition_free_warn_pct": 15,
    "partition_free_critical_pct": 5,
    # Journal-disk-usage thresholds (percent of SystemMaxUse=).
    "journal_warn_pct": 80,
    "journal_critical_pct": 95,
    # Logrotate freshness threshold (days since last run).
    "logrotate_warn_days": 14,
    "logrotate_critical_days": 30,
    # Operator-pinned partitions to watch. Empty list = walk all
    # mounted filesystems (excluding pseudo-fs like /proc, /sys).
    "watch_partitions": [],
    # Pseudo-filesystems to always skip.
    "skip_fstypes": ["tmpfs", "devtmpfs", "proc", "sysfs", "cgroup",
                     "cgroup2", "pstore", "bpf", "tracefs", "debugfs",
                     "securityfs", "fuse.gvfs-fuse-daemon", "fusectl",
                     "ramfs", "rpc_pipefs", "configfs", "mqueue",
                     "hugetlbfs", "nsfs", "binfmt_misc",
                     "fuse.snapfuse", "overlay", "squashfs",
                     "autofs", "fusectl"],
}


def _which(name: str) -> str | None:
    return shutil.which(name)


# ── Axis: log-rotate posture ────────────────────────────────────────
def probe_logrotate() -> dict[str, Any]:
    logrotate_d = Path("/etc/logrotate.d")
    cfg_count = 0
    if logrotate_d.is_dir():
        cfg_count = sum(1 for _ in logrotate_d.iterdir())
    state = Path("/var/lib/logrotate/status")
    if not state.is_file():
        state = Path("/var/lib/logrotate.status")  # alternate Debian path
    last_run_days = None
    if state.is_file():
        try:
            import time
            mtime = state.stat().st_mtime
            last_run_days = int((time.time() - mtime) // 86400)
        except OSError:
            pass
    journal_storage = None
    journald_conf = Path("/etc/systemd/journald.conf")
    if journald_conf.is_file():
        try:
            for line in journald_conf.read_text().splitlines():
                line = line.strip()
                if line.startswith("Storage=") and not line.startswith("#"):
                    journal_storage = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    return {
        "logrotate_configs_count": cfg_count,
        "last_run_days_ago": last_run_days,
        "journal_storage_setting": journal_storage,
        "state_file_present": state.is_file(),
    }


def verdict_logrotate(p: dict, cfg: dict) -> dict:
    days = p["last_run_days_ago"]
    if days is None:
        return {"verdict": "unknown",
                "detail": "logrotate state file not found — "
                          "is logrotate installed?"}
    if days >= cfg["logrotate_critical_days"]:
        return {"verdict": "critical",
                "detail": f"logrotate last ran {days} days ago "
                          f"(≥ critical {cfg['logrotate_critical_days']})"}
    if days >= cfg["logrotate_warn_days"]:
        return {"verdict": "warn",
                "detail": f"logrotate last ran {days} days ago "
                          f"(≥ warn {cfg['logrotate_warn_days']})"}
    return {"verdict": "ok",
            "detail": f"logrotate fresh ({days} days ago, "
                      f"{p['logrotate_configs_count']} configs)"}


# ── Axis: RAID ──────────────────────────────────────────────────────
def probe_raid() -> dict[str, Any]:
    mdstat = Path("/proc/mdstat")
    if not mdstat.is_file():
        return {"present": False, "arrays": []}
    try:
        body = mdstat.read_text()
    except OSError as e:
        return {"present": False, "error": str(e), "arrays": []}
    arrays: list[dict] = []
    current = None
    for line in body.splitlines():
        if line.startswith("md"):
            if current:
                arrays.append(current)
            parts = line.split()
            current = {
                "name": parts[0],
                "state": "active" if "active" in parts else "unknown",
                "level": next((p for p in parts if p.startswith("raid")), None),
                "raw": line,
                "degraded": False,
                "recovery": False,
            }
        elif current is not None:
            if "_" in line and "[" in line:  # e.g. [UUU_] = degraded
                current["degraded"] = "_" in line.split("[")[-1].split("]")[0]
                current["status_line"] = line.strip()
            if "recovery" in line or "resync" in line:
                current["recovery"] = True
                current["recovery_line"] = line.strip()
    if current:
        arrays.append(current)
    return {"present": True, "arrays": arrays}


def verdict_raid(p: dict) -> dict:
    if not p["present"]:
        return {"verdict": "no-raid",
                "detail": "no software RAID arrays on this host"}
    arrays = p["arrays"]
    if not arrays:
        return {"verdict": "no-raid",
                "detail": "/proc/mdstat present but no arrays parsed"}
    degraded = [a for a in arrays if a.get("degraded")]
    recovering = [a for a in arrays if a.get("recovery")]
    if degraded and not recovering:
        return {"verdict": "critical",
                "detail": f"{len(degraded)} array(s) DEGRADED with no "
                          f"recovery in progress — operator must "
                          f"intervene NOW"}
    if degraded and recovering:
        return {"verdict": "warn",
                "detail": f"{len(degraded)} array(s) recovering — "
                          f"monitor; rebuild in progress"}
    return {"verdict": "ok",
            "detail": f"{len(arrays)} array(s) healthy"}


# ── Axis: partitions ────────────────────────────────────────────────
def probe_partitions(cfg: dict) -> list[dict[str, Any]]:
    out: list[dict] = []
    df_bin = _which("df")
    if df_bin is None:
        return out
    try:
        r = subprocess.run(
            [df_bin, "-P", "-T"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return out
    skip = set(cfg["skip_fstypes"])
    watch = set(cfg["watch_partitions"])
    for line in r.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 7:
            continue
        device, fstype, total, used, free, used_pct_s, mount = parts[:7]
        if fstype in skip:
            continue
        if watch and mount not in watch:
            continue
        try:
            used_pct = int(used_pct_s.rstrip("%"))
        except ValueError:
            continue
        out.append({
            "device": device,
            "mount": mount,
            "fstype": fstype,
            "total_kb": int(total) if total.isdigit() else None,
            "used_kb":  int(used) if used.isdigit() else None,
            "free_kb":  int(free) if free.isdigit() else None,
            "used_pct": used_pct,
            "free_pct": 100 - used_pct,
        })
    return out


def verdict_partitions(parts: list[dict], cfg: dict) -> dict:
    warn = cfg["partition_free_warn_pct"]
    crit = cfg["partition_free_critical_pct"]
    if not parts:
        return {"verdict": "unknown",
                "detail": "no partitions probed (df missing or filtered)"}
    critical = [p for p in parts if p["free_pct"] <= crit]
    watching = [p for p in parts if crit < p["free_pct"] <= warn]
    if critical:
        names = ", ".join(f"{p['mount']} ({p['free_pct']}%)" for p in critical)
        return {"verdict": "critical",
                "detail": f"{len(critical)} partition(s) ≤ {crit}% free: {names}"}
    if watching:
        names = ", ".join(f"{p['mount']} ({p['free_pct']}%)" for p in watching)
        return {"verdict": "warn",
                "detail": f"{len(watching)} partition(s) ≤ {warn}% free: {names}"}
    return {"verdict": "ok",
            "detail": f"{len(parts)} partition(s) all > {warn}% free"}


# ── Axis: journal ───────────────────────────────────────────────────
def probe_journal() -> dict[str, Any]:
    out: dict[str, Any] = {
        "disk_usage_bytes": None,
        "system_max_use_setting": None,
    }
    if _which("journalctl"):
        try:
            r = subprocess.run(
                ["journalctl", "--disk-usage"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if r.returncode == 0:
                # "Archived and active journals take up 123.4M in the file system."
                line = r.stdout.strip()
                # crude byte parse — look for the last unit.
                import re
                m = re.search(r"([\d.]+)\s*([KMGT])", line)
                if m:
                    val = float(m.group(1))
                    mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[m.group(2)]
                    out["disk_usage_bytes"] = int(val * mult)
                    out["disk_usage_human"] = line
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Parse SystemMaxUse= from /etc/systemd/journald.conf.
    journald_conf = Path("/etc/systemd/journald.conf")
    if journald_conf.is_file():
        try:
            for line in journald_conf.read_text().splitlines():
                line = line.strip()
                if line.startswith("SystemMaxUse=") and not line.startswith("#"):
                    out["system_max_use_setting"] = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    return out


def verdict_journal(p: dict, cfg: dict) -> dict:
    if p["disk_usage_bytes"] is None:
        return {"verdict": "unknown",
                "detail": "journalctl --disk-usage unavailable"}
    if p["system_max_use_setting"] is None:
        return {"verdict": "ok",
                "detail": f"journal currently {p.get('disk_usage_human', '?')}, "
                          f"no SystemMaxUse= cap → grows unbounded "
                          f"unless ad-hoc vacuumed"}
    # Parse SystemMaxUse= (e.g. "1G", "500M").
    import re
    m = re.match(r"([\d.]+)\s*([KMGT])", p["system_max_use_setting"])
    if not m:
        return {"verdict": "unknown",
                "detail": f"can't parse SystemMaxUse={p['system_max_use_setting']!r}"}
    cap_val = float(m.group(1))
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[m.group(2)]
    cap = int(cap_val * mult)
    pct = int((p["disk_usage_bytes"] / cap) * 100) if cap > 0 else 0
    if pct >= cfg["journal_critical_pct"]:
        return {"verdict": "critical",
                "detail": f"journal at {pct}% of SystemMaxUse= "
                          f"({p['system_max_use_setting']}) — vacuum NOW"}
    if pct >= cfg["journal_warn_pct"]:
        return {"verdict": "warn",
                "detail": f"journal at {pct}% of SystemMaxUse="}
    return {"verdict": "ok",
            "detail": f"journal at {pct}% of SystemMaxUse= "
                      f"({p['system_max_use_setting']})"}


# ── Combined verdict ────────────────────────────────────────────────
def combined_verdict(axes: dict[str, dict]) -> dict[str, Any]:
    weights = {"critical": 2, "warn": 1, "ok": 0,
               "no-raid": 0, "unknown": 1}
    severity = max(weights.get(v["verdict"], 1) for v in axes.values())
    if severity >= 2:
        return {"verdict": "degraded", "rc": 2,
                "message": "≥1 axis is critical — operator must intervene now."}
    if severity >= 1:
        return {"verdict": "watch", "rc": 1,
                "message": "≥1 axis is warning — operator should investigate."}
    return {"verdict": "healthy", "rc": 0,
            "message": "all storage-health axes ok."}


# ── Build report ────────────────────────────────────────────────────
def build_report(overlay_path: Path | None) -> dict[str, Any]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("storage-health", DEFAULTS,
                                    explicit_path=overlay_path)
        cfg.update({k: v for k, v in loaded.items() if not k.startswith("_")})
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]

    lr = probe_logrotate()
    raid = probe_raid()
    parts = probe_partitions(cfg)
    journal = probe_journal()

    axes = {
        "logrotate": verdict_logrotate(lr, cfg),
        "raid": verdict_raid(raid),
        "partitions": verdict_partitions(parts, cfg),
        "journal": verdict_journal(journal, cfg),
    }
    comb = combined_verdict(axes)
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "config": cfg,
        "axes": axes,
        "inputs": {
            "logrotate": lr,
            "raid": raid,
            "partitions": parts,
            "journal": journal,
        },
        "verdict": comb["verdict"],
        "rc": comb["rc"],
        "message": comb["message"],
        "overlay": meta,
    }


def render_human(doc: dict) -> str:
    lines = ["── R298 sovereign-os storage health rollup (E2.M12) ──"]
    lines.append(f"  verdict:    {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  message:    {doc['message']}")
    lines.append("")
    for name, axis in doc["axes"].items():
        mark = {"ok": "OK", "warn": "??", "critical": "!!",
                "no-raid": "--", "unknown": "??"}.get(axis["verdict"], "??")
        lines.append(f"  [{mark}] {name:11s}  {axis['verdict']}")
        lines.append(f"            {axis['detail']}")
    return "\n".join(lines) + "\n"


# ── Main ────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="storage-health-rollup.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "advisory", "inputs"):
        sp = sub.add_parser(verb)
        sp.add_argument("--config", type=Path)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")
    args = p.parse_args(argv)
    doc = build_report(args.config)

    if args.verb == "inputs":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "config": doc["config"],
                "inputs": doc["inputs"],
                "overlay": doc["overlay"],
            }, indent=2))
        else:
            print(json.dumps(doc["inputs"], indent=2))
        return 0

    if args.verb == "advisory":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": doc["verdict"],
                "message": doc["message"],
                "rc": doc["rc"],
                "axes_summary": {k: v["verdict"] for k, v in doc["axes"].items()},
            }, indent=2))
        else:
            print(f"verdict: {doc['verdict']}")
            print(f"  {doc['message']}")
        return doc["rc"]

    # status
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
