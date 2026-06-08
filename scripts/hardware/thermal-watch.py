#!/usr/bin/env python3
"""sovereign-os thermal-watch (R172) — periodic thermal threshold check.

Reads /sys/class/hwmon + nvidia-smi GPU temps, classifies each
sensor against configurable thresholds, emits:

  1. Layer B textfile-collector metrics:
       sovereign_os_thermal_celsius{sensor="..."} <C>
       sovereign_os_thermal_severity{sensor="...",level="critical"} 0|1
       sovereign_os_thermal_breach_total <count of sensors at WARN+CRITICAL>

  2. journal log lines tagged "thermal-watch":
       INFO  for normal readings (only at startup / threshold-change),
       WARN  for sensors crossing the warn threshold,
       ALERT for sensors crossing the critical threshold.

  3. JSONL incident events appended to a file (path configurable)
     when CRITICAL is crossed. Picked up by the daemon's eventstream
     collector and surfaced to the bus as OCSF detection findings.

The mirror selfdef counterpart is SD-R17 (selfdef-hardware ThermalReading
+ `selfdefctl hardware thermals`). This sovereign-os script adds the
THRESHOLD + ALERT layer on top — sovereign-os owns "is this concerning?"
because thresholds depend on the profile (a 9900X under SAIN-01
sustained inference workload tolerates higher Tctl than a developer
laptop running idle).

Thresholds default per profile (selectable via --profile):

  sain-01:          warn=85, critical=95   (sustained inference)
  developer:        warn=80, critical=90
  headless:         warn=75, critical=85   (server class)
  old-workstation:  warn=80, critical=90
  minimal:          warn=80, critical=90   (VM baseline)

Per-sensor overrides allowed via --override 'k10temp/Tctl=warn:80,crit:92'.

CLI:
  thermal-watch.py                # current profile / once
  thermal-watch.py --json         # machine-readable
  thermal-watch.py --once         # explicit single-pass (default behavior)
  thermal-watch.py --emit-metrics # write the .prom textfile (timer mode)
  thermal-watch.py --profile sain-01

Exit codes:
  0  normal (no sensor at WARN or CRITICAL)
  1  at least one sensor at WARN
  2  at least one sensor at CRITICAL
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_HWMON_DIR = Path("/sys/class/hwmon")
DEFAULT_METRICS_PATH = Path("/var/lib/node_exporter/textfile_collector/sovereign-os-thermal-watch.prom")
DEFAULT_EVENTS_JSONL = Path("/var/lib/sovereign-os/events/thermal.jsonl")

# Per-profile defaults: (warn_celsius, critical_celsius).
PROFILE_THRESHOLDS: dict[str, tuple[int, int]] = {
    "sain-01":          (85, 95),
    "developer":        (80, 90),
    "headless":         (75, 85),
    "old-workstation":  (80, 90),
    "minimal":          (80, 90),
}

# NVIDIA GPUs run hotter under load (junction temps in the 80s are
# normal on GeForce parts). Always use these GPU-specific thresholds
# regardless of profile.
GPU_THRESHOLDS: tuple[int, int] = (85, 95)


@dataclass
class Reading:
    source: str
    celsius: int
    severity: str  # "ok" | "warn" | "critical"
    warn_threshold: int
    critical_threshold: int


def read_hwmon(hwmon_dir: Path) -> list[tuple[str, int]]:
    """Return [(sensor_name, celsius), ...] from /sys/class/hwmon/."""
    if not hwmon_dir.exists() or not hwmon_dir.is_dir():
        return []
    out: list[tuple[str, int]] = []
    devs = []
    for entry in hwmon_dir.iterdir():
        if not entry.name.startswith("hwmon"):
            continue
        try:
            idx = int(entry.name[len("hwmon") :])
        except ValueError:
            continue
        devs.append((idx, entry))
    devs.sort(key=lambda x: x[0])
    for _, dev in devs:
        name_path = dev / "name"
        try:
            name = name_path.read_text().strip()
        except OSError:
            continue
        if not name:
            continue
        temps: list[tuple[int, int, str | None]] = []
        for temp_file in dev.glob("temp*_input"):
            stem = temp_file.name.removesuffix("_input")
            if not stem.startswith("temp"):
                continue
            try:
                idx = int(stem[len("temp") :])
            except ValueError:
                continue
            try:
                millideg = int(temp_file.read_text().strip())
            except (OSError, ValueError):
                continue
            celsius = (millideg + (500 if millideg >= 0 else -500)) // 1000
            label_path = dev / f"temp{idx}_label"
            label: str | None = None
            try:
                lab = label_path.read_text().strip()
                label = lab or None
            except OSError:
                label = None
            temps.append((idx, celsius, label))
        temps.sort(key=lambda x: x[0])
        for idx, celsius, label in temps:
            tag = f"{name}/{label}" if label else f"{name}/temp{idx}"
            out.append((tag, celsius))
    return out


def read_nvidia_smi() -> list[tuple[str, int]]:
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0 or not r.stdout:
        return []
    out: list[tuple[str, int]] = []
    for line in r.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        try:
            idx = int(parts[0])
            celsius = int(parts[1])
        except ValueError:
            continue
        out.append((f"nvidia-gpu-{idx}", celsius))
    return out


def classify(source: str, celsius: int, warn: int, critical: int) -> Reading:
    if celsius >= critical:
        sev = "critical"
    elif celsius >= warn:
        sev = "warn"
    else:
        sev = "ok"
    return Reading(
        source=source,
        celsius=celsius,
        severity=sev,
        warn_threshold=warn,
        critical_threshold=critical,
    )


def write_atomic(path: Path, body: str) -> None:
    """node_exporter textfile collector contract: tempfile + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, prefix=f"{path.name}."
    ) as tf:
        tf.write(body)
        tmp_path = Path(tf.name)
    os.replace(tmp_path, path)


