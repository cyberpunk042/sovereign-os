//! `sovereign-chromofold` — the safe Rust surface for the ChromoFold engine.
//!
//! ChromoFold is a GPU-resident, random-access, **searchable** entropy+index
//! layer over the token-/tensor-shaped data an LLM runs on. This crate is the
//! safe wrapper (**SDD-400**) — it forbids `unsafe` (inherited from the
//! workspace) and calls only the safe entry points of the sanctioned FFI crate
//! [`sovereign_chromofold_sys`]. It is an **opt-in, off-by-default** sibling to
//! the existing kv/quant/compress reference controllers, never a replacement.
//!
//! ## What works today
//!
//! - [`FmIndex`] — the **CPU-native FM-index (provenance-B, SDD-400 Q-400-F)**: a
//!   self-contained, `unsafe`-free port that answers `count` / `ranges` / `locate`
//!   / `predict` over a token stream with **no GPU and no native library**,
//!   verified against a naive substring oracle. This is the working search path.
//! - [`availability`] — is the native GPU engine (provenance-A) linked?
//! - [`engine_root`] — the resident engine checkout (`CHROMOFOLD_ROOT`, else
//!   `WARP_SHADERS_ROOT`), or `None` when absent (honest-degrade / offline).
//! - [`descriptor`] — the [`CapabilityDescriptor`], a sovereign-side mirror of the
//!   native `packaging/chromofold_capability.json` source-of-truth.
//!
//! ## The two backends
//!
//! - **provenance-B** ([`FmIndex`]) — CPU-native Rust, always available, the
//!   reference-grade correctness floor.
//! - **provenance-A** (`sovereign-chromofold-sys` + the GPU engine) — the
//!   device-native hot path; its safe host-side marshalling is the hardware-gated
//!   **step 7** of SDD-400. Both must agree with the same oracle.

use serde::{Deserialize, Serialize};

pub mod fm;
pub use fm::FmIndex;

/// The ChromoFold stable-C-ABI version this build binds (`CHROMOFOLD_ABI_VERSION`),
/// re-exported from the FFI crate so consumers read it without touching `unsafe`.
pub use sovereign_chromofold_sys::ABI_VERSION;
/// 32-bit words per wavelet superblock (`CF_WAVELET_SB`), re-exported for the
/// same reason.
pub use sovereign_chromofold_sys::WAVELET_SB;

/// The env var naming the resident ChromoFold engine checkout (native `capability.json`).
pub const ROOT_ENV: &str = "CHROMOFOLD_ROOT";
/// The fallback env var (the sibling Warp repo also holds the engine tree).
pub const ROOT_DEFAULT_ENV: &str = "WARP_SHADERS_ROOT";

/// Whether the native ChromoFold engine is available to this build.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Availability {
    /// `libchromofold` is linked (the `linked` feature is on).
    Linked,
    /// The engine is not linked; every device operation honest-degrades rather
    /// than fabricating a result (SB-077). This is the default.
    Unavailable,
}

/// Report whether the native engine is linked into this build.
#[must_use]
pub fn availability() -> Availability {
    if sovereign_chromofold_sys::linked() {
        Availability::Linked
    } else {
        Availability::Unavailable
    }
}

/// Resolve the resident engine checkout: `CHROMOFOLD_ROOT`, else `WARP_SHADERS_ROOT`
/// (the native capability contract, SDD-400 Q-400-D). `None` means honest-degrade —
/// no checkout resident, so metadata/fixtures come from the committed source-of-truth
/// and device operations are offline.
#[must_use]
pub fn engine_root() -> Option<String> {
    for key in [ROOT_ENV, ROOT_DEFAULT_ENV] {
        if let Ok(v) = std::env::var(key) {
            if !v.is_empty() {
                return Some(v);
            }
        }
    }
    None
}

/// One capability in the [`CapabilityDescriptor`] — mirrors an entry of the native
/// `chromofold_capability.json` `capabilities` array.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Capability {
    /// Stable id (e.g. `fm_count`).
    pub id: String,
    /// The header declaring it (`chromofold.h` or `chromofold_search.h`).
    pub header: String,
    /// The C ABI function (e.g. `cf_fm_count_async`).
    pub func: String,
    /// True for the primitive sovereign-os binds first (Lane A: `fm_count`).
    pub sovereign_os_first: bool,
}

/// A sovereign-side mirror of the native `packaging/chromofold_capability.json`
/// source-of-truth (SDD-300 committed-metadata pattern) — the honest-degrade UI /
/// cockpit / CLI reads it to show exactly what this build offers, never fabricating
/// a capability the build lacks.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilityDescriptor {
    /// The native descriptor schema this mirror tracks.
    pub schema: String,
    /// The native engine this crate binds to.
    pub engine: String,
    /// The correctness oracle + performance floor every binding must match
    /// bit-for-bit (the PROJECT_SYNC contract).
    pub oracle: String,
    /// The stable C-ABI version bound (`CHROMOFOLD_ABI_VERSION`).
    pub abi_version: u32,
    /// Which integration lane this build is on.
    pub lane: String,
    /// The shared library the FFI links.
    pub library: String,
    /// The committed headers mirrored by the `-sys` crate.
    pub headers: Vec<String>,
    /// The env var naming the engine checkout.
    pub root_env: String,
    /// The fallback env var.
    pub root_default_env: String,
    /// Runtime availability of the native engine.
    pub availability: Availability,
    /// The resolved engine root, or `None` when honest-degrading.
    pub engine_root: Option<String>,
    /// Whether the CPU-native FM-index backend (provenance-B, [`FmIndex`]) is
    /// available. Always `true` — it needs no GPU and no native library.
    pub cpu_fm_index: bool,
    /// The per-capability map (mirrors the native descriptor).
    pub capabilities: Vec<Capability>,
}

