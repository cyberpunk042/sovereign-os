//! `sovereign-cpu-dispatch` — E0490: CPU Feature Dispatch.
//!
//! "Do not compile one binary and hope." The AVX engine ships four code paths
//! of increasing capability, and runtime CPUID selects the best one the host
//! actually supports — falling back gracefully so the binary runs everywhere
//! but goes fast on the operator's Zen5. This crate fixes the four paths, their
//! feature requirements, and the selection.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The four build dispatch paths (E0490), least → most capable.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DispatchPath {
    /// Scalar baseline — runs on any x86-64.
    ScalarBaseline,
    /// AVX2 path.
    Avx2,
    /// Generic AVX-512 path.
    Avx512Generic,
    /// Zen5-tuned AVX-512 path (`-march=znver5`).
    Zen5Avx512,
}

impl DispatchPath {
    /// All four paths, least capable first.
    pub const ALL: [DispatchPath; 4] = [
        DispatchPath::ScalarBaseline,
        DispatchPath::Avx2,
        DispatchPath::Avx512Generic,
        DispatchPath::Zen5Avx512,
    ];

    /// Capability rank (ScalarBaseline=0 … Zen5Avx512=3).
    #[must_use]
    pub fn rank(self) -> u8 {
        Self::ALL.iter().position(|p| *p == self).unwrap() as u8
    }
}

/// The host CPU features that gate path selection.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct CpuFeatures {
    /// AVX2 available.
    pub avx2: bool,
    /// AVX-512 (foundation) available.
    pub avx512: bool,
    /// The microarchitecture is AMD Zen5.
    pub zen5: bool,
}

impl CpuFeatures {
    /// Whether this CPU can run `path`.
    #[must_use]
    pub fn supports(&self, path: DispatchPath) -> bool {
        match path {
            DispatchPath::ScalarBaseline => true,
            DispatchPath::Avx2 => self.avx2,
            // AVX-512 paths need AVX-512; the Zen5 path additionally needs Zen5.
            DispatchPath::Avx512Generic => self.avx512,
            DispatchPath::Zen5Avx512 => self.avx512 && self.zen5,
        }
    }
}

/// Select the most capable path the host supports — the runtime-CPUID decision.
/// `ScalarBaseline` is always supported, so this never fails.
#[must_use]
pub fn select_best(features: &CpuFeatures) -> DispatchPath {
    DispatchPath::ALL
        .into_iter()
        .rev() // most capable first
        .find(|p| features.supports(*p))
        .unwrap_or(DispatchPath::ScalarBaseline)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_ranked_paths() {
        assert_eq!(DispatchPath::ALL.len(), 4);
        assert_eq!(DispatchPath::ScalarBaseline.rank(), 0);
        assert_eq!(DispatchPath::Zen5Avx512.rank(), 3);
    }

    #[test]
    fn operator_zen5_gets_the_zen5_path() {
        let zen5 = CpuFeatures {
            avx2: true,
            avx512: true,
            zen5: true,
        };
        assert_eq!(select_best(&zen5), DispatchPath::Zen5Avx512);
    }

    #[test]
    fn generic_avx512_without_zen5_falls_to_generic() {
        let intel_avx512 = CpuFeatures {
            avx2: true,
            avx512: true,
            zen5: false,
        };
        assert_eq!(select_best(&intel_avx512), DispatchPath::Avx512Generic);
        // Zen5 path requires both avx512 AND zen5.
        assert!(!intel_avx512.supports(DispatchPath::Zen5Avx512));
    }

    #[test]
    fn avx2_only_and_baseline_only() {
        let avx2 = CpuFeatures {
            avx2: true,
            avx512: false,
            zen5: false,
        };
        assert_eq!(select_best(&avx2), DispatchPath::Avx2);
        let none = CpuFeatures::default();
        assert_eq!(select_best(&none), DispatchPath::ScalarBaseline);
    }

    #[test]
    fn zen5_flag_without_avx512_does_not_pick_zen5_path() {
        // A Zen5 that (hypothetically) lacks AVX-512 must not take the AVX-512 path.
        let weird = CpuFeatures {
            avx2: true,
            avx512: false,
            zen5: true,
        };
        assert_eq!(select_best(&weird), DispatchPath::Avx2);
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&DispatchPath::Zen5Avx512).unwrap(),
            "\"zen5-avx512\""
        );
    }
}
