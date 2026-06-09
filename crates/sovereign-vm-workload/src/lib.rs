//! `sovereign-vm-workload` — E0119 / M00220–M00221: 3090-VM workload suitability.
//!
//! The 3090 runs in a VFIO VM as a *quarantined* cognition engine. That makes
//! it ideal for risky, isolatable work — and unfit for anything needing tight
//! cross-GPU coupling (which the isolation boundary deliberately severs). This
//! crate fixes both lists and the suitability gate the scheduler reads before
//! routing a workload to the quarantined VM.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// A kind of workload that might be routed to the quarantined 3090 VM.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum VmWorkload {
    // --- good: isolatable, exactly what the quarantine is for (M00220) ---
    /// Draft generation.
    DraftGeneration,
    /// Untrusted model experiments.
    UntrustedModelExperiments,
    /// Web-browsing agents.
    WebBrowsingAgents,
    /// Tool planning.
    ToolPlanning,
    /// Safe file inspection.
    SafeFileInspection,
    /// Vision/OCR of unknown files.
    VisionOcrUnknownFiles,
    /// Code-execution attempts.
    CodeExecutionAttempts,
    /// Dependency installs.
    DependencyInstalls,
    /// Speculative patch generation.
    SpeculativePatchGeneration,
    // --- bad: need tight GPU coupling the isolation severs (M00221) ---
    /// Sharing tensors across GPUs.
    SharingTensors,
    /// Tight KV-cache cooperation.
    TightKvCooperation,
    /// Layer-split across GPUs.
    LayerSplit,
    /// Ultra-low-latency cross-GPU sync.
    UltraLowLatencySync,
}

impl VmWorkload {
    /// All thirteen catalogued workloads.
    pub const ALL: [VmWorkload; 13] = [
        VmWorkload::DraftGeneration,
        VmWorkload::UntrustedModelExperiments,
        VmWorkload::WebBrowsingAgents,
        VmWorkload::ToolPlanning,
        VmWorkload::SafeFileInspection,
        VmWorkload::VisionOcrUnknownFiles,
        VmWorkload::CodeExecutionAttempts,
        VmWorkload::DependencyInstalls,
        VmWorkload::SpeculativePatchGeneration,
        VmWorkload::SharingTensors,
        VmWorkload::TightKvCooperation,
        VmWorkload::LayerSplit,
        VmWorkload::UltraLowLatencySync,
    ];

    /// Whether this workload is appropriate for the quarantined VM. The
    /// tight-cross-GPU-coupling workloads are NOT (the VFIO isolation severs
    /// the coupling they need); everything else is.
    #[must_use]
    pub fn is_vm_appropriate(self) -> bool {
        !matches!(
            self,
            VmWorkload::SharingTensors
                | VmWorkload::TightKvCooperation
                | VmWorkload::LayerSplit
                | VmWorkload::UltraLowLatencySync
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn thirteen_workloads_nine_good_four_bad() {
        assert_eq!(VmWorkload::ALL.len(), 13);
        let good = VmWorkload::ALL
            .iter()
            .filter(|w| w.is_vm_appropriate())
            .count();
        let bad = VmWorkload::ALL
            .iter()
            .filter(|w| !w.is_vm_appropriate())
            .count();
        assert_eq!(good, 9);
        assert_eq!(bad, 4);
    }

    #[test]
    fn risky_isolatable_work_belongs_in_the_vm() {
        for w in [
            VmWorkload::UntrustedModelExperiments,
            VmWorkload::CodeExecutionAttempts,
            VmWorkload::DependencyInstalls,
            VmWorkload::WebBrowsingAgents,
        ] {
            assert!(w.is_vm_appropriate(), "{w:?}");
        }
    }

    #[test]
    fn tight_gpu_coupling_must_not_run_in_the_vm() {
        for w in [
            VmWorkload::SharingTensors,
            VmWorkload::TightKvCooperation,
            VmWorkload::LayerSplit,
            VmWorkload::UltraLowLatencySync,
        ] {
            assert!(!w.is_vm_appropriate(), "{w:?}");
        }
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&VmWorkload::VisionOcrUnknownFiles).unwrap(),
            "\"vision-ocr-unknown-files\""
        );
        assert_eq!(
            serde_json::to_string(&VmWorkload::TightKvCooperation).unwrap(),
            "\"tight-kv-cooperation\""
        );
    }
}
