//! End-to-end smoke of the safe `HostFmIndex` through a resident `libchromofold.so`
//! (SDD-400 Lane A, the linked / provenance-A path). Loads a `.cffm` blob, then counts
//! every single-symbol pattern and checks the total equals the text length `n` — a
//! global FM invariant (each of the `n` non-sentinel positions starts exactly one
//! suffix), so it verifies real GPU search results with no golden file.
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run -p sovereign-chromofold-sys --features linked --example host_fm_smoke -- <path>.cffm

#[cfg(feature = "linked")]
fn main() {
    use sovereign_chromofold_sys::HostFmIndex;

    let path = std::env::args()
        .nth(1)
        .expect("usage: host_fm_smoke <path>.cffm");
    let blob = std::fs::read(&path).expect("read .cffm");
    assert!(
        blob.len() >= 28 && &blob[0..4] == b"CFFM",
        "not a .cffm blob"
    );
    // header: magic[4] version[4] n[8] bits[4] vocab[4] sigma[4] ...
    let n = u64::from_le_bytes(blob[8..16].try_into().unwrap());
    let sigma = u32::from_le_bytes(blob[24..28].try_into().unwrap());

    let ix = HostFmIndex::load(&blob).expect("HostFmIndex::load");

    // one length-1 pattern per symbol s in 0..sigma (0 is the sentinel). The BWT is the
    // length-`n` string s = (seq+1) ++ [sentinel], so every symbol counted once covers
    // all n positions: the single-symbol counts sum to exactly n.
    let pat: Vec<i32> = (0..sigma as i32).collect();
    let pstart: Vec<i32> = (0..pat.len() as i32).collect();
    let plen: Vec<i32> = vec![1; pat.len()];
    let counts = ix.count(&pat, &pstart, &plen).expect("HostFmIndex::count");

    let total: u64 = counts.iter().map(|&c| c as u64).sum();
    println!("HostFmIndex smoke through libchromofold.so — {path}");
    println!(
        "  index: n={n}  sigma={sigma}  (loaded {} bytes)",
        blob.len()
    );
    println!("  sum of single-symbol counts = {total}  (expected n = {n})");
    // every one of the n positions starts exactly one suffix => counts sum to n.
    assert_eq!(
        total, n,
        "FM count invariant violated — GPU search returned wrong results"
    );
    println!("PASS — safe HostFmIndex ran FM-search on the GPU and satisfies the count invariant.");
}

#[cfg(not(feature = "linked"))]
fn main() {
    println!("built without the `linked` feature — honest-degrade, nothing to run.");
}
