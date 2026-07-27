//! `sovereign-chromofold-sys` — the sanctioned-unsafe FFI carve-out over the
//! ChromoFold native engine's **stable C ABI** (`../chromoFold/include/chromofold/chromofold.h`).
//!
//! Every other crate in this workspace forbids `unsafe`
//! (`[workspace.lints.rust] unsafe_code = "forbid"`). Binding a C ABI needs
//! `extern "C"` + `unsafe` call sites, so — per **SDD-400** — this is the single,
//! operator-approved place they live (the SECOND carve-out after `sovereign-simd`).
//! The safe surface callers use is [`sovereign-chromofold`]; nothing outside this
//! crate ever sees a raw device pointer or writes `unsafe`.
//!
//! ## What it binds (ABI v0)
//!
//! Two committed headers, mirrored 1:1:
//! - **`chromofold.h`** — the packed-wavelet primitives (`cf_access_async`,
//!   `cf_rank_async` — the header's *"FM-index primitive"* —, `cf_embedding_gather_async`)
//!   plus the **fused compressed-KV attention** compute kernels (SDD-401 phase 3):
//!   `cf_kv_attn_fused_async` (the folded-KV serving path, ~8× less KV VRAM) and
//!   `cf_kv_attn_dense_async` (its bit-exact verification baseline).
//! - **`chromofold_search.h`** — the RRR-backed self-index + **FM-index
//!   compressed-domain search**: `cf_rrrw_access_async`/`cf_rrrw_rank_async` and
//!   the Lane-A priority `cf_fm_count_async` / `cf_fm_ranges_async` /
//!   `cf_fm_locate_async`. This is the net-new capability with no analogue in a
//!   plain KV/quant stack. (There is no `cf_predict` in the ABI — n-gram
//!   prediction is a *derived* capability built on top of count/ranges, not a C
//!   entry point.)
//!
//! All views are POD / `#[repr(C)]`, passed by value; the async query path is
//! device-native (every pointer is a DEVICE pointer). This crate ALSO binds the
//! engine's **host-pointer FM-search layer** (`cf_fm_host_load` / `cf_fm_host_count`
//! / `cf_fm_host_ranges` / `cf_fm_host_locate` / `cf_fm_host_free`, over the opaque
//! [`CfFmHostIndex`]): the engine performs the host↔device marshalling internally,
//! so this path needs **no cudart on the caller** — SDD-400 "step 7" satisfied *by
//! the engine* rather than re-implemented here. Verified through the `.so` by a
//! pure-C caller (`../chromoFold/packaging/functional_host.c`,
//! `make -C packaging functional-host`: `cf_fm_host_count` bit-identical to golden).
//!
//! ## Honest-degrade (opt-in, OFF by default)
//!
//! The `extern "C"` block + `unsafe {}` wrappers are behind the OFF-by-default
//! `linked` feature. With it off (the default, and the only state possible today
//! while `libchromofold` is pre-implementation — SDD-400 Q-400-G) the crate
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

/// Opaque handle to a device-resident FM-index built from a `.cffm` blob by the
/// engine's **host-pointer** search layer (`cf_fm_host_*` in `chromofold_search.h`).
/// It owns device memory; only the engine dereferences it. Callers hold a `*mut`/`*const`
/// to it and never look inside — so unlike [`CfFmView`] this API needs no cudart on the
/// caller side (all device marshalling is inside the engine). See [`fm_host_load`].
#[repr(C)]
pub struct CfFmHostIndex {
    _private: [u8; 0],
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

    // --- chromofold.h: fused compressed-KV attention (M6/M9 seam; SDD-401 phase 3) ---
    // K/V are block-Huffman-coded ints in device memory; the kernel decodes +
    // dequantizes each attended value inside the consumer, so no dense KV buffer
    // is materialized. All pointers are DEVICE pointers.
    #[allow(clippy::too_many_arguments)]
    fn cf_kv_attn_fused_async(
        kw: *const u32,
        kb: *const i32,
        kl: *const i32,
        kmax: c_int,
        vw: *const u32,
        vb: *const i32,
        vl: *const i32,
        vmax: c_int,
        kscale: *const f32,
        vscale: *const f32,
        q: *const f32,
        out: *mut f32,
        seq: c_int,
        dim: c_int,
        nq: c_int,
        window: c_int,
        block: c_int,
        zero: c_int,
        sscale: f32,
        stream: *mut c_void,
    ) -> i32;

