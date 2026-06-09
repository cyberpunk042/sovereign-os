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

/// Take one full telemetry sample of the running system and return it as a
/// JSON document (raw measurement + derived scheduling signal).
fn sample() -> serde_json::Value {
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

    // Derived — per-target thermal verdicts from the live load (the actionable
    // scheduling signal a thermal-aware dispatcher consumes). Separated from
    // the raw telemetry above so consumers can tell measurement from policy.
    let thermal = ThermalPolicy::canonical();
    let thermal_verdicts: Vec<serde_json::Value> = thermal
        .evaluate_snapshot(&load)
        .into_iter()
        .map(|(target, verdict)| serde_json::json!({ "target": target, "verdict": verdict }))
        .collect();
    let thermal_any_shutdown = thermal.any_shutdown(&load);

    // Derived — E0431 adaptive-intelligence reactions: the operator-named
    // scheduler actions prescribed by the live pressure + idle hardware.
    let reactions = derive_reactions(&pressure, &load, &registry, ReactionThresholds::default());

    let doc = serde_json::json!({
        "schema": "sovereign-telemetry/1",
        "captured_at_unix": at,
        "pressure": pressure,
        "load": load,
        "load_valid": load_valid,
        "observability": fabric,
        "observability_valid": fabric_valid,
        "derived": {
            "thermal_verdicts": thermal_verdicts,
            "thermal_any_shutdown": thermal_any_shutdown,
            "adaptive_reactions": reactions,
        },
    });
    doc
}

fn main() {
    // `--watch [--interval N]`: emit one compact JSON sample per N seconds
    // (NDJSON stream) until interrupted — a continuous monitor. Without
    // `--watch`, emit a single pretty sample and exit (the default probe).
    let args: Vec<String> = std::env::args().skip(1).collect();
    let watch = args.iter().any(|a| a == "--watch");
    let interval_secs = args
        .iter()
        .position(|a| a == "--interval")
        .and_then(|i| args.get(i + 1))
        .and_then(|s| s.parse::<u64>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(5);

    loop {
        let doc = sample();
        // Compact one-line NDJSON while watching; pretty for a single shot.
        let rendered = if watch {
            serde_json::to_string(&doc)
        } else {
            serde_json::to_string_pretty(&doc)
        };
        match rendered {
            Ok(s) => println!("{s}"),
            Err(e) => {
                eprintln!("sovereign-telemetry: serialization failed: {e}");
                std::process::exit(1);
            }
        }
        if !watch {
            break;
        }
        sleep(Duration::from_secs(interval_secs));
    }
}
