//! **Cross-backend parity** (SDD-400): prove provenance-A (GPU, `HostFmSearch` over a
//! `.cffm`) and provenance-B (CPU-native `FmIndex` over the raw token stream) return
//! *identical* `count` and `locate` on the **same corpus** — and that both match a naive
//! oracle. The crate docs claim "both backends must agree with the same oracle"; this is
//! the evidence, not the assertion.
//!
//! Two fixtures from chromoFold's native builder over one corpus (regenerate with
//! `make -C <chromoFold> parity-fixtures` — they are git-ignored, deterministic on seed 21):
//!   build_index parity.cfrw --n 50000 --vocab 48 --seed 21 --sa-sample 8 \
//!               --fm parity.cffm --dump-tokens parity.toks
//! `parity.toks` = raw `seq` (i64 count, then i32 tokens); `parity.cffm` = the FM-index
//! over the sentinel-shifted stream `s = (seq+1) ++ [0]`. So a provenance-A pattern symbol
//! is the provenance-B token id **+ 1** (0 is the sentinel).
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run -p sovereign-chromofold --features linked --example parity_smoke -- \
//!       <chromoFold>/packaging/fixtures/parity.cffm <chromoFold>/packaging/fixtures/parity.toks

#[cfg(feature = "linked")]
fn read_tokens(path: &str) -> Vec<u32> {
    let raw = std::fs::read(path).expect("read .toks");
    // header: i64 little-endian count, then `count` i32 tokens.
    let n = i64::from_le_bytes(raw[0..8].try_into().unwrap()) as usize;
    let mut toks = Vec::with_capacity(n);
    for i in 0..n {
        let o = 8 + i * 4;
        toks.push(i32::from_le_bytes(raw[o..o + 4].try_into().unwrap()) as u32);
    }
    toks
}

/// Naive occurrence positions of `pat` (raw token space) in `toks` — the oracle.
#[cfg(feature = "linked")]
fn naive_positions(toks: &[u32], pat: &[u32]) -> Vec<usize> {
    if pat.is_empty() || pat.len() > toks.len() {
        return vec![];
    }
    (0..=toks.len() - pat.len())
        .filter(|&i| &toks[i..i + pat.len()] == pat)
        .collect()
}

#[cfg(feature = "linked")]
fn main() {
    use sovereign_chromofold::{FmIndex, HostFmSearch};

    let mut args = std::env::args().skip(1);
    let cffm = args
        .next()
        .expect("usage: parity_smoke <parity.cffm> <parity.toks>");
    let toks_path = args
        .next()
        .expect("usage: parity_smoke <parity.cffm> <parity.toks>");

    let toks = read_tokens(&toks_path);
    let blob = std::fs::read(&cffm).expect("read .cffm");
    let fm = FmIndex::build(&toks); // provenance-B (CPU-native)
    let ix = HostFmSearch::load(&blob).expect("HostFmSearch::load"); // provenance-A (GPU)

    // Patterns I choose here (not the ones baked into the fixture): substrings drawn by a
    // fixed stride at several lengths (guaranteed ≥1 hit), plus deliberate misses to
    // exercise the zero-occurrence path on both backends.
    let mut patterns: Vec<Vec<u32>> = Vec::new();
    for &len in &[1usize, 2, 3, 5, 8, 13] {
        let mut at = 0usize;
        while at + len <= toks.len() && patterns.len() < 400 {
            patterns.push(toks[at..at + len].to_vec());
            at += 997; // coprime-ish stride for spread across the corpus
        }
    }
    // near-certain misses: a value one past the alphabet can never appear.
    let miss = *toks.iter().max().unwrap() + 1;
    for len in [2usize, 4, 7] {
        patterns.push(vec![miss; len]);
    }

    let (mut checked, mut zero_cases, mut max_occ) = (0usize, 0usize, 0u64);
    for pat in &patterns {
        // provenance-B: raw token ids.
        let b_count = fm.count(pat);
        let mut b_pos = fm.locate(pat);
        b_pos.sort_unstable();

        // provenance-A: same pattern shifted into the sentinel alphabet (+1).
        let shifted: Vec<i32> = pat.iter().map(|&t| t as i32 + 1).collect();
        let pstart = [0i32];
        let plen = [shifted.len() as i32];
        let a_count = ix.count(&shifted, &pstart, &plen).expect("A.count")[0] as u64;
        let (lo, hi) = ix.ranges(&shifted, &pstart, &plen).expect("A.ranges");
        let rows: Vec<i32> = (lo[0]..hi[0]).collect();
        let mut a_pos: Vec<usize> = ix
            .locate(&rows)
            .expect("A.locate")
            .into_iter()
            .map(|p| p as usize)
            .collect();
        a_pos.sort_unstable();

        // oracle.
        let mut o_pos = naive_positions(&toks, pat);
        o_pos.sort_unstable();
        let o_count = o_pos.len() as u64;

        assert_eq!(a_count, o_count, "provenance-A count != oracle for {pat:?}");
        assert_eq!(b_count, o_count, "provenance-B count != oracle for {pat:?}");
        assert_eq!(a_pos, o_pos, "provenance-A locate != oracle for {pat:?}");
        assert_eq!(b_pos, o_pos, "provenance-B locate != oracle for {pat:?}");

        checked += 1;
        if o_count == 0 {
            zero_cases += 1;
        }
        max_occ = max_occ.max(o_count);
    }

    println!("cross-backend parity through libchromofold.so");
    println!(
        "  corpus: {} tokens (vocab≤{})   fixture: {}",
        toks.len(),
        miss,
        cffm
    );
    println!(
        "  {checked} patterns checked ({zero_cases} zero-occurrence, max {max_occ} occ/pattern)"
    );
    println!("PASS — provenance-A (GPU) == provenance-B (CPU) == naive oracle, count AND locate.");
}

#[cfg(not(feature = "linked"))]
fn main() {
    // provenance-B alone is available with no engine; parity needs the GPU backend.
    use sovereign_chromofold::{HostFmSearch, HostSearchError};
    assert!(matches!(
        HostFmSearch::load(&[]),
        Err(HostSearchError::Unavailable)
    ));
    println!(
        "built without the `linked` feature — provenance-A absent, no cross-backend parity to run."
    );
}