def render_metrics(readings: list[Reading]) -> str:
    lines: list[str] = []
    lines.append(
        "# HELP sovereign_os_thermal_celsius Per-sensor temperature in degrees Celsius (R172)"
    )
    lines.append("# TYPE sovereign_os_thermal_celsius gauge")
    for r in readings:
        safe = r.source.replace('"', '\\"')
        lines.append(f'sovereign_os_thermal_celsius{{sensor="{safe}"}} {r.celsius}')
    lines.append(
        "# HELP sovereign_os_thermal_severity 1 if sensor at this severity level, 0 otherwise"
    )
    lines.append("# TYPE sovereign_os_thermal_severity gauge")
    for r in readings:
        safe = r.source.replace('"', '\\"')
        for lvl in ("ok", "warn", "critical"):
            v = 1 if r.severity == lvl else 0
            lines.append(
                f'sovereign_os_thermal_severity{{sensor="{safe}",level="{lvl}"}} {v}'
            )
    breach = sum(1 for r in readings if r.severity in ("warn", "critical"))
    lines.append(
        "# HELP sovereign_os_thermal_breach_total Count of sensors at WARN or CRITICAL"
    )
    lines.append("# TYPE sovereign_os_thermal_breach_total gauge")
    lines.append(f"sovereign_os_thermal_breach_total {breach}")
    lines.append(
        f"# TYPE sovereign_os_thermal_last_run_unix gauge\nsovereign_os_thermal_last_run_unix {int(time.time())}"
    )
    return "\n".join(lines) + "\n"