    // Dense-reference KV path: decodes K/V into caller `kd`/`vd` [seq,dim] scratch
    // then runs the same causal windowed attention — the bit-exact verification
    // baseline for the fused path (SDD-401 phase 4 oracle), not a serving path.
    #[allow(clippy::too_many_arguments)]
    fn cf_kv_attn_dense_async(
        kw: *const u32,
        kb: *const i32,
        kl: *const i32,
        kmax: c_int,
        vw: *const u32,
        vb: *const i32,
        vl: *const i32,
        vmax: c_int,
        kscale: *const f32,
        vscale: *const f32,
        q: *const f32,
        kd: *mut f32,
        vd: *mut f32,
        out: *mut f32,
        seq: c_int,
        dim: c_int,
        nq: c_int,
        window: c_int,
        block: c_int,
        zero: c_int,
        sscale: f32,
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

    // --- chromofold_search.h: host-pointer FM-search (device marshalling inside the engine) ---

    fn cf_fm_host_load(cffm: *const u8, nbytes: usize, out: *mut *mut CfFmHostIndex) -> i32;

    fn cf_fm_host_count(
        ix: *const CfFmHostIndex,
        pat: *const i32,
        pstart: *const i32,
        plen: *const i32,
        npat: u32,
        counts_out: *mut u32,
    ) -> i32;

    fn cf_fm_host_ranges(
        ix: *const CfFmHostIndex,
        pat: *const i32,
        pstart: *const i32,
        plen: *const i32,
        npat: u32,
        lo_out: *mut i32,
        hi_out: *mut i32,
    ) -> i32;

    fn cf_fm_host_locate(
        ix: *const CfFmHostIndex,
        rows: *const i32,
        nocc: u32,
        pos_out: *mut i32,
    ) -> i32;

    fn cf_fm_host_free(ix: *mut CfFmHostIndex);

    // --- chromofold_search.h: device-native path (P5) — resident buffers, zero host round-trip ---

    fn cf_fm_host_view(ix: *const CfFmHostIndex, out: *mut CfFmView) -> i32;

    fn cf_device_alloc(nbytes: usize, out: *mut *mut c_void) -> i32;
    fn cf_device_free(dptr: *mut c_void);
    fn cf_device_h2d(ddst: *mut c_void, hsrc: *const c_void, nbytes: usize) -> i32;
    fn cf_device_d2h(hdst: *mut c_void, dsrc: *const c_void, nbytes: usize) -> i32;

    fn cf_stream_create(out: *mut *mut c_void) -> i32;
    fn cf_stream_destroy(stream: *mut c_void);
    fn cf_stream_sync(stream: *mut c_void) -> i32;
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

/// Fused compressed-KV attention (SDD-401 phase 4 target): causal windowed
/// attention over block-Huffman-coded int K/V, decoding + dequantizing each
/// attended value inside the kernel so no dense KV buffer is materialized —
/// the folded-KV serving path (~8× less KV VRAM).
///
/// `kw`/`kb`/`kl`/`kmax` and `vw`/`vb`/`vl`/`vmax` are the K/V code words, block
/// bit-offsets, decode lookup tables, and max symbol; `kscale` (`dim`) / `vscale`
/// (`seq`) are dequant scales; `q`/`out` are `[nq, dim]` row-major. `zero` is the
/// pad/zero symbol, `sscale` the softmax scale, `window` the causal window
/// (`0` = full causal).
///
/// # Safety
/// All pointers are DEVICE allocations of the documented shape, live for the
/// async call; `stream` is a valid `cudaStream_t` or null. The kernel allocates
/// nothing and does not synchronize.
#[cfg(feature = "linked")]
#[allow(clippy::too_many_arguments)]
pub unsafe fn kv_attn_fused_async(
    kw: *const u32,
    kb: *const i32,
    kl: *const i32,
    kmax: c_int,
    vw: *const u32,
    vb: *const i32,
    vl: *const i32,
    vmax: c_int,
    kscale: *const f32,
    vscale: *const f32,
    q: *const f32,
    out: *mut f32,
    seq: c_int,
    dim: c_int,
    nq: c_int,
    window: c_int,
    block: c_int,
    zero: c_int,
    sscale: f32,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_kv_attn_fused_async(
            kw, kb, kl, kmax, vw, vb, vl, vmax, kscale, vscale, q, out, seq, dim, nq, window,
            block, zero, sscale, stream,
        )
    })
}

