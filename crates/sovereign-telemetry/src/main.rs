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

use sovereign_hardware_load_sample::{
    GpuTelemetry, LoadSnapshot, cpu_util_pct, parse_gpu_csv, parse_proc_stat_cpu,
    parse_thermal_zone_temp,
};
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget};
use sovereign_hardware_thermal_policy::ThermalPolicy;
use sovereign_observability_fabric::{ObservabilityFabric, ObservabilitySource, SourceState};
use sovereign_pressure_reactions::{ReactionThresholds, derive_reactions};
use sovereign_pressure_sensors::{PressureSnapshot, parse_psi_some_avg10};

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
        .and_then(|c| parse_psi_some_avg10(&c).ok())
        .unwrap_or(0.0)
}

/// CPU utilization sampled across a 200ms window, or `None` when `/proc/stat`
/// is unreadable.
fn cpu_util() -> Option<u8> {
    let a = parse_proc_stat_cpu(&fs::read_to_string("/proc/stat").ok()?).ok()?;
    sleep(Duration::from_millis(200));
    let b = parse_proc_stat_cpu(&fs::read_to_string("/proc/stat").ok()?).ok()?;
    Some(cpu_util_pct(a, b))
}

/// First thermal zone's temperature in °C, or `None` when sysfs thermal is
/// unavailable (e.g. inside a container without `/sys/class/thermal`).
fn cpu_temp() -> Option<u8> {
    fs::read_to_string("/sys/class/thermal/thermal_zone0/temp")
        .ok()
        .and_then(|c| parse_thermal_zone_temp(&c).ok())
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
    parse_gpu_csv(text.lines().next()?).ok()
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
        // update_source only fails on an absent source, impossible on the
        // canonical fabric — ignore the typed result deliberately.
        let _ = fab.update_source(src, state, 0, at);
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

    // Pressure — real Linux PSI on cpu/memory/io (0.0 each when PSI disabled).
    let pressure = PressureSnapshot::from_psi(&at, psi("cpu"), psi("memory"), psi("io"))
        .expect("PSI stall fractions are normalised 0..=1, so from_psi validates");

    // Load — cpu-pulse utilization from /proc/stat; NVIDIA GPU best-effort.
    let mut load = LoadSnapshot::empty_canonical(&at);
    if let Some(u) = cpu_util() {
        // Sample is already range-valid; ignore the typed result deliberately.
        let _ = load.update_target(HardwareTarget::CpuPulse, 0, u, cpu_temp().unwrap_or(0), &at);
    }
    let gpu = nvidia_gpu();
    if let Some(g) = gpu {
        let _ = load.update_gpu(HardwareTarget::BlackwellOracle, g, &at);
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
