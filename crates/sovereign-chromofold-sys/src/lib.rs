//! `sovereign-chromofold-sys` — the sanctioned-unsafe FFI carve-out over the
//! ChromoFold native engine's **stable C ABI** (`../chromoFold/include/chromofold/chromofold.h`).
//!
//! Every other crate in this workspace forbids `unsafe`
//! (`[workspace.lints.rust] unsafe_code = "forbid"`). Binding a C ABI needs
//! `extern "C"` + `unsafe` call sites, so — per **SDD-500** — this is the single,
//! operator-approved place they live (the SECOND carve-out after `sovereign-simd`).
//! The safe surface callers use is [`sovereign-chromofold`]; nothing outside this
//! crate ever sees a raw device pointer or writes `unsafe`.
//!
//! ## What it binds (ABI v0)
//!
//! Two committed headers, mirrored 1:1:
//! - **`chromofold.h`** — the packed-wavelet primitives (`cf_access_async`,
//!   `cf_rank_async` — the header's *"FM-index primitive"* —, `cf_embedding_gather_async`).
//! - **`chromofold_search.h`** — the RRR-backed self-index + **FM-index
//!   compressed-domain search**: `cf_rrrw_access_async`/`cf_rrrw_rank_async` and
//!   the Lane-A priority `cf_fm_count_async` / `cf_fm_ranges_async` /
//!   `cf_fm_locate_async`. This is the net-new capability with no analogue in a
//!   plain KV/quant stack. (There is no `cf_predict` in the ABI — n-gram
//!   prediction is a *derived* capability built on top of count/ranges, not a C
//!   entry point.)
//!
//! All views are POD / `#[repr(C)]`, passed by value; the query path is
//! device-native (every pointer is a DEVICE pointer). The safe host-side surface
//! — GPU marshalling of host patterns into device memory — is the wrapper crate's
//! step-7 (hardware-gated) work; this crate is the faithful, compile-checked ABI
//! mirror plus the `unsafe` call sites.
//!
//! ## Honest-degrade (opt-in, OFF by default)
//!
//! The `extern "C"` block + `unsafe {}` wrappers are behind the OFF-by-default
//! `linked` feature. With it off (the default, and the only state possible today
//! while `libchromofold` is pre-implementation — SDD-500 Q-500-G) the crate
//! compiles as a pure stub, links nothing, and [`linked`] reports `false` — so
//! the box behaves exactly as it does without ChromoFold.

#![allow(non_camel_case_types)]

use core::ffi::c_int;
#[cfg(feature = "linked")]
use core::ffi::c_void;

/// The ChromoFold stable-C-ABI version this crate binds (`CHROMOFOLD_ABI_VERSION`).
/// A build that links `libchromofold` MUST agree on this, or the layouts below diverge.
pub const ABI_VERSION: u32 = 0;

/// 32-bit words per wavelet superblock (`CF_WAVELET_SB`), fixed to match the
/// frozen Warp reference. The `superblocks` array holds `nblocks + 1` cumulative
/// popcounts per level over windows of this width.
pub const WAVELET_SB: u32 = 8;

/// Status codes returned by the C ABI (`cf_status`). Repr matches the C `enum`
/// (a 32-bit int), so the FFI functions return this directly.
#[repr(i32)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CfStatus {
    /// Success (`CF_OK`).
    Ok = 0,
    /// A caller argument was invalid (`CF_ERR_INVALID_ARGUMENT`).
    InvalidArgument = 1,
    /// The requested operation is unsupported by this build (`CF_ERR_UNSUPPORTED`).
    Unsupported = 2,
    /// The underlying CUDA runtime reported an error (`CF_ERR_CUDA`).
    Cuda = 3,
}

impl CfStatus {
    /// Convert a raw C return code into a [`CfStatus`], mapping any unknown value
    /// to [`CfStatus::Unsupported`] rather than fabricating success.
    #[must_use]
    pub fn from_raw(code: i32) -> Self {
        match code {
            0 => Self::Ok,
            1 => Self::InvalidArgument,
            3 => Self::Cuda,
            _ => Self::Unsupported,
        }
    }
}