/// Dense-reference KV attention — decodes K/V into caller-provided `kd`/`vd`
/// `[seq, dim]` scratch, then runs the same causal windowed attention. The
/// **bit-exact verification baseline** for [`kv_attn_fused_async`] (SDD-401
/// phase 4 oracle) — proves the fused path matches dense and quantifies the
/// memory it avoids; not the preferred serving path.
///
/// # Safety
/// Same contract as [`kv_attn_fused_async`], plus `kd`/`vd` are writable device
/// `[seq, dim]` scratch buffers.
#[cfg(feature = "linked")]
#[allow(clippy::too_many_arguments)]
pub unsafe fn kv_attn_dense_async(
    kw: *const u32,
    kb: *const i32,
    kl: *const i32,
    kmax: c_int,
    vw: *const u32,
    vb: *const i32,
    vl: *const i32,
    vmax: c_int,
    kscale: *const f32,
    vscale: *const f32,
    q: *const f32,
    kd: *mut f32,
    vd: *mut f32,
    out: *mut f32,
    seq: c_int,
    dim: c_int,
    nq: c_int,
    window: c_int,
    block: c_int,
    zero: c_int,
    sscale: f32,
    stream: *mut c_void,
) -> CfStatus {
    CfStatus::from_raw(unsafe {
        cf_kv_attn_dense_async(
            kw, kb, kl, kmax, vw, vb, vl, vmax, kscale, vscale, q, kd, vd, out, seq, dim, nq,
            window, block, zero, sscale, stream,
        )
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

// --- host-pointer FM-search wrappers (no cudart on the caller; marshalling is in the engine) ---

/// Build a device-resident FM-index from a `.cffm` container blob. On [`CfStatus::Ok`],
/// `*out` owns device memory until [`fm_host_free`].
///
/// # Safety
/// `cffm` points to `nbytes` readable bytes; `out` is a valid writable
/// `*mut *mut CfFmHostIndex`. NULL is handled by the engine (returns
/// `InvalidArgument` before any CUDA call).
#[cfg(feature = "linked")]
pub unsafe fn fm_host_load(
    cffm: *const u8,
    nbytes: usize,
    out: *mut *mut CfFmHostIndex,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_host_load(cffm, nbytes, out) })
}

/// Count occurrences of each of `npat` patterns (host arrays: `pat` flattened,
/// per-pattern `pstart`/`plen`). `counts_out` is host memory of length `npat`.
///
/// # Safety
/// `ix` a live handle from [`fm_host_load`]; `pat`/`pstart`/`plen`/`counts_out`
/// readable/writable host arrays of the stated lengths.
#[cfg(feature = "linked")]
pub unsafe fn fm_host_count(
    ix: *const CfFmHostIndex,
    pat: *const i32,
    pstart: *const i32,
    plen: *const i32,
    npat: u32,
    counts_out: *mut u32,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_host_count(ix, pat, pstart, plen, npat, counts_out) })
}

