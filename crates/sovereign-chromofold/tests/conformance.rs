//! Conformance seam (SDD-500) — the sovereign-os side of the native session's
//! "C-link conformance test", minus the link.
//!
//! It cannot link `libchromofold` (pre-implementation — SDD-500 Q-500-G), so it
//! verifies the parts that hold regardless of the engine being present: the
//! bound ABI constants match the committed C header, and the committed
//! `cf_wavelet_view` fixture satisfies every layout invariant the header
//! declares. When the engine is linkable, a `#[cfg(feature = "linked")]` sibling
//! adds the bit-for-bit golden-vector round-trip against the Warp oracle.

use serde::Deserialize;

/// The v0 `cf_wavelet_view` metadata fixture (committed source-of-truth).
#[derive(Debug, Deserialize)]
struct WaveletViewV0 {
    abi_version: u32,
    wavelet_sb: u32,
    token_count: u64,
    vocab: u64,
    levels: u32,
    nwords: u32,
    nblocks: u32,
    superblocks_per_level: u32,
    zero_counts_len: u32,
}

const FIXTURE: &str = include_str!("fixtures/wavelet_view_v0.json");

fn load() -> WaveletViewV0 {
    serde_json::from_str(FIXTURE).expect("fixture parses")
}

#[test]
fn bound_abi_constants_match_the_committed_header() {
    assert_eq!(sovereign_chromofold::ABI_VERSION, 0);
    assert_eq!(sovereign_chromofold::WAVELET_SB, 8);
}

#[test]
fn fixture_agrees_with_the_bound_abi() {
    let v = load();
    assert_eq!(v.abi_version, sovereign_chromofold::ABI_VERSION);
    assert_eq!(v.wavelet_sb, sovereign_chromofold::WAVELET_SB);
}

#[test]
fn fixture_satisfies_the_wavelet_view_layout_invariants() {
    let v = load();

    // levels == ceil(log2(vocab))
    let expected_levels = (u64::BITS - (v.vocab - 1).leading_zeros()).max(1);
    assert_eq!(
        v.levels, expected_levels,
        "levels must be ceil(log2(vocab))"
    );

    // nwords == ceil(n / 32)
    let expected_nwords = v.token_count.div_ceil(32) as u32;
    assert_eq!(v.nwords, expected_nwords, "nwords must be ceil(n / 32)");

    // superblocks has nblocks + 1 entries per level
    assert_eq!(
        v.superblocks_per_level,
        v.nblocks + 1,
        "superblocks_per_level must be nblocks + 1"
    );

    // one zero-count per level
    assert_eq!(
        v.zero_counts_len, v.levels,
        "zero_counts has exactly `levels` entries"
    );

    // nblocks covers nwords in CF_WAVELET_SB-word windows
    let expected_nblocks = v.nwords.div_ceil(v.wavelet_sb).max(1);
    assert_eq!(
        v.nblocks, expected_nblocks,
        "nblocks must cover nwords in CF_WAVELET_SB-word windows"
    );
}

/// One reference-format entry (mirrors the native `reference_fixtures`).
#[derive(Debug, Deserialize)]
struct RefFormat {
    ext: String,
    magic: String,
    version: u32,
    file: String,
}

#[derive(Debug, Deserialize)]
struct RefFormats {
    fixtures_subdir: String,
    formats: Vec<RefFormat>,
}

const REF_FORMATS: &str = include_str!("fixtures/reference_formats.json");

#[test]
fn reference_format_manifest_is_wellformed() {
    let m: RefFormats = serde_json::from_str(REF_FORMATS).expect("manifest parses");
    assert!(!m.formats.is_empty(), "manifest lists no formats");
    for f in &m.formats {
        assert_eq!(f.magic.len(), 4, "magic {:?} must be 4 bytes", f.magic);
        assert!(f.magic.is_ascii(), "magic {:?} must be ASCII", f.magic);
        assert!(f.version >= 1, "version must be >= 1 for {}", f.ext);
        assert!(
            f.ext.starts_with('.'),
            "ext {:?} must start with '.'",
            f.ext
        );
    }
}

#[test]
fn real_fixtures_match_the_header_seam_when_engine_root_present() {
    // The sovereign side of ../chromoFold packaging/seam_check.c, no GPU: when a
    // checkout is resident (CHROMOFOLD_ROOT / WARP_SHADERS_ROOT) and carries the
    // packaging fixtures, assert every reference blob's 4-byte magic + u32-LE
    // version match the committed manifest. Honest-degrade (skip) when the root or
    // the fixtures are absent — never a spurious failure, never a fabricated pass.
    let Some(root) = sovereign_chromofold::engine_root() else {
        eprintln!("engine root not resident; skipping real header-seam check (honest-degrade)");
        return;
    };
    let m: RefFormats = serde_json::from_str(REF_FORMATS).expect("manifest parses");
    let base = std::path::Path::new(&root).join(&m.fixtures_subdir);
    if !base.is_dir() {
        eprintln!(
            "no {} under {root}; skipping real header-seam check (honest-degrade)",
            m.fixtures_subdir
        );
        return;
    }
    for f in &m.formats {
        let path = base.join(&f.file);
        let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
        assert!(
            bytes.len() >= 8,
            "{} too short for an 8-byte header",
            path.display()
        );
        assert_eq!(
            &bytes[0..4],
            f.magic.as_bytes(),
            "magic mismatch in {}",
            path.display()
        );
        let ver = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        assert_eq!(ver, f.version, "version mismatch in {}", path.display());
    }
}