def append_event_jsonl(path: Path, reading: Reading, host_tag: str) -> None:
    """Append an OCSF Detection Finding (class_uid 2004) for a sensor
    that crossed the CRITICAL threshold. The selfdef daemon's
    eventstream collector tails this file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)
    event = {
        "metadata": {
            "version": "1.3.0",
            "product": {"name": "sovereign-os/thermal-watch", "version": "1.0.0"},
        },
        "category_uid": 2,
        "class_uid": 2004,
        "activity_id": 1,
        "type_uid": 200401,
        "time": now_ms,
        "severity_id": 5,  # critical
        "severity": "Critical",
        "status": "New",
        "finding_info": {
            "title": f"Thermal critical: {reading.source} at {reading.celsius}°C",
            "uid": f"thermal/{reading.source}/{now_ms}",
        },
        "message": (
            f"Sensor {reading.source} reading {reading.celsius}°C exceeds "
            f"critical threshold {reading.critical_threshold}°C"
        ),
        "src_endpoint": {"hostname": host_tag},
        "unmapped": {
            "sensor": reading.source,
            "celsius": reading.celsius,
            "warn_threshold": reading.warn_threshold,
            "critical_threshold": reading.critical_threshold,
            "source": "sovereign-os.thermal-watch.R172",
        },
    }
    with path.open("a") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")


def parse_overrides(specs: list[str]) -> dict[str, tuple[int, int]]:
    """`--override 'k10temp/Tctl=warn:80,crit:92'` parsing.

    Returns dict mapping sensor → (warn, critical). Missing keys keep
    profile defaults."""
    out: dict[str, tuple[int, int]] = {}
    for s in specs:
        if "=" not in s:
            sys.stderr.write(f"WARN  R172: malformed override (missing '='): {s}\n")
            continue
        sensor, rhs = s.split("=", 1)
        warn = critical = None
        for piece in rhs.split(","):
            piece = piece.strip()
            if piece.startswith("warn:"):
                try:
                    warn = int(piece[len("warn:") :])
                except ValueError:
                    pass
            elif piece.startswith("crit:") or piece.startswith("critical:"):
                v = piece.split(":", 1)[1]
                try:
                    critical = int(v)
                except ValueError:
                    pass
        if warn is None or critical is None:
            sys.stderr.write(
                f"WARN  R172: override missing warn or crit: {s}\n"
            )
            continue
        out[sensor.strip()] = (warn, critical)
    return out


def host_tag() -> str:
    try:
        return Path("/etc/hostname").read_text().strip() or os.uname().nodename
    except OSError:
        return os.uname().nodename


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "sovereign-os thermal-watch (R172). Reads hwmon + nvidia-smi, "
            "classifies vs per-profile thresholds, emits Layer B + journal."
        )
    )
    p.add_argument(
        "--profile",
        default=os.environ.get("SOVEREIGN_OS_PROFILE_ID", "sain-01"),
        choices=sorted(PROFILE_THRESHOLDS.keys()),
    )
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--emit-metrics",
        action="store_true",
        help="write Layer B textfile-collector .prom",
    )
    p.add_argument(
        "--metrics-path",
        type=Path,
        default=Path(
            os.environ.get("SOVEREIGN_OS_THERMAL_METRICS", str(DEFAULT_METRICS_PATH))
        ),
    )
    p.add_argument(
        "--events-jsonl",
        type=Path,
        default=Path(
            os.environ.get("SOVEREIGN_OS_THERMAL_EVENTS", str(DEFAULT_EVENTS_JSONL))
        ),
    )
    p.add_argument(
        "--hwmon-dir", type=Path, default=DEFAULT_HWMON_DIR,
    )
    p.add_argument(
        "--override",
        action="append",
        default=[],
        help="Per-sensor override: 'k10temp/Tctl=warn:80,crit:92'",
    )
    p.add_argument(
        "--no-nvidia-smi",
        action="store_true",
        help="Skip the nvidia-smi probe (testing).",
    )
    p.add_argument("--once", action="store_true", help="single-pass (default)")
    p.add_argument(
        "--dry-run-events",
        action="store_true",
        help="don't write the JSONL events file (testing)",
    )
    args = p.parse_args()

    warn, critical = PROFILE_THRESHOLDS[args.profile]
    overrides = parse_overrides(args.override)

    raw = read_hwmon(args.hwmon_dir)
    if not args.no_nvidia_smi:
        raw.extend(read_nvidia_smi())

    readings: list[Reading] = []
    for source, celsius in raw:
        if source in overrides:
            w, c = overrides[source]
        elif source.startswith("nvidia-gpu-"):
            w, c = GPU_THRESHOLDS
        else:
            w, c = warn, critical
        readings.append(classify(source, celsius, w, c))

    if args.emit_metrics:
        try:
            write_atomic(args.metrics_path, render_metrics(readings))
        except OSError as e:
            sys.stderr.write(f"WARN  R172: metrics write failed: {e}\n")

    # Emit JSONL events for CRITICAL readings only.
    critical_readings = [r for r in readings if r.severity == "critical"]
    if critical_readings and not args.dry_run_events:
        try:
            for r in critical_readings:
                append_event_jsonl(args.events_jsonl, r, host_tag())
        except OSError as e:
            sys.stderr.write(f"WARN  R172: event write failed: {e}\n")

    if args.json:
        print(
            json.dumps(
                {
                    "profile": args.profile,
                    "warn_threshold": warn,
                    "critical_threshold": critical,
                    "gpu_warn": GPU_THRESHOLDS[0],
                    "gpu_critical": GPU_THRESHOLDS[1],
                    "readings": [asdict(r) for r in readings],
                    "breach_count": sum(
                        1 for r in readings if r.severity in ("warn", "critical")
                    ),
                    "host_tag": host_tag(),
                    "ts_unix": int(time.time()),
                },
                indent=2,
            )
        )
    else:
        print(f"# R172 thermal-watch — profile={args.profile} (warn={warn} critical={critical})")
        if not readings:
            print("# no sensors exposed")
        else:
            print(f"{'sensor':<28}  {'C':>4}  {'sev':>8}  thresholds")
            for r in readings:
                print(
                    f"{r.source:<28}  {r.celsius:>4}  {r.severity:>8}  "
                    f"warn≥{r.warn_threshold} crit≥{r.critical_threshold}"
                )

    # Exit code reflects worst severity.
    if any(r.severity == "critical" for r in readings):
        return 2
    if any(r.severity == "warn" for r in readings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