/// Suffix-array `[lo, hi)` interval per pattern (host in/out, length `npat`).
///
/// # Safety
/// As [`fm_host_count`]; `lo_out`/`hi_out` host arrays of length `npat`.
#[allow(clippy::too_many_arguments)]
#[cfg(feature = "linked")]
pub unsafe fn fm_host_ranges(
    ix: *const CfFmHostIndex,
    pat: *const i32,
    pstart: *const i32,
    plen: *const i32,
    npat: u32,
    lo_out: *mut i32,
    hi_out: *mut i32,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_host_ranges(ix, pat, pstart, plen, npat, lo_out, hi_out) })
}

/// Text position of each of `nocc` suffix-array row indices in `rows` (host in/out).
///
/// # Safety
/// `ix` live; `rows`/`pos_out` host arrays of length `nocc`.
#[cfg(feature = "linked")]
pub unsafe fn fm_host_locate(
    ix: *const CfFmHostIndex,
    rows: *const i32,
    nocc: u32,
    pos_out: *mut i32,
) -> CfStatus {
    CfStatus::from_raw(unsafe { cf_fm_host_locate(ix, rows, nocc, pos_out) })
}

/// Release a device-resident index from [`fm_host_load`].
///
/// # Safety
/// `ix` must be a handle from [`fm_host_load`] not already freed; unused after.
#[cfg(feature = "linked")]
pub unsafe fn fm_host_free(ix: *mut CfFmHostIndex) {
    unsafe { cf_fm_host_free(ix) }
}

/// A device-resident FM-index built from a `.cffm` blob, queried with plain host
/// slices — the **safe** GPU search surface. It owns the opaque [`CfFmHostIndex`],
/// frees it on drop, and no `unsafe` or device pointer crosses its API (the engine
/// does all host↔device marshalling). Because [`sovereign-chromofold`] forbids
/// `unsafe`, this safe RAII wrapper over the FFI lives here, the sanctioned carve-out.
///
/// Build once (P9 build ≠ query), then `count`/`ranges`/`locate` many times. Pattern
/// symbols are token ids already shifted into the sentinel alphabet the backward
/// search consumes (the same convention the `.cffm` fixtures store).
#[cfg(feature = "linked")]
pub struct HostFmIndex {
    raw: *mut CfFmHostIndex,
}

#[cfg(feature = "linked")]
impl HostFmIndex {
    /// Build a device-resident FM-index from a `.cffm` container blob.
    pub fn load(cffm: &[u8]) -> Result<Self, CfStatus> {
        let mut raw: *mut CfFmHostIndex = core::ptr::null_mut();
        // Safety: `cffm` is a valid slice; `&mut raw` is a valid out-pointer.
        let st = unsafe { fm_host_load(cffm.as_ptr(), cffm.len(), &mut raw) };
        match st {
            CfStatus::Ok if !raw.is_null() => Ok(Self { raw }),
            CfStatus::Ok => Err(CfStatus::Cuda), // Ok but null handle: treat as engine failure, never fabricate
            other => Err(other),
        }
    }

    /// Count occurrences of each pattern (flattened `pat`, per-pattern `pstart`/`plen`).
    /// One count per pattern; `pstart`/`plen` must be equal length.
    pub fn count(&self, pat: &[i32], pstart: &[i32], plen: &[i32]) -> Result<Vec<u32>, CfStatus> {
        if pstart.len() != plen.len() {
            return Err(CfStatus::InvalidArgument);
        }
        let npat = pstart.len();
        let mut out = vec![0u32; npat];
        // Safety: live handle; every slice outlives the synchronous call.
        let st = unsafe {
            fm_host_count(
                self.raw,
                pat.as_ptr(),
                pstart.as_ptr(),
                plen.as_ptr(),
                npat as u32,
                out.as_mut_ptr(),
            )
        };
        if st == CfStatus::Ok { Ok(out) } else { Err(st) }
    }