/// An immutable, device-resident packed-wavelet index (`cf_wavelet_view`).
///
/// **All pointers are DEVICE pointers** — this is a device-native API (the engine
/// consumes and returns device memory and never does a PCIe round trip). The
/// layout is fixed by the C header and asserted by the conformance test; do not
/// reorder fields.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct CfWaveletView {
    /// `levels * nwords` u32 bitplanes (row-major per level).
    pub bitplanes: *const u32,
    /// `levels * (nblocks + 1)` i32 cumulative popcounts, every [`WAVELET_SB`] words.
    pub superblocks: *const i32,
    /// `levels` i32 zero-bit counts, one per level.
    pub zero_counts: *const i32,
    /// Number of tokens `n` in the index.
    pub token_count: u64,
    /// `ceil(log2(vocab))`.
    pub levels: u32,
    /// `(n + 31) / 32`.
    pub nwords: u32,
    /// Superblock count; `superblocks` has `nblocks + 1` entries per level.
    pub nblocks: u32,
}

/// An RRR-backed wavelet index (`cf_rrrw_view` from `chromofold_search.h`): every
/// wavelet level is an RRR bitvector with two-level superblock samples (the
/// entropy-sized, BWT-below-H0 self-index). Layout matches
/// `detail/rrr_wavelet_device.cuh` exactly — do not reorder. `int` fields/pointers
/// map to [`c_int`] for ABI correctness. All pointers are DEVICE pointers.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct CfRrrwView {
    /// `[bits * cwords]` 4-bit block-class stream per level, LSB-first.
    pub classes: *const u32,
    /// Flat enumerative-offset stream; per-level base in `offbase`.
    pub offsets: *const u32,
    /// `[bits * na]` two-level rank sample: i32 anchor every K superblocks.
    pub rank_a: *const i32,
    /// `[bits * (nsb + 1)]` two-level rank sample: u16 delta per superblock.
    pub rank_d: *const u16,
    /// `[bits * na]` two-level offset-bit sample: i32 anchor.
    pub off_a: *const i32,
    /// `[bits * (nsb + 1)]` two-level offset-bit sample: u16 delta.
    pub off_d: *const u16,
    /// `[bits]` bit offset of each level's slice within `offsets`.
    pub offbase: *const i32,
    /// `[bits]` number of 0-bits per level (1-child descent base).
    pub zeros: *const i32,
    /// `[16]` constant: offset bit-width per class.
    pub width: *const c_int,
    /// `[16 * 16]` constant: Pascal's triangle for the combinatorial decode.
    pub binom: *const c_int,
    /// `levels = ceil(log2(vocab))`.
    pub bits: c_int,
    /// Class words per level.
    pub cwords: c_int,
    /// Superblocks per level (delta/sample rows are `nsb + 1`).
    pub nsb: c_int,
    /// Rank/offset anchors per level.
    pub na: c_int,
}

/// An FM-index over the RRR-backed BWT wavelet + a succinct sampled suffix array
/// (`cf_fm_view` from `chromofold_search.h`). Layout matches
/// `detail/fm_search_device.cuh` exactly. All pointers are DEVICE pointers.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct CfFmView {
    /// The RRR-backed wavelet of the BWT.
    pub w: CfRrrwView,
    /// `[sigma]` cumulative symbol counts (the FM C-table; `C` in the header).
    pub c_table: *const i32,
    /// `[mwords_len]` packed sampled-SA mark plane (bit p set => SA[p] is sampled).
    pub mwords: *const u32,
    /// `[msb_len]` its superblock directory (SB=8 words), ranked by `cf_rank1`.
    pub msb: *const i32,
    /// `[nsval]` sampled suffix-array values (text positions), in SA order.
    pub sval: *const i32,
    /// Alphabet size (incl. sentinel).
    pub sigma: c_int,
    /// BWT length = `|s|`.
    pub n: c_int,
    /// An LF-walk hits a mark within `sa_sample` steps.
    pub sa_sample: c_int,
}

