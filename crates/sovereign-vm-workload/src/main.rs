//! `sovereign-vm-workload` CLI — the runnable end of E0119 / M00220–M00221.
//!
//! The library fixes the 4090-VM suitability gate: the 4090 runs in a VFIO VM
//! as a quarantined cognition engine, which makes it right for risky, isolatable
//! work and wrong for anything needing tight cross-GPU coupling (the isolation
//! deliberately severs it). But nothing *ran* the gate, so "is it safe to route
//! this workload to the quarantined VM?" was unanswerable at the command line.
//! This binary is that runnable end — it exercises the real decision function
//! [`VmWorkload::is_vm_appropriate`], no live VM required.
//!
//! Modes:
//!   * default (no args) — print the 13 catalogued workloads, grouped into the
//!     ones the quarantined VM is *for* and the ones it must NOT run: the
//!     suitability gate itself, as a human-readable reference.
//!   * `--check FILE` — load a routing request (a single `VmWorkload` or a JSON
//!     array of them: the workloads someone intends to route to the VM), run
//!     `is_vm_appropriate()` on each, report OK / FAIL, and exit non-zero if any
//!     workload would break under VFIO isolation (i.e. must not run in the VM).
//!   * `--help` — usage.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::process::ExitCode;

use sovereign_vm_workload::VmWorkload;

/// The stable kebab-case label for a workload — identical to how [`VmWorkload`]
/// serializes to JSON (kept honest by the `workload_label_matches_serde` test).
fn workload_label(workload: VmWorkload) -> &'static str {
    match workload {
        VmWorkload::DraftGeneration => "draft-generation",
        VmWorkload::UntrustedModelExperiments => "untrusted-model-experiments",
        VmWorkload::WebBrowsingAgents => "web-browsing-agents",
        VmWorkload::ToolPlanning => "tool-planning",
        VmWorkload::SafeFileInspection => "safe-file-inspection",
        VmWorkload::VisionOcrUnknownFiles => "vision-ocr-unknown-files",
        VmWorkload::CodeExecutionAttempts => "code-execution-attempts",
        VmWorkload::DependencyInstalls => "dependency-installs",
        VmWorkload::SpeculativePatchGeneration => "speculative-patch-generation",
        VmWorkload::SharingTensors => "sharing-tensors",
        VmWorkload::TightKvCooperation => "tight-kv-cooperation",
        VmWorkload::LayerSplit => "layer-split",
        VmWorkload::UltraLowLatencySync => "ultra-low-latency-sync",
    }
}

/// A one-line human description of why each workload belongs — or does not
/// belong — in the quarantined 4090 VM.
fn workload_note(workload: VmWorkload) -> &'static str {
    match workload {
        VmWorkload::DraftGeneration => "isolatable draft generation",
        VmWorkload::UntrustedModelExperiments => "untrusted model experiments, safely boxed",
        VmWorkload::WebBrowsingAgents => "web-browsing agents behind the isolation boundary",
        VmWorkload::ToolPlanning => "tool planning that must not touch the host",
        VmWorkload::SafeFileInspection => "safe inspection of files of unknown provenance",
        VmWorkload::VisionOcrUnknownFiles => "vision/OCR of unknown files",
        VmWorkload::CodeExecutionAttempts => "code-execution attempts, quarantined",
        VmWorkload::DependencyInstalls => "dependency installs that could be hostile",
        VmWorkload::SpeculativePatchGeneration => "speculative patch generation, sandboxed",
        VmWorkload::SharingTensors => "needs cross-GPU tensor sharing the isolation severs",
        VmWorkload::TightKvCooperation => "needs tight KV-cache cooperation across GPUs",
        VmWorkload::LayerSplit => "needs a layer-split across GPUs the VM cannot span",
        VmWorkload::UltraLowLatencySync => "needs ultra-low-latency cross-GPU sync",
    }
}

/// The human-readable reference: the 13 workloads, grouped by whether the
/// quarantined VM should run them.
fn reference_text() -> String {
    let mut s = String::from(
        "The 4090-VM suitability gate (E0119 / M00220–M00221): the 4090 runs in a VFIO VM\n\
         as a quarantined cognition engine. Route to it only what the isolation is FOR.\n\n",
    );

    let (good, bad): (Vec<_>, Vec<_>) = VmWorkload::ALL
        .into_iter()
        .partition(|w| w.is_vm_appropriate());

    s.push_str(&format!(
        "  Appropriate for the quarantined VM ({} — isolatable, risky work):\n",
        good.len()
    ));
    for (i, w) in good.iter().enumerate() {
        s.push_str(&format!(
            "  {:>2}. {:<30} {}\n",
            i + 1,
            workload_label(*w),
            workload_note(*w),
        ));
    }

    s.push_str(&format!(
        "\n  MUST NOT run in the VM ({} — need tight cross-GPU coupling the isolation severs):\n",
        bad.len()
    ));
    for (i, w) in bad.iter().enumerate() {
        s.push_str(&format!(
            "  {:>2}. {:<30} {}\n",
            i + 1,
            workload_label(*w),
            workload_note(*w),
        ));
    }
    s
}

/// The `--help` / usage text.
fn help_text() -> String {
    "sovereign-vm-workload — the 4090-VM suitability gate (E0119 / M00220–M00221)\n\n\
     The 4090 runs in a VFIO VM as a quarantined cognition engine: right for risky,\n\
     isolatable work; wrong for workloads needing tight cross-GPU coupling (the\n\
     isolation deliberately severs it).\n\n\
     USAGE:\n\
     \x20   sovereign-vm-workload                 print the 13 catalogued workloads (reference)\n\
     \x20   sovereign-vm-workload --check FILE     validate a VM routing request from JSON\n\
     \x20   sovereign-vm-workload --help           print this help and exit\n\n\
     --check FILE loads a single VmWorkload string or a JSON array of them — the\n\
     workloads someone intends to route to the quarantined VM — runs the gate\n\
     is_vm_appropriate() on each, and exits non-zero if any workload would break\n\
     under VFIO isolation (i.e. must not run in the VM).\n"
        .to_string()
}