    /// Suffix-array `[lo, hi)` interval per pattern (occurrences = `hi - lo`).
    pub fn ranges(
        &self,
        pat: &[i32],
        pstart: &[i32],
        plen: &[i32],
    ) -> Result<(Vec<i32>, Vec<i32>), CfStatus> {
        if pstart.len() != plen.len() {
            return Err(CfStatus::InvalidArgument);
        }
        let npat = pstart.len();
        let mut lo = vec![0i32; npat];
        let mut hi = vec![0i32; npat];
        // Safety: live handle; slices outlive the call.
        let st = unsafe {
            fm_host_ranges(
                self.raw,
                pat.as_ptr(),
                pstart.as_ptr(),
                plen.as_ptr(),
                npat as u32,
                lo.as_mut_ptr(),
                hi.as_mut_ptr(),
            )
        };
        if st == CfStatus::Ok {
            Ok((lo, hi))
        } else {
            Err(st)
        }
    }

    /// Text position of each suffix-array row index in `rows`.
    pub fn locate(&self, rows: &[i32]) -> Result<Vec<i32>, CfStatus> {
        let mut out = vec![0i32; rows.len()];
        // Safety: live handle; slices outlive the call.
        let st =
            unsafe { fm_host_locate(self.raw, rows.as_ptr(), rows.len() as u32, out.as_mut_ptr()) };
        if st == CfStatus::Ok { Ok(out) } else { Err(st) }
    }
}

#[cfg(feature = "linked")]
impl Drop for HostFmIndex {
    fn drop(&mut self) {
        // Safety: `raw` came from a successful `fm_host_load` and is freed exactly once.
        unsafe { fm_host_free(self.raw) };
    }
}

// ---- Device-native path (P5): resident device buffers, zero host round-trip in the query loop ----

/// A resident device buffer of `len` elements of `T`, owned via the engine's
/// `cf_device_*` ABI helpers (so the caller links no cudart). Allocated on the device,
/// freed on drop. Upload/download move data host↔device explicitly — a device-resident
/// consumer keeps the buffer and skips the download. Not `Send`/`Sync`: it names device
/// memory bound to the engine's context.
#[cfg(feature = "linked")]
pub struct DeviceBuffer<T: Copy> {
    ptr: *mut c_void,
    len: usize,
    _t: core::marker::PhantomData<T>,
}

#[cfg(feature = "linked")]
impl<T: Copy> DeviceBuffer<T> {
    /// Allocate an (uninitialized) device buffer of `len` elements.
    pub fn with_len(len: usize) -> Result<Self, CfStatus> {
        let mut ptr: *mut c_void = core::ptr::null_mut();
        // Safety: `&mut ptr` is a valid out-pointer; the engine allocates device memory.
        let st = CfStatus::from_raw(unsafe {
            cf_device_alloc(len * core::mem::size_of::<T>(), &mut ptr)
        });
        match st {
            CfStatus::Ok if !ptr.is_null() => Ok(Self {
                ptr,
                len,
                _t: core::marker::PhantomData,
            }),
            CfStatus::Ok => Err(CfStatus::Cuda), // Ok but null: engine failure, never fabricate
            other => Err(other),
        }
    }

    /// Allocate and upload `host` in one step.
    pub fn from_host(host: &[T]) -> Result<Self, CfStatus> {
        let mut b = Self::with_len(host.len())?;
        b.upload(host)?;
        Ok(b)
    }

    /// Upload `host` (length must equal the buffer) host→device.
    pub fn upload(&mut self, host: &[T]) -> Result<(), CfStatus> {
        if host.len() != self.len {
            return Err(CfStatus::InvalidArgument);
        }
        if self.len == 0 {
            return Ok(());
        }
        // Safety: `ptr` is our live buffer of `len*size_of::<T>()` bytes; `host` is that long.
        let st = CfStatus::from_raw(unsafe {
            cf_device_h2d(
                self.ptr,
                host.as_ptr() as *const c_void,
                self.len * core::mem::size_of::<T>(),
            )
        });
        if st == CfStatus::Ok { Ok(()) } else { Err(st) }
    }