/// Whether this build links the native engine. `false` (the default) means
/// honest-degrade: the FFI is compiled out and no `libchromofold` is required.
#[must_use]
pub const fn linked() -> bool {
    cfg!(feature = "linked")
}

#[cfg(feature = "linked")]
#[link(name = "chromofold")]
unsafe extern "C" {
    fn cf_access_async(
        index: CfWaveletView,
        device_positions: *const u32,
        device_output: *mut u32,
        count: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_rank_async(
        index: CfWaveletView,
        device_symbols: *const u32,
        device_positions: *const u32,
        device_output: *mut u32,
        count: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_embedding_gather_async(
        index: CfWaveletView,
        embeddings: *const f32,
        dim: u32,
        device_positions: *const u32,
        out: *mut f32,
        count: usize,
        stream: *mut c_void,
    ) -> i32;

    // --- chromofold_search.h: RRR self-index + FM-index compressed-domain search ---

    fn cf_rrrw_access_async(
        v: CfRrrwView,
        positions: *const u32,
        out: *mut u32,
        count: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_rrrw_rank_async(
        v: CfRrrwView,
        symbols: *const u32,
        positions: *const u32,
        out: *mut u32,
        count: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_fm_count_async(
        v: CfFmView,
        pat: *const i32,
        pstart: *const i32,
        plen: *const i32,
        out: *mut u32,
        npat: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_fm_ranges_async(
        v: CfFmView,
        pat: *const i32,
        pstart: *const i32,
        plen: *const i32,
        lo_out: *mut i32,
        hi_out: *mut i32,
        npat: usize,
        stream: *mut c_void,
    ) -> i32;

    fn cf_fm_locate_async(
        v: CfFmView,
        r_in: *const i32,
        out: *mut i32,
        nocc: usize,
        stream: *mut c_void,
    ) -> i32;
}

/// Device-native batched `access`: decode token IDs at `device_positions` into
/// `device_output` (both device pointers of length `count`), on `stream`.
///
/// # Safety
/// All pointers must be valid device allocations of the stated length for the
/// lifetime of the async call, `index` must reference live device memory, and
/// `stream` must be a valid `cudaStream_t` (or null for the default stream).
#[cfg(feature = "linked")]
pub unsafe fn access_async(
    index: CfWaveletView,
    device_positions: *const u32,
    device_output: *mut u32,
    count: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_access_async(index, device_positions, device_output, count, stream)
    })
}

/// Device-native batched `rank` — the FM-index primitive: for each query,
/// occurrences of `device_symbols[t]` in the first `device_positions[t]` tokens.
///
/// # Safety
/// Same contract as [`access_async`]: all pointers are device allocations of
/// length `count`, `index` is live device memory, `stream` is valid or null.
#[cfg(feature = "linked")]
pub unsafe fn rank_async(
    index: CfWaveletView,
    device_symbols: *const u32,
    device_positions: *const u32,
    device_output: *mut u32,
    count: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_rank_async(
            index,
            device_symbols,
            device_positions,
            device_output,
            count,
            stream,
        )
    })
}

/// Fused decode-and-gather: for each position decode its token id and immediately
/// gather that token's embedding row — a full decompressed buffer never exists.
///
/// # Safety
/// `embeddings` is `[vocab, dim]` and `out` is `[count, dim]` row-major device
/// memory; all pointers are valid device allocations, `index` is live, `stream`
/// valid or null.
#[cfg(feature = "linked")]
pub unsafe fn embedding_gather_async(
    index: CfWaveletView,
    embeddings: *const f32,
    dim: u32,
    device_positions: *const u32,
    out: *mut f32,
    count: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_embedding_gather_async(index, embeddings, dim, device_positions, out, count, stream)
    })
}

