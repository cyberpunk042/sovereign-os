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
};
use sovereign_hardware_registry::{HardwareRegistry, HardwareTarget};
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

fn main() {
    let at = captured_at();

    // Pressure — real Linux PSI on cpu/memory/io (0.0 each when PSI disabled).
    let pressure = PressureSnapshot::from_psi(&at, psi("cpu"), psi("memory"), psi("io"))
        .expect("PSI stall fractions are normalised 0..=1, so from_psi validates");

    // Load — cpu-pulse utilization from /proc/stat; NVIDIA GPU best-effort.
    let mut load = LoadSnapshot::empty_canonical(&at);
    if let Some(u) = cpu_util() {
        // Sample is already range-valid; ignore the typed result deliberately.
        let _ = load.update_target(HardwareTarget::CpuPulse, 0, u, 0, &at);
    }
    if let Some(g) = nvidia_gpu() {
        let _ = load.update_gpu(HardwareTarget::BlackwellOracle, g, &at);
    }
    let load_valid = load
        .validate_against(&HardwareRegistry::canonical())
        .is_ok();

    let doc = serde_json::json!({
        "schema": "sovereign-telemetry/1",
        "captured_at_unix": at,
        "pressure": pressure,
        "load": load,
        "load_valid": load_valid,
    });
    match serde_json::to_string_pretty(&doc) {
        Ok(s) => println!("{s}"),
        Err(e) => {
            eprintln!("sovereign-telemetry: serialization failed: {e}");
            std::process::exit(1);
        }
    }
}
