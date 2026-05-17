#!/usr/bin/env python3
"""scripts/network/perf-baseline.py — R276 (E3.M6).

Operator-named (verbatim, 2026-05-17 mandate): "networks and in and
out".

R220 ships up/down probes. R263+R268 ship per-service deep posture.
R276 closes E3.M6: time-series performance baseline + drift detection.

Probes (read-only, best-effort):
  ping <target> -c N      egress latency + packet loss
  dig @<resolver>         DNS resolve latency
  curl <url> -w timing    TLS handshake + first-byte time

Baseline is stored as JSON in /var/lib/sovereign-os/network-baseline.json
(env: SOVEREIGN_OS_NETWORK_BASELINE). Each `record` invocation
captures the current measurement; each `drift` invocation compares
recent vs baseline and surfaces deltas exceeding operator thresholds.

CLI:
  perf-baseline.py probe [--targets t1,t2,...] [--json]
      one-shot measurement; doesn't update baseline
  perf-baseline.py record [--targets ...] [--json]
      probe + append to history file
  perf-baseline.py drift [--threshold-pct N] [--json]
      compare LATEST sample vs the recorded BASELINE (first sample);
      rc=1 when ≥1 target exceeds threshold

Exit codes:
  0  no drift OR informational
  1  ≥1 target drifted beyond threshold
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = Path("/var/lib/sovereign-os/network-baseline.json")

DEFAULT_TARGETS = [
    {"name": "cloudflare-1.1.1.1", "kind": "ping", "target": "1.1.1.1"},
    {"name": "quad9-9.9.9.9",      "kind": "ping", "target": "9.9.9.9"},
    {"name": "dns-cloudflare",     "kind": "dns",  "target": "1.1.1.1", "host": "example.com"},
    {"name": "https-cloudflare",   "kind": "https", "target": "https://1.1.1.1"},
]


def resolve_state_path() -> Path:
    env = os.environ.get("SOVEREIGN_OS_NETWORK_BASELINE")
    if env:
        return Path(env)
    return DEFAULT_STATE


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "baselines": {}, "samples": []}
    try:
        with path.open() as fh:
            d = json.load(fh)
        d.setdefault("baselines", {})
        d.setdefault("samples", [])
        return d
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "baselines": {}, "samples": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as fh:
        json.dump(state, fh, indent=2)
    tmp.replace(path)


# --------------------------------------------------------------- probes


def probe_ping(target: str, count: int = 4) -> dict[str, Any]:
    if not shutil.which("ping"):
        return {"ok": False, "error": "ping binary missing"}
    try:
        r = subprocess.run(
            ["ping", "-c", str(count), "-W", "2", target],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "error": str(e)}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[:200], "loss_pct": 100.0}
    # Parse: 'rtt min/avg/max/mdev = 1.234/2.345/3.456/0.123 ms'
    avg_ms = None
    loss_pct = None
    m = re.search(r"min/avg/max/[^=]+=\s*([\d.]+)/([\d.]+)/([\d.]+)", r.stdout)
    if m:
        avg_ms = float(m.group(2))
    m2 = re.search(r"(\d+)% packet loss", r.stdout)
    if m2:
        loss_pct = float(m2.group(1))
    return {"ok": True, "avg_ms": avg_ms, "loss_pct": loss_pct or 0.0}


def probe_dns(resolver: str, host: str) -> dict[str, Any]:
    if not shutil.which("dig"):
        return {"ok": False, "error": "dig binary missing"}
    try:
        r = subprocess.run(
            ["dig", "@" + resolver, "+stats", "+time=3", "+tries=1", host],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "error": str(e)}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[:200]}
    m = re.search(r";; Query time:\s*(\d+)\s*msec", r.stdout)
    return {"ok": True, "avg_ms": float(m.group(1)) if m else None, "loss_pct": 0.0}


def probe_https(url: str) -> dict[str, Any]:
    if not shutil.which("curl"):
        return {"ok": False, "error": "curl binary missing"}
    fmt = ("connect_ms=%{time_connect}\n"
           "ssl_ms=%{time_appconnect}\n"
           "ttfb_ms=%{time_starttransfer}\n"
           "total_ms=%{time_total}\n"
           "http=%{http_code}\n")
    try:
        r = subprocess.run(
            ["curl", "-fsS", "-o", "/dev/null", "--max-time", "5",
             "-w", fmt, url],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "error": str(e)}
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout)[:200]}
    out: dict[str, Any] = {"ok": True}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            try:
                if k.endswith("_ms"):
                    out[k] = float(v) * 1000.0  # curl emits seconds
                else:
                    out[k] = v.strip()
            except ValueError:
                pass
    # The 'avg_ms' shorthand for downstream uniformity.
    out["avg_ms"] = out.get("ttfb_ms")
    out["loss_pct"] = 0.0
    return out


def measure_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for t in targets:
        kind = t.get("kind")
        if kind == "ping":
            res = probe_ping(t["target"])
        elif kind == "dns":
            res = probe_dns(t["target"], t.get("host", "example.com"))
        elif kind == "https":
            res = probe_https(t["target"])
        else:
            res = {"ok": False, "error": f"unknown kind {kind!r}"}
        rows.append({
            "name": t["name"],
            "kind": kind,
            "target": t["target"],
            "measurement": res,
        })
    return rows


# --------------------------------------------------------------- verbs


def cmd_probe(args: argparse.Namespace) -> int:
    targets = parse_targets(args.targets) or DEFAULT_TARGETS
    rows = measure_targets(targets)
    out = {
        "round": "R276",
        "vector": "E3.M6 (network-perf-baseline-probe)",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "targets": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R276 sovereign-os network-perf-baseline probe (E3.M6) ──")
    for r in rows:
        m = r["measurement"]
        if m.get("ok"):
            print(f"  ✓ {r['name']:<24} avg_ms={m.get('avg_ms')}  loss%={m.get('loss_pct', 0)}")
        else:
            print(f"  ✗ {r['name']:<24} ERROR: {m.get('error', '?')}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    state_path = resolve_state_path()
    state = load_state(state_path)
    targets = parse_targets(args.targets) or DEFAULT_TARGETS
    measured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = measure_targets(targets)
    sample = {"measured_at": measured_at, "targets": rows}
    state["samples"].append(sample)
    # First sample for each target becomes the BASELINE.
    for r in rows:
        if r["name"] not in state["baselines"] and r["measurement"].get("ok"):
            state["baselines"][r["name"]] = {
                "measured_at": measured_at,
                "avg_ms": r["measurement"].get("avg_ms"),
                "loss_pct": r["measurement"].get("loss_pct", 0.0),
            }
    save_state(state_path, state)
    out = {
        "round": "R276",
        "vector": "E3.M6 (record)",
        "state_path": str(state_path),
        "measured_at": measured_at,
        "sample_count": len(state["samples"]),
        "baseline_count": len(state["baselines"]),
        "targets": rows,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R276 network-perf-baseline record ──")
        print(f"  state:    {state_path}")
        print(f"  samples:  {len(state['samples'])}  baselines: {len(state['baselines'])}")
        for r in rows:
            print(f"  • {r['name']:<24} {r['measurement']}")
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    state_path = resolve_state_path()
    state = load_state(state_path)
    if not state["samples"]:
        out = {
            "round": "R276",
            "vector": "E3.M6 (drift)",
            "verdict": "no-data",
            "message": "no samples recorded yet — run `record` first",
            "drift_count": 0,
            "drifts": [],
        }
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(out["message"])
        return 0

    latest = state["samples"][-1]
    threshold_pct = args.threshold_pct
    drifts: list[dict[str, Any]] = []
    for r in latest["targets"]:
        name = r["name"]
        m = r["measurement"]
        baseline = state["baselines"].get(name)
        if not baseline or not m.get("ok") or m.get("avg_ms") is None:
            continue
        baseline_avg = baseline.get("avg_ms")
        if baseline_avg is None or baseline_avg <= 0:
            continue
        delta_pct = (m["avg_ms"] - baseline_avg) / baseline_avg * 100.0
        if abs(delta_pct) >= threshold_pct:
            drifts.append({
                "name": name,
                "baseline_avg_ms": baseline_avg,
                "latest_avg_ms": m["avg_ms"],
                "delta_ms": round(m["avg_ms"] - baseline_avg, 2),
                "delta_pct": round(delta_pct, 1),
                "direction": "slower" if delta_pct > 0 else "faster",
            })
    out = {
        "round": "R276",
        "vector": "E3.M6 (drift)",
        "verdict": "drifting" if drifts else "stable",
        "threshold_pct": threshold_pct,
        "sample_count": len(state["samples"]),
        "drift_count": len(drifts),
        "drifts": drifts,
        "latest_measured_at": latest["measured_at"],
    }
    rc = 1 if drifts else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R276 network-perf-baseline drift (E3.M6) ──")
    print(f"  threshold: ±{threshold_pct}%   samples: {len(state['samples'])}   drifts: {len(drifts)}")
    for d in drifts:
        print(f"\n  ⚠ {d['name']}: baseline {d['baseline_avg_ms']} ms → latest {d['latest_avg_ms']} ms  "
              f"({d['direction']} by {d['delta_pct']}% / {d['delta_ms']} ms)")
    if not drifts:
        print("  (no drift exceeds threshold)")
    return rc


# --------------------------------------------------------------- helpers


def parse_targets(spec: str | None) -> list[dict[str, Any]] | None:
    """`--targets ping:1.1.1.1,dns:9.9.9.9:example.com` → target list."""
    if not spec:
        return None
    out: list[dict[str, Any]] = []
    for raw in spec.split(","):
        parts = raw.strip().split(":", 2)
        if not parts:
            continue
        kind = parts[0]
        if kind == "ping" and len(parts) >= 2:
            out.append({"name": f"{kind}-{parts[1]}", "kind": kind, "target": parts[1]})
        elif kind == "dns" and len(parts) >= 3:
            out.append({"name": f"{kind}-{parts[1]}", "kind": kind, "target": parts[1], "host": parts[2]})
        elif kind == "https" and len(parts) >= 2:
            url = ":".join(parts[1:])
            out.append({"name": f"https-{url}", "kind": "https", "target": url})
    return out or None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="perf-baseline.py",
        description="R276 (E3.M6) — network performance baseline + drift detection.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    pp = sub.add_parser("probe", help="one-shot measurement (doesn't persist)")
    pp.add_argument("--targets")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_probe)
    pr = sub.add_parser("record", help="probe + persist to state file")
    pr.add_argument("--targets")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_record)
    pd = sub.add_parser("drift", help="compare latest sample vs baseline")
    pd.add_argument("--threshold-pct", type=float, default=25.0)
    pd.add_argument("--json", action="store_true")
    pd.set_defaults(func=cmd_drift)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