/// RRR self-index batched **access**: decode the token id at each of `count`
/// `positions` into `out` (both device arrays), on `stream`.
///
/// # Safety
/// `v` references live device memory; `positions`/`out` are device arrays of
/// length `count`; `stream` valid or null.
#[cfg(feature = "linked")]
pub unsafe fn rrrw_access_async(
    v: CfRrrwView,
    positions: *const u32,
    out: *mut u32,
    count: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_rrrw_access_async(v, positions, out, count, stream) })
}

/// RRR self-index batched **rank**: occurrences of `symbols[t]` in the first
/// `positions[t]` tokens, for each `t`.
///
/// # Safety
/// `v` references live device memory; `symbols`/`positions`/`out` are device
/// arrays of length `count`; `stream` valid or null.
#[cfg(feature = "linked")]
pub unsafe fn rrrw_rank_async(
    v: CfRrrwView,
    symbols: *const u32,
    positions: *const u32,
    out: *mut u32,
    count: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_rrrw_rank_async(v, symbols, positions, out, count, stream) })
}

/// FM-index backward-search **count** (the Lane-A, sovereign-os-first primitive):
/// for each of `npat` patterns (flattened in `pat`, per-pattern start/len in
/// `pstart`/`plen`) write the occurrence count to `out[t]`.
///
/// # Safety
/// `v` must reference live device memory; `pat`/`pstart`/`plen` are device arrays
/// (`plen`/`pstart` length `npat`), `out` a device array of length `npat`;
/// `stream` valid or null.
#[cfg(feature = "linked")]
pub unsafe fn fm_count_async(
    v: CfFmView,
    pat: *const i32,
    pstart: *const i32,
    plen: *const i32,
    out: *mut u32,
    npat: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_count_async(v, pat, pstart, plen, out, npat, stream) })
}

/// FM-index **ranges**: like [`fm_count_async`], but write the suffix-array
/// `[lo, hi)` interval per pattern (occurrences = `hi - lo`).
///
/// # Safety
/// Same pointer contract as [`fm_count_async`]; `lo_out`/`hi_out` are device
/// arrays of length `npat`.
// 8 args mirrors the `cf_fm_ranges_async` C ABI exactly — the signature is the
// contract, not ours to reshape.
#[allow(clippy::too_many_arguments)]
#[cfg(feature = "linked")]
pub unsafe fn fm_ranges_async(
    v: CfFmView,
    pat: *const i32,
    pstart: *const i32,
    plen: *const i32,
    lo_out: *mut i32,
    hi_out: *mut i32,
    npat: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_fm_ranges_async(v, pat, pstart, plen, lo_out, hi_out, npat, stream)
    })
}

/// FM-index **locate**: for each suffix-array row index `r_in[t]` (from a
/// `[lo, hi)` range) write its text position to `out[t]`.
///
/// # Safety
/// `v` live device memory; `r_in`/`out` device arrays of length `nocc`; `stream`
/// valid or null.
#[cfg(feature = "linked")]
pub unsafe fn fm_locate_async(
    v: CfFmView,
    r_in: *const i32,
    out: *mut i32,
    nocc: usize,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_locate_async(v, r_in, out, nocc, stream) })
}

#[cfg(test)]
mod tests {
    use super::*;
    use core::mem::{align_of, size_of};

    #[test]
    fn abi_constants_match_the_committed_header() {
        // chromofold.h: CHROMOFOLD_ABI_VERSION 0, CF_WAVELET_SB 8.
        assert_eq!(ABI_VERSION, 0);
        assert_eq!(WAVELET_SB, 8);
    }

