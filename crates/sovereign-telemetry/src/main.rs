//! `sovereign-telemetry` — sovereign-os's live hardware-telemetry probe.
//!
//! Reads the running system and emits a validated `PressureSnapshot` +
//! `LoadSnapshot` as JSON on stdout. This is the first runnable binary in the
//! observability lane: it drives the `sovereign-pressure-sensors` and
//! `sovereign-hardware-load-sample` ingestion end-to-end against real kernel
//! and vendor telemetry, degrading gracefully when a source (PSI, a GPU) is
//! absent rather than failing.
//!
//! Usage: `sovereign-telemetry` → pretty JSON on stdout, exit 0 (exit 1 only
//! on a serialization fault, which cannot happen for these types).

#![forbid(unsafe_code)]

use std::fs;
use std::process::Command;
use std::thread::sleep;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use sovereign_hardware_load_sample::LoadSnapshot;
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget};
use sovereign_hardware_thermal_policy::ThermalPolicy;
use sovereign_observability_fabric::{ObservabilityFabric, ObservabilitySource, SourceState};
use sovereign_pressure_reactions::{ReactionThresholds, derive_reactions};
use sovereign_pressure_sensors::{PressureAxis, PressureSnapshot};

// ---------------------------------------------------------------------------
// Sampling glue.
//
// The model crates (`sovereign-pressure-sensors`, `sovereign-hardware-load-
// sample`, `sovereign-observability-fabric`) are pure typed snapshots with
// canonical constructors + validation; they intentionally carry no OS I/O.
// Reading `/proc`, `/sys`, and `nvidia-smi` is this binary's job, so the raw
// parsers live here and feed the model types through their public fields.
// ---------------------------------------------------------------------------

/// CPU time accumulators from `/proc/stat`'s aggregate `cpu` line.
struct CpuTimes {
    idle: u64,
    total: u64,
}

/// First NVIDIA GPU reading from an `nvidia-smi` CSV row.
struct GpuTelemetry {
    vram_used_gb: u32,
    util_pct: u8,
    temp_c: u8,
}

/// Parse a PSI file's `some avg10=<pct>` into a normalised fraction 0.0..=1.0,
/// or `None` when the line is absent/unparseable.
fn parse_psi_some_avg10(content: &str) -> Option<f32> {
    let rest = content.lines().find_map(|l| l.strip_prefix("some "))?;
    let pct: f32 = rest
        .split_whitespace()
        .find_map(|f| f.strip_prefix("avg10="))
        .and_then(|v| v.parse().ok())?;
    Some((pct / 100.0).clamp(0.0, 1.0))
}

/// Parse the aggregate `cpu` line of `/proc/stat` into idle+total jiffies.
fn parse_proc_stat_cpu(content: &str) -> Option<CpuTimes> {
    let mut fields = content.lines().next()?.split_whitespace();
    if fields.next()? != "cpu" {
        return None;
    }
    let vals: Vec<u64> = fields.filter_map(|x| x.parse().ok()).collect();
    if vals.len() < 4 {
        return None;
    }
    // idle (3) + iowait (4, when present) count as not-busy.
    let idle = vals[3] + vals.get(4).copied().unwrap_or(0);
    let total: u64 = vals.iter().sum();
    Some(CpuTimes { idle, total })
}

/// Busy-percent (0..=100) between two `/proc/stat` cpu samples.
fn cpu_util_pct(a: CpuTimes, b: CpuTimes) -> u8 {
    let dt = b.total.saturating_sub(a.total);
    if dt == 0 {
        return 0;
    }
    let di = b.idle.saturating_sub(a.idle);
    let busy = dt.saturating_sub(di);
    ((busy * 100) / dt).min(100) as u8
}

/// Parse a `thermal_zone*/temp` (millidegrees C) into whole °C.
fn parse_thermal_zone_temp(content: &str) -> Option<u8> {
    let milli: i64 = content.trim().parse().ok()?;
    Some((milli / 1000).clamp(0, 255) as u8)
}