/// The outcome of checking one requested workload against the gate.
struct CheckOutcome {
    /// The requested workload.
    workload: VmWorkload,
    /// Whether the gate admits it to the quarantined VM.
    appropriate: bool,
}

/// Accept either a single workload string or a JSON array of them.
fn parse_workloads(json: &str) -> Result<Vec<VmWorkload>, serde_json::Error> {
    match serde_json::from_str::<Vec<VmWorkload>>(json) {
        Ok(v) => Ok(v),
        // Not an array — try a single workload string, surfacing that error.
        Err(_) => serde_json::from_str::<VmWorkload>(json).map(|w| vec![w]),
    }
}

/// Parse one-or-many workloads from JSON and run each through the gate.
fn check_json(json: &str) -> Result<Vec<CheckOutcome>, serde_json::Error> {
    let workloads = parse_workloads(json)?;
    Ok(workloads
        .into_iter()
        .map(|w| CheckOutcome {
            workload: w,
            appropriate: w.is_vm_appropriate(),
        })
        .collect())
}

/// `--check FILE`: read the file, run the routing request through the gate,
/// print a report, and return a process exit code (non-zero on read/parse error
/// or if any requested workload must not run in the VM).
fn run_check(path: &str) -> ExitCode {
    let json = match std::fs::read_to_string(path) {
        Ok(j) => j,
        Err(e) => {
            eprintln!("error: cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    let outcomes = match check_json(&json) {
        Ok(o) => o,
        Err(e) => {
            eprintln!("error: {path} is not a VmWorkload (or array of them): {e}");
            return ExitCode::FAILURE;
        }
    };
    if outcomes.is_empty() {
        println!("(no workloads in {path})");
        return ExitCode::SUCCESS;
    }

    let mut all_ok = true;
    for o in &outcomes {
        let label = workload_label(o.workload);
        if o.appropriate {
            println!("OK   {label} — appropriate for the quarantined VM");
        } else {
            all_ok = false;
            println!(
                "FAIL {label} — must NOT run in the VM: {}",
                workload_note(o.workload)
            );
        }
    }

    if all_ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--help" || a == "-h") {
        print!("{}", help_text());
        return ExitCode::SUCCESS;
    }

    if let Some(i) = args.iter().position(|a| a == "--check") {
        let Some(path) = args.get(i + 1) else {
            eprintln!("error: --check requires a FILE argument\n");
            eprint!("{}", help_text());
            return ExitCode::FAILURE;
        };
        return run_check(path);
    }

    if let Some(unknown) = args.iter().find(|a| a.starts_with('-')) {
        eprintln!("error: unknown argument '{unknown}'\n");
        eprint!("{}", help_text());
        return ExitCode::FAILURE;
    }

    print!("{}", reference_text());
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn workload_label_matches_serde() {
        // The CLI's kebab labels must not drift from the enum's JSON form.
        for w in VmWorkload::ALL {
            let json = serde_json::to_string(&w).unwrap();
            assert_eq!(json, format!("\"{}\"", workload_label(w)));
        }
    }

    #[test]
    fn reference_lists_all_thirteen_workloads() {
        let t = reference_text();
        for w in VmWorkload::ALL {
            assert!(
                t.contains(workload_label(w)),
                "reference missing {w:?}:\n{t}"
            );
            assert!(
                t.contains(workload_note(w)),
                "reference missing note for {w:?}:\n{t}"
            );
        }
        // Every catalogued workload appears on exactly one numbered line.
        let numbered = t
            .lines()
            .filter(|l| l.trim_start().starts_with(|c: char| c.is_ascii_digit()))
            .count();
        assert_eq!(
            numbered,
            VmWorkload::ALL.len(),
            "expected 13 workload lines"
        );
    }

    #[test]
    fn check_admits_appropriate_workload() {
        let json = serde_json::to_string(&VmWorkload::CodeExecutionAttempts).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert_eq!(outcomes[0].workload, VmWorkload::CodeExecutionAttempts);
        assert!(outcomes[0].appropriate);
    }

    #[test]
    fn check_rejects_tight_gpu_coupling_workload() {
        let json = serde_json::to_string(&VmWorkload::LayerSplit).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 1);
        assert!(
            !outcomes[0].appropriate,
            "layer-split must not be admitted to the VM"
        );
    }

    #[test]
    fn check_parses_array_and_flags_the_inappropriate_one() {
        let arr = vec![
            VmWorkload::DraftGeneration,
            VmWorkload::UltraLowLatencySync,
            VmWorkload::WebBrowsingAgents,
        ];
        let json = serde_json::to_string(&arr).unwrap();
        let outcomes = check_json(&json).unwrap();
        assert_eq!(outcomes.len(), 3);
        assert!(outcomes[0].appropriate);
        assert!(!outcomes[1].appropriate); // ultra-low-latency-sync
        assert!(outcomes[2].appropriate);
        // Mixed request → the whole routing request must be rejected.
        assert!(!outcomes.iter().all(|o| o.appropriate));
    }

    #[test]
    fn check_reports_invalid_json_as_error() {
        assert!(check_json("not json").is_err());
        assert!(check_json("\"not-a-real-workload\"").is_err());
    }
}