/// The capability descriptor for this build — the honest current truth.
///
/// Mirrors the native `chromofold_capability.json` capability set: the packed-wavelet
/// primitives (`chromofold.h`) and the RRR self-index + FM-index search
/// (`chromofold_search.h`), with `fm_count` flagged as the sovereign-os-first Lane-A
/// primitive. `availability` and `engine_root` are resolved at call time.
#[must_use]
pub fn descriptor() -> CapabilityDescriptor {
    let cap = |id: &str, header: &str, func: &str, first: bool| Capability {
        id: id.to_string(),
        header: header.to_string(),
        func: func.to_string(),
        sovereign_os_first: first,
    };
    CapabilityDescriptor {
        schema: "chromofold.capability/1".to_string(),
        engine: "chromoFold (native C++20/CUDA, ../chromoFold)".to_string(),
        oracle:
            "warp-solar-system-shaders/warp_compress (Warp prototype, correctness oracle + floor)"
                .to_string(),
        abi_version: sovereign_chromofold_sys::ABI_VERSION,
        lane: "A — FM-index-search-first".to_string(),
        library: "libchromofold.so".to_string(),
        headers: vec![
            "chromofold.h".to_string(),
            "chromofold_search.h".to_string(),
        ],
        root_env: ROOT_ENV.to_string(),
        root_default_env: ROOT_DEFAULT_ENV.to_string(),
        availability: availability(),
        engine_root: engine_root(),
        cpu_fm_index: true,
        capabilities: vec![
            cap("wavelet_access", "chromofold.h", "cf_access_async", false),
            cap("wavelet_rank", "chromofold.h", "cf_rank_async", false),
            cap(
                "embedding_gather",
                "chromofold.h",
                "cf_embedding_gather_async",
                false,
            ),
            cap(
                "rrrw_access",
                "chromofold_search.h",
                "cf_rrrw_access_async",
                false,
            ),
            cap(
                "rrrw_rank",
                "chromofold_search.h",
                "cf_rrrw_rank_async",
                false,
            ),
            cap("fm_count", "chromofold_search.h", "cf_fm_count_async", true),
            cap(
                "fm_ranges",
                "chromofold_search.h",
                "cf_fm_ranges_async",
                false,
            ),
            cap(
                "fm_locate",
                "chromofold_search.h",
                "cf_fm_locate_async",
                false,
            ),
        ],
    }
}

// The searchable surface is [`FmIndex`] (provenance-B, CPU-native). It supersedes
// the earlier corpus-less honest-degrade stubs: a real FM-index needs a corpus,
// so search lives on the index, not on free functions. The GPU host path
// (provenance-A) will add its own surface at SDD-400 step 7.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn availability_is_honest_degrade_by_default() {
        // opt-in, off by default: no GPU engine linked → Unavailable, never a
        // fabricated "Linked". (The CPU FmIndex backend is independent of this.)
        assert_eq!(availability(), Availability::Unavailable);
    }

    #[test]
    fn cpu_fm_index_backend_is_available_and_works() {
        // provenance-B: the CPU FM-index works with no GPU / no engine linked.
        assert!(descriptor().cpu_fm_index);
        let idx = FmIndex::build(&"abracadabra".bytes().map(u32::from).collect::<Vec<_>>());
        assert_eq!(idx.count(&[b'a' as u32]), 5);
    }

    #[test]
    fn descriptor_mirrors_the_native_capability_contract() {
        let d = descriptor();
        assert_eq!(d.abi_version, 0);
        assert_eq!(d.schema, "chromofold.capability/1");
        assert_eq!(d.root_env, "CHROMOFOLD_ROOT");
        assert_eq!(d.root_default_env, "WARP_SHADERS_ROOT");
        assert!(d.lane.contains("FM-index"));
        assert_eq!(d.capabilities.len(), 8);
        // exactly one sovereign-os-first primitive, and it is fm_count (Lane A).
        let first: Vec<&str> = d
            .capabilities
            .iter()
            .filter(|c| c.sovereign_os_first)
            .map(|c| c.id.as_str())
            .collect();
        assert_eq!(first, vec!["fm_count"]);
        // every search capability names the search header.
        assert!(
            d.capabilities
                .iter()
                .filter(|c| c.id.starts_with("fm_") || c.id.starts_with("rrrw_"))
                .all(|c| c.header == "chromofold_search.h")
        );
    }

    #[test]
    fn descriptor_round_trips_through_serde() {
        let d = descriptor();
        let json = serde_json::to_string(&d).expect("serialize");
        let back: CapabilityDescriptor = serde_json::from_str(&json).expect("deserialize");
        assert_eq!(d, back);
    }
}