/// Parse one `nvidia-smi --format=csv,noheader,nounits` row of
/// `memory.used[MiB], utilization.gpu[%], temperature.gpu[C]`.
fn parse_gpu_csv(line: &str) -> Option<GpuTelemetry> {
    let mut f = line.split(',').map(str::trim);
    let mem_mib: u64 = f.next()?.parse().ok()?;
    let util: f32 = f.next()?.parse().ok()?;
    let temp: f32 = f.next()?.parse().ok()?;
    Some(GpuTelemetry {
        vram_used_gb: (mem_mib / 1024) as u32,
        util_pct: util.round().clamp(0.0, 100.0) as u8,
        temp_c: temp.round().clamp(0.0, 255.0) as u8,
    })
}

/// Unix epoch seconds as a string. The probe carries no calendar formatter, so
/// it stamps captures with the raw epoch; consumers convert as needed.
fn captured_at() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
        .to_string()
}

/// `some avg10` PSI stall fraction (0.0..=1.0) for one resource, or 0.0 when
/// PSI is unavailable (e.g. the kernel was built without `CONFIG_PSI`).
fn psi(resource: &str) -> f32 {
    fs::read_to_string(format!("/proc/pressure/{resource}"))
        .ok()
        .and_then(|c| parse_psi_some_avg10(&c))
        .unwrap_or(0.0)
}

/// CPU utilization sampled across a 200ms window, or `None` when `/proc/stat`
/// is unreadable.
fn cpu_util() -> Option<u8> {
    let a = parse_proc_stat_cpu(&fs::read_to_string("/proc/stat").ok()?)?;
    sleep(Duration::from_millis(200));
    let b = parse_proc_stat_cpu(&fs::read_to_string("/proc/stat").ok()?)?;
    Some(cpu_util_pct(a, b))
}

/// First thermal zone's temperature in °C, or `None` when sysfs thermal is
/// unavailable (e.g. inside a container without `/sys/class/thermal`).
fn cpu_temp() -> Option<u8> {
    fs::read_to_string("/sys/class/thermal/thermal_zone0/temp")
        .ok()
        .and_then(|c| parse_thermal_zone_temp(&c))
}