    /// Download the buffer device→host into a fresh `Vec`.
    pub fn to_vec(&self) -> Result<Vec<T>, CfStatus>
    where
        T: Default,
    {
        let mut out = vec![T::default(); self.len];
        if self.len > 0 {
            // Safety: `out` is `len` elements; `ptr` is our live buffer of the same byte length.
            let st = CfStatus::from_raw(unsafe {
                cf_device_d2h(
                    out.as_mut_ptr() as *mut c_void,
                    self.ptr,
                    self.len * core::mem::size_of::<T>(),
                )
            });
            if st != CfStatus::Ok {
                return Err(st);
            }
        }
        Ok(out)
    }

    /// Element count.
    #[must_use]
    pub fn len(&self) -> usize {
        self.len
    }
    /// Whether the buffer holds zero elements.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    fn dptr(&self) -> *mut c_void {
        self.ptr
    }
}

#[cfg(feature = "linked")]
impl<T: Copy> Drop for DeviceBuffer<T> {
    fn drop(&mut self) {
        // Safety: `ptr` came from a successful `cf_device_alloc`, freed exactly once.
        unsafe { cf_device_free(self.ptr) };
    }
}

/// A device stream owned via the engine ABI. Drops via `cf_stream_destroy`. Queries run
/// on it asynchronously; call [`Stream::sync`] before reading a result buffer back.
#[cfg(feature = "linked")]
pub struct Stream {
    ptr: *mut c_void,
}

#[cfg(feature = "linked")]
impl Stream {
    /// Create a fresh device stream.
    pub fn new() -> Result<Self, CfStatus> {
        let mut ptr: *mut c_void = core::ptr::null_mut();
        // Safety: `&mut ptr` is a valid out-pointer.
        let st = CfStatus::from_raw(unsafe { cf_stream_create(&mut ptr) });
        match st {
            CfStatus::Ok if !ptr.is_null() => Ok(Self { ptr }),
            CfStatus::Ok => Err(CfStatus::Cuda),
            other => Err(other),
        }
    }

    /// Block until all work previously enqueued on this stream has finished.
    pub fn sync(&self) -> Result<(), CfStatus> {
        // Safety: `ptr` is a live stream from `cf_stream_create`.
        let st = CfStatus::from_raw(unsafe { cf_stream_sync(self.ptr) });
        if st == CfStatus::Ok { Ok(()) } else { Err(st) }
    }

    fn raw(&self) -> *mut c_void {
        self.ptr
    }
}

#[cfg(feature = "linked")]
impl Drop for Stream {
    fn drop(&mut self) {
        // Safety: `ptr` came from a successful `cf_stream_create`, destroyed exactly once.
        unsafe { cf_stream_destroy(self.ptr) };
    }
}

/// A device-resident FM-index exposing the **device-native** search path (P5): queries run
/// over caller-owned resident [`DeviceBuffer`]s on a [`Stream`], writing results to a
/// resident buffer — no host round-trip in the loop. Owns a [`HostFmIndex`] (the resident
/// index) and caches its [`CfFmView`], whose device pointers stay valid for `self`.
#[cfg(feature = "linked")]
pub struct DeviceFmIndex {
    /// Keep-alive guard: owns the resident index, so every device pointer in `view` stays
    /// valid for `self`. Read only at construction; its `Drop` frees the index.
    #[allow(dead_code)]
    inner: HostFmIndex,
    view: CfFmView,
}

#[cfg(feature = "linked")]
impl DeviceFmIndex {
    /// Build from a `.cffm` blob and take the resident device view.
    pub fn load(cffm: &[u8]) -> Result<Self, CfStatus> {
        let inner = HostFmIndex::load(cffm)?;
        let mut view = core::mem::MaybeUninit::<CfFmView>::uninit();
        // Safety: `inner.raw` is a live host index; `view` is a valid out-pointer.
        let st = CfStatus::from_raw(unsafe { cf_fm_host_view(inner.raw, view.as_mut_ptr()) });
        if st != CfStatus::Ok {
            return Err(st);
        }
        // Safety: on Ok, cf_fm_host_view wrote a fully-initialized CfFmView.
        Ok(Self {
            inner,
            view: unsafe { view.assume_init() },
        })
    }

