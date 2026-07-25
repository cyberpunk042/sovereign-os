//! End-to-end smoke of the **safe** provenance-A surface `sovereign_chromofold::HostFmSearch`
//! through a resident `libchromofold.so` (SDD-400 step 7). Unlike the sibling
//! `sovereign-chromofold-sys` `host_fm_smoke` (which drives the FFI wrapper directly),
//! this exercises the layer downstream code actually calls — the `unsafe`-free crate.
//!
//! It loads a `.cffm` blob, counts every single-symbol pattern, and checks the total
//! equals the text length `n` — a global FM invariant (each of the `n` positions starts
//! exactly one suffix), so it verifies real GPU results with no golden file.
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run -p sovereign-chromofold --features linked --example host_search_smoke -- <path>.cffm

#[cfg(feature = "linked")]
fn main() {
    use sovereign_chromofold::HostFmSearch;

    let path = std::env::args()
        .nth(1)
        .expect("usage: host_search_smoke <path>.cffm");
    let blob = std::fs::read(&path).expect("read .cffm");
    assert!(
        blob.len() >= 28 && &blob[0..4] == b"CFFM",
        "not a .cffm blob"
    );
    // header: magic[4] version[4] n[8] bits[4] vocab[4] sigma[4] ...
    let n = u64::from_le_bytes(blob[8..16].try_into().unwrap());
    let sigma = u32::from_le_bytes(blob[24..28].try_into().unwrap());

    let ix = HostFmSearch::load(&blob).expect("HostFmSearch::load");

    // one length-1 pattern per symbol s in 0..sigma (0 is the sentinel); every symbol
    // counted once covers all n positions, so the single-symbol counts sum to exactly n.
    let pat: Vec<i32> = (0..sigma as i32).collect();
    let pstart: Vec<i32> = (0..pat.len() as i32).collect();
    let plen: Vec<i32> = vec![1; pat.len()];
    let counts = ix.count(&pat, &pstart, &plen).expect("HostFmSearch::count");

    let total: u64 = counts.iter().map(|&c| c as u64).sum();
    println!("HostFmSearch (safe surface) smoke through libchromofold.so — {path}");
    println!(
        "  index: n={n}  sigma={sigma}  (loaded {} bytes)",
        blob.len()
    );
    println!("  sum of single-symbol counts = {total}  (expected n = {n})");
    assert_eq!(
        total, n,
        "FM count invariant violated — GPU search returned wrong results"
    );
    println!(
        "PASS — safe sovereign_chromofold::HostFmSearch ran FM-search on the GPU (invariant holds)."
    );
}

#[cfg(not(feature = "linked"))]
fn main() {
    // honest-degrade: without the engine linked, HostFmSearch::load refuses.
    use sovereign_chromofold::{HostFmSearch, HostSearchError};
    assert!(matches!(
        HostFmSearch::load(&[]),
        Err(HostSearchError::Unavailable)
    ));
    println!("built without the `linked` feature — HostFmSearch honest-degrades, nothing to run.");
}