/// The first NVIDIA GPU's telemetry via `nvidia-smi`, or `None` when the tool
/// is absent / returns no usable row (the common case off a GPU host).
fn nvidia_gpu() -> Option<GpuTelemetry> {
    let out = Command::new("nvidia-smi")
        .args([
            "--query-gpu=memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let text = String::from_utf8(out.stdout).ok()?;
    parse_gpu_csv(text.lines().next()?)
}

/// Honest source-*presence* fabric: mark the sources this probe can detect on
/// disk as `Idle` (connected, throughput not measured here), leaving the rest
/// `Disconnected`. A richer collector measures real eps later; this binary
/// reports only what it can verify, so the cockpit never shows a source as
/// live that this probe didn't actually find.
fn observability(at: &str, gpu_present: bool) -> ObservabilityFabric {
    let mut fab = ObservabilityFabric::empty_canonical();
    let mut mark = |src, present: bool| {
        let state = if present {
            SourceState::Idle
        } else {
            SourceState::Disconnected
        };
        // The canonical fabric carries every source, so the lookup always
        // hits; set presence-state + heartbeat directly on the public record.
        if let Some(rec) = fab.sources.iter_mut().find(|r| r.source == src) {
            rec.state = state;
            rec.last_heartbeat_at = at.to_string();
        }
    };
    mark(
        ObservabilitySource::Psi,
        std::path::Path::new("/proc/pressure/cpu").exists(),
    );
    mark(ObservabilitySource::Dcgm, gpu_present);
    mark(
        ObservabilitySource::Journald,
        std::path::Path::new("/run/systemd/journal").exists()
            || std::path::Path::new("/var/log/journal").exists(),
    );
    mark(
        ObservabilitySource::ZfsEvents,
        std::path::Path::new("/proc/spl/kstat/zfs").exists(),
    );
    fab
}

/// Set one axis reading on a pressure snapshot in place (the canonical
/// snapshot carries every axis, so the lookup always hits).
fn set_axis(snapshot: &mut PressureSnapshot, axis: PressureAxis, value: f32) {
    if let Some(r) = snapshot.readings.iter_mut().find(|r| r.axis == axis) {
        r.value = value;
    }
}

/// A serde enum's kebab-case wire string, for use as a Prometheus label value.
fn label(x: &impl serde::Serialize) -> String {
    serde_json::to_value(x)
        .ok()
        .and_then(|v| v.as_str().map(String::from))
        .unwrap_or_default()
}

/// One full typed telemetry sample of the running system.
struct Sample {
    at: String,
    pressure: PressureSnapshot,
    load: LoadSnapshot,
    load_valid: bool,
    fabric: ObservabilityFabric,
    fabric_valid: bool,
    thermal_verdicts: Vec<(
        HardwareTarget,
        sovereign_hardware_thermal_policy::ThermalVerdict,
    )>,
    thermal_any_shutdown: bool,
    reactions: Vec<sovereign_pressure_reactions::Reaction>,
}

/// Probe the running system once into a typed [`Sample`].
fn sample() -> Sample {
    let at = captured_at();

    // Pressure — real Linux PSI on cpu/memory/io (0.0 each when PSI disabled);
    // the Gpu/HumanAttention/Cost axes are not measured by this probe and stay
    // at the canonical 0.0 rather than being fabricated.
    let mut pressure = PressureSnapshot::free_canonical();
    pressure.captured_at = at.clone();
    set_axis(&mut pressure, PressureAxis::Cpu, psi("cpu"));
    set_axis(&mut pressure, PressureAxis::Memory, psi("memory"));
    set_axis(&mut pressure, PressureAxis::Io, psi("io"));

    // Load — cpu-pulse utilization from /proc/stat; NVIDIA GPU best-effort.
    // Both update the canonical snapshot's public per-target records in place.
    let mut load = LoadSnapshot::empty_canonical(&at);
    if let Some(u) = cpu_util()
        && let Some(t) = load
            .loads
            .iter_mut()
            .find(|l| l.target == HardwareTarget::CpuPulse)
    {
        t.util_pct = u;
        t.temp_c = cpu_temp().unwrap_or(0);
    }
    let gpu = nvidia_gpu();
    if let Some(g) = &gpu
        && let Some(t) = load
            .loads
            .iter_mut()
            .find(|l| l.target == HardwareTarget::BlackwellOracle)
    {
        t.vram_used_gb = g.vram_used_gb;
        t.util_pct = g.util_pct;
        t.temp_c = g.temp_c;
    }
    let registry = HardwareRegistry::canonical();
    let load_valid = load.validate_against(&registry).is_ok();

    // Observability — honest source-presence fabric.
    let fabric = observability(&at, gpu.is_some());
    let fabric_valid = fabric.validate().is_ok();

    // Derived — per-target thermal verdicts + E0431 adaptive reactions.
    let thermal = ThermalPolicy::canonical();
    let thermal_verdicts = thermal.evaluate_snapshot(&load);
    let thermal_any_shutdown = thermal.any_shutdown(&load);
    let reactions = derive_reactions(&pressure, &load, &registry, ReactionThresholds::default());

    Sample {
        at,
        pressure,
        load,
        load_valid,
        fabric,
        fabric_valid,
        thermal_verdicts,
        thermal_any_shutdown,
        reactions,
    }
}

impl Sample {
    /// Render as the structured JSON document (raw measurement + derived
    /// scheduling signal).
    fn to_json(&self) -> serde_json::Value {
        let thermal_verdicts: Vec<serde_json::Value> = self
            .thermal_verdicts
            .iter()
            .map(|(target, verdict)| serde_json::json!({ "target": target, "verdict": verdict }))
            .collect();
        serde_json::json!({
            "schema": "sovereign-telemetry/1",
            "captured_at_unix": self.at,
            "pressure": self.pressure,
            "load": self.load,
            "load_valid": self.load_valid,
            "observability": self.fabric,
            "observability_valid": self.fabric_valid,
            "derived": {
                "thermal_verdicts": thermal_verdicts,
                "thermal_any_shutdown": self.thermal_any_shutdown,
                "adaptive_reactions": self.reactions,
            },
        })
    }

    /// Render as Prometheus text-exposition — the operator-visible surface
    /// (write to a node_exporter textfile → scrape → Grafana). Aligns with the
    /// M00201–M00206 observability-plane metric sets.
    fn to_prometheus(&self) -> String {
        let mut s = String::new();
        s.push_str("# HELP sovereign_pressure_axis Normalised 0..1 stall pressure per PSI axis.\n");
        s.push_str("# TYPE sovereign_pressure_axis gauge\n");
        for r in &self.pressure.readings {
            s.push_str(&format!(
                "sovereign_pressure_axis{{axis=\"{}\"}} {}\n",
                label(&r.axis),
                r.value
            ));
        }
        s.push_str(
            "# HELP sovereign_load_util_pct Compute utilization percent per hardware target.\n",
        );
        s.push_str("# TYPE sovereign_load_util_pct gauge\n");
        for l in &self.load.loads {
            s.push_str(&format!(
                "sovereign_load_util_pct{{target=\"{}\"}} {}\n",
                label(&l.target),
                l.util_pct
            ));
        }
        s.push_str("# HELP sovereign_load_vram_used_gb VRAM used (GiB) per hardware target.\n");
        s.push_str("# TYPE sovereign_load_vram_used_gb gauge\n");
        for l in &self.load.loads {
            s.push_str(&format!(
                "sovereign_load_vram_used_gb{{target=\"{}\"}} {}\n",
                label(&l.target),
                l.vram_used_gb
            ));
        }
        s.push_str("# HELP sovereign_thermal_verdict 1 for the live thermal verdict per target.\n");
        s.push_str("# TYPE sovereign_thermal_verdict gauge\n");
        for (target, verdict) in &self.thermal_verdicts {
            s.push_str(&format!(
                "sovereign_thermal_verdict{{target=\"{}\",verdict=\"{}\"}} 1\n",
                label(target),
                label(verdict)
            ));
        }
        s.push_str(
            "# HELP sovereign_thermal_any_shutdown 1 if any target is in thermal Shutdown.\n",
        );
        s.push_str("# TYPE sovereign_thermal_any_shutdown gauge\n");
        s.push_str(&format!(
            "sovereign_thermal_any_shutdown {}\n",
            u8::from(self.thermal_any_shutdown)
        ));
        s.push_str("# HELP sovereign_adaptive_reaction_active 1 per fired E0431 adaptive-reaction trigger.\n");
        s.push_str("# TYPE sovereign_adaptive_reaction_active gauge\n");
        for rx in &self.reactions {
            s.push_str(&format!(
                "sovereign_adaptive_reaction_active{{trigger=\"{}\"}} 1\n",
                label(&rx.trigger)
            ));
        }
        s.push_str("# HELP sovereign_telemetry_valid 1 when the snapshot passed validation.\n");
        s.push_str("# TYPE sovereign_telemetry_valid gauge\n");
        s.push_str(&format!(
            "sovereign_telemetry_valid{{kind=\"load\"}} {}\n",
            u8::from(self.load_valid)
        ));
        s.push_str(&format!(
            "sovereign_telemetry_valid{{kind=\"observability\"}} {}\n",
            u8::from(self.fabric_valid)
        ));
        s
    }
}

fn main() {
    // Output modes:
    //   default        one pretty JSON sample, then exit (the probe).
    //   --prometheus   Prometheus text-exposition (operator-visible surface;
    //                  write to a node_exporter textfile → scrape → Grafana).
    //   --watch [--interval N]   emit one sample per N seconds until
    //                  interrupted — a continuous monitor (compact NDJSON, or
    //                  repeated Prometheus blocks when combined with --prometheus).
    let args: Vec<String> = std::env::args().skip(1).collect();
    let watch = args.iter().any(|a| a == "--watch");
    let prometheus = args.iter().any(|a| a == "--prometheus");
    let interval_secs = args
        .iter()
        .position(|a| a == "--interval")
        .and_then(|i| args.get(i + 1))
        .and_then(|s| s.parse::<u64>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(5);

    loop {
        let s = sample();
        if prometheus {
            print!("{}", s.to_prometheus());
        } else {
            let doc = s.to_json();
            // Compact one-line NDJSON while watching; pretty for a single shot.
            let rendered = if watch {
                serde_json::to_string(&doc)
            } else {
                serde_json::to_string_pretty(&doc)
            };
            match rendered {
                Ok(out) => println!("{out}"),
                Err(e) => {
                    eprintln!("sovereign-telemetry: serialization failed: {e}");
                    std::process::exit(1);
                }
            }
        }
        if !watch {
            break;
        }
        sleep(Duration::from_secs(interval_secs));
    }
}