    /// BWT length `n` (`|s|`) of the resident index.
    #[must_use]
    pub fn n(&self) -> i32 {
        self.view.n
    }
    /// Alphabet size (incl. sentinel).
    #[must_use]
    pub fn sigma(&self) -> i32 {
        self.view.sigma
    }

    /// Count each of `npat` patterns (device-resident `pat`/`pstart`/`plen`), writing
    /// `npat` counts into `out` on `stream`. Asynchronous: `stream.sync()` before reading
    /// `out`. No host copy.
    pub fn count_into(
        &self,
        pat: &DeviceBuffer<i32>,
        pstart: &DeviceBuffer<i32>,
        plen: &DeviceBuffer<i32>,
        out: &mut DeviceBuffer<u32>,
        npat: usize,
        stream: &Stream,
    ) -> Result<(), CfStatus> {
        if pstart.len() < npat || plen.len() < npat || out.len() < npat {
            return Err(CfStatus::InvalidArgument);
        }
        // Safety: view pointers owned by `self.inner`; buffers live for the call; stream valid.
        let st = CfStatus::from_raw(unsafe {
            cf_fm_count_async(
                self.view,
                pat.dptr() as *const i32,
                pstart.dptr() as *const i32,
                plen.dptr() as *const i32,
                out.dptr() as *mut u32,
                npat,
                stream.raw(),
            )
        });
        if st == CfStatus::Ok { Ok(()) } else { Err(st) }
    }

    /// Suffix-array `[lo, hi)` per pattern into resident `lo_out`/`hi_out` on `stream`.
    #[allow(clippy::too_many_arguments)]
    pub fn ranges_into(
        &self,
        pat: &DeviceBuffer<i32>,
        pstart: &DeviceBuffer<i32>,
        plen: &DeviceBuffer<i32>,
        lo_out: &mut DeviceBuffer<i32>,
        hi_out: &mut DeviceBuffer<i32>,
        npat: usize,
        stream: &Stream,
    ) -> Result<(), CfStatus> {
        if pstart.len() < npat || plen.len() < npat || lo_out.len() < npat || hi_out.len() < npat {
            return Err(CfStatus::InvalidArgument);
        }
        // Safety: as `count_into`.
        let st = CfStatus::from_raw(unsafe {
            cf_fm_ranges_async(
                self.view,
                pat.dptr() as *const i32,
                pstart.dptr() as *const i32,
                plen.dptr() as *const i32,
                lo_out.dptr() as *mut i32,
                hi_out.dptr() as *mut i32,
                npat,
                stream.raw(),
            )
        });
        if st == CfStatus::Ok { Ok(()) } else { Err(st) }
    }

    /// Text position of each of `nocc` suffix-array rows (`rows`) into `out` on `stream`.
    pub fn locate_into(
        &self,
        rows: &DeviceBuffer<i32>,
        out: &mut DeviceBuffer<i32>,
        nocc: usize,
        stream: &Stream,
    ) -> Result<(), CfStatus> {
        if rows.len() < nocc || out.len() < nocc {
            return Err(CfStatus::InvalidArgument);
        }
        // Safety: as `count_into`.
        let st = CfStatus::from_raw(unsafe {
            cf_fm_locate_async(
                self.view,
                rows.dptr() as *const i32,
                out.dptr() as *mut i32,
                nocc,
                stream.raw(),
            )
        });
        if st == CfStatus::Ok { Ok(()) } else { Err(st) }
    }
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
    fn fm_host_index_is_opaque_zero_sized() {
        // The host handle is an opaque FFI type: the caller never sees its layout, so it
        // must be a ZST (only the engine allocates/dereferences it). No GPU needed.
        assert_eq!(size_of::<CfFmHostIndex>(), 0);
        assert_eq!(align_of::<CfFmHostIndex>(), 1);
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
