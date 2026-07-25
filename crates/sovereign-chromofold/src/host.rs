//! `host` — the **provenance-A** searchable surface (SDD-400 step 7).
//!
//! FM-index `count` / `ranges` / `locate` on the GPU engine, for a caller holding a
//! `.cffm` container blob. This is the safe, `unsafe`-free sibling of the CPU-native
//! [`FmIndex`](crate::FmIndex) (provenance-B): it delegates to
//! [`sovereign_chromofold_sys::HostFmIndex`], which owns **all** host↔device
//! marshalling inside the engine — so nothing here (nor any downstream caller) links
//! cudart or touches a device pointer.
//!
//! ## Opt-in, off by default (honest-degrade)
//!
//! This module compiles in **every** build so downstream code is feature-agnostic,
//! but the behaviour is gated on the `linked` feature (the operator mandate: the GPU
//! engine is opt-in, off by default):
//!
//! - `linked` **off** (default): [`HostFmSearch::load`] returns
//!   [`HostSearchError::Unavailable`] — never a fabricated index, never a fake result.
//! - `linked` **on** (a box with a resident `libchromofold`): it delegates to the
//!   safe FFI wrapper and runs the search on the GPU.
//!
//! Pattern symbols are token ids **already shifted into the sentinel alphabet** the
//! backward search consumes — the same convention the `.cffm` fixtures store (matching
//! [`sovereign_chromofold_sys::HostFmIndex`]). Provenance-A and provenance-B must agree
//! with the same oracle; this surface is the one that runs on hardware.

pub use sovereign_chromofold_sys::CfStatus;

/// Why a provenance-A host search could not produce a result. Distinguishes the
/// honest-degrade case (engine not linked) from a real engine failure, so a caller
/// can fall back to [`FmIndex`](crate::FmIndex) on `Unavailable` but must **not**
/// silently swallow an `Engine` error (a bad blob or a CUDA fault).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HostSearchError {
    /// The GPU engine is not linked (the `linked` feature is off). Honest-degrade:
    /// there is no result to give, and none is fabricated.
    Unavailable,
    /// The linked engine returned a non-`Ok` status (invalid `.cffm`, CUDA error, …).
    Engine(CfStatus),
}

impl core::fmt::Display for HostSearchError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            HostSearchError::Unavailable => {
                f.write_str("ChromoFold GPU engine not linked (opt-in `linked` feature off)")
            }
            HostSearchError::Engine(st) => write!(f, "ChromoFold engine returned {st:?}"),
        }
    }
}

impl std::error::Error for HostSearchError {}

/// A device-resident FM-index built from a `.cffm` blob, queried with plain host
/// slices — the safe **provenance-A** search surface. Build once (P9 build ≠ query),
/// then `count` / `ranges` / `locate` many times.
///
/// When the `linked` feature is off this type still exists (so signatures are stable),
/// but it can never be constructed — [`HostFmSearch::load`] honest-degrades to
/// [`HostSearchError::Unavailable`].
pub struct HostFmSearch {
    #[cfg(feature = "linked")]
    inner: sovereign_chromofold_sys::HostFmIndex,
}

impl HostFmSearch {
    /// Build a device-resident FM-index from a `.cffm` container blob.
    ///
    /// Honest-degrades to [`HostSearchError::Unavailable`] with the `linked` feature
    /// off; delegates to the engine otherwise.
    pub fn load(cffm: &[u8]) -> Result<Self, HostSearchError> {
        #[cfg(feature = "linked")]
        {
            match sovereign_chromofold_sys::HostFmIndex::load(cffm) {
                Ok(inner) => Ok(Self { inner }),
                Err(st) => Err(HostSearchError::Engine(st)),
            }
        }
        #[cfg(not(feature = "linked"))]
        {
            let _ = cffm;
            Err(HostSearchError::Unavailable)
        }
    }

    /// Count occurrences of each pattern (flattened `pat`, per-pattern `pstart`/`plen`).
    /// One count per pattern; `pstart` and `plen` must be equal length.
    pub fn count(
        &self,
        pat: &[i32],
        pstart: &[i32],
        plen: &[i32],
    ) -> Result<Vec<u32>, HostSearchError> {
        #[cfg(feature = "linked")]
        {
            self.inner
                .count(pat, pstart, plen)
                .map_err(HostSearchError::Engine)
        }
        #[cfg(not(feature = "linked"))]
        {
            let _ = (pat, pstart, plen);
            Err(HostSearchError::Unavailable)
        }
    }

    /// Suffix-array `[lo, hi)` interval per pattern (occurrences = `hi - lo`).
    pub fn ranges(
        &self,
        pat: &[i32],
        pstart: &[i32],
        plen: &[i32],
    ) -> Result<(Vec<i32>, Vec<i32>), HostSearchError> {
        #[cfg(feature = "linked")]
        {
            self.inner
                .ranges(pat, pstart, plen)
                .map_err(HostSearchError::Engine)
        }
        #[cfg(not(feature = "linked"))]
        {
            let _ = (pat, pstart, plen);
            Err(HostSearchError::Unavailable)
        }
    }

    /// Text positions for a set of suffix-array rows (from [`HostFmSearch::ranges`]).
    pub fn locate(&self, rows: &[i32]) -> Result<Vec<i32>, HostSearchError> {
        #[cfg(feature = "linked")]
        {
            self.inner.locate(rows).map_err(HostSearchError::Engine)
        }
        #[cfg(not(feature = "linked"))]
        {
            let _ = rows;
            Err(HostSearchError::Unavailable)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(not(feature = "linked"))]
    fn load_honest_degrades_without_the_engine() {
        // Default build: the GPU engine is not linked, so load MUST refuse rather
        // than fabricate an index. This is the opt-in / off-by-default contract.
        // (matches!, not assert_eq!: HostFmSearch wraps an FFI handle and is neither
        // Debug nor PartialEq, so we inspect the Err arm rather than the whole Result.)
        assert!(matches!(
            HostFmSearch::load(&[]),
            Err(HostSearchError::Unavailable)
        ));
        assert!(matches!(
            HostFmSearch::load(b"CFFM not-a-real-blob"),
            Err(HostSearchError::Unavailable)
        ));
    }

    #[test]
    fn error_display_distinguishes_degrade_from_failure() {
        assert!(
            HostSearchError::Unavailable
                .to_string()
                .contains("not linked")
        );
        assert!(
            HostSearchError::Engine(CfStatus::Cuda)
                .to_string()
                .contains("Cuda")
        );
    }
}