    #[test]
    fn status_maps_unknown_codes_to_unsupported_not_ok() {
        assert_eq!(CfStatus::from_raw(0), CfStatus::Ok);
        assert_eq!(CfStatus::from_raw(1), CfStatus::InvalidArgument);
        assert_eq!(CfStatus::from_raw(3), CfStatus::Cuda);
        // never fabricate success for a code we don't recognise (SB-077).
        assert_eq!(CfStatus::from_raw(42), CfStatus::Unsupported);
        assert_ne!(CfStatus::from_raw(42), CfStatus::Ok);
    }

    #[test]
    fn wavelet_view_has_the_c_abi_layout() {
        // repr(C): three device pointers, then u64, then three u32. Assert the
        // struct is pointer-aligned and its size is stable so a future field
        // reorder (which would silently corrupt the FFI) fails the build.
        assert_eq!(align_of::<CfWaveletView>(), align_of::<*const u32>());
        let ptrs = 3 * size_of::<*const u32>();
        let expected = ptrs + size_of::<u64>() + 3 * size_of::<u32>();
        // allow tail padding to the pointer alignment
        assert!(size_of::<CfWaveletView>() >= expected);
        assert_eq!(size_of::<CfWaveletView>() % align_of::<CfWaveletView>(), 0);
    }

    #[test]
    fn search_views_are_repr_c_and_pointer_aligned() {
        // cf_fm_view embeds cf_rrrw_view by value; both are POD repr(C) passed by
        // value across the ABI. Assert pointer alignment + no trailing-pad bug so
        // a field reorder that would corrupt the FFI fails the build.
        assert_eq!(align_of::<CfRrrwView>(), align_of::<*const u32>());
        assert_eq!(align_of::<CfFmView>(), align_of::<*const u32>());
        assert_eq!(size_of::<CfRrrwView>() % align_of::<CfRrrwView>(), 0);
        assert_eq!(size_of::<CfFmView>() % align_of::<CfFmView>(), 0);
        // cf_fm_view begins with the embedded wavelet, so it is at least as large.
        assert!(size_of::<CfFmView>() > size_of::<CfRrrwView>());
    }

    #[test]
    fn default_build_does_not_link_the_engine() {
        // honest-degrade: with the `linked` feature off (the default) the box
        // behaves as today — no libchromofold required.
        assert!(!linked());
    }

    /// The no-GPU null-arg seam the native `chromofold_capability.json` advertises
    /// (`null_arg_contract`): every entry point returns `CF_ERR_INVALID_ARGUMENT`
    /// on a NULL required pointer BEFORE any CUDA call — so a linked box validates
    /// the real `.so` ABI contract without a GPU. Compiled only under `linked`
    /// (needs the library); it does not run in the default, engine-absent CI.
    #[cfg(feature = "linked")]
    #[test]
    fn fm_count_rejects_null_args_before_any_cuda_call() {
        let null_rrrw = CfRrrwView {
            classes: core::ptr::null(),
            offsets: core::ptr::null(),
            rank_a: core::ptr::null(),
            rank_d: core::ptr::null(),
            off_a: core::ptr::null(),
            off_d: core::ptr::null(),
            offbase: core::ptr::null(),
            zeros: core::ptr::null(),
            width: core::ptr::null(),
            binom: core::ptr::null(),
            bits: 0,
            cwords: 0,
            nsb: 0,
            na: 0,
        };
        let null_fm = CfFmView {
            w: null_rrrw,
            c_table: core::ptr::null(),
            mwords: core::ptr::null(),
            msb: core::ptr::null(),
            sval: core::ptr::null(),
            sigma: 0,
            n: 0,
            sa_sample: 0,
        };
        let mut out = [0u32; 1];
        // SAFETY: the null-arg contract guarantees an early CF_ERR_INVALID_ARGUMENT
        // return before any pointer is dereferenced or any CUDA call is made.
        let st = unsafe {
            fm_count_async(
                null_fm,
                core::ptr::null(),
                core::ptr::null(),
                core::ptr::null(),
                out.as_mut_ptr(),
                1,
                core::ptr::null_mut(),
            )
        };
        assert_eq!(st, CfStatus::InvalidArgument);
    }
}
