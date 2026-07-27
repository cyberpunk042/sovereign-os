//! End-to-end smoke of the **device-native** (P5) search surface: resident device buffers,
//! `cf_fm_count_async` on a stream, zero host round-trip in the query loop. Proves the safe
//! `DeviceFmIndex`/`DeviceBuffer`/`Stream` path runs on the GPU and agrees with the FM count
//! invariant (single-symbol counts sum to `n`), downloading results only once at the end.
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run -p sovereign-chromofold --features linked --example device_search -- <path>.cffm

#[cfg(feature = "linked")]
fn main() {
    use sovereign_chromofold::{DeviceBuffer, DeviceFmIndex, Stream};

    let path = std::env::args()
        .nth(1)
        .expect("usage: device_search <path>.cffm");
    let blob = std::fs::read(&path).expect("read .cffm");

    let ix = DeviceFmIndex::load(&blob).expect("DeviceFmIndex::load");
    let (n, sigma) = (ix.n(), ix.sigma());

    // one length-1 pattern per symbol 0..sigma (0 is the sentinel): counts must sum to n.
    let pat: Vec<i32> = (0..sigma).collect();
    let pstart: Vec<i32> = (0..sigma).collect();
    let plen: Vec<i32> = vec![1; sigma as usize];
    let npat = sigma as usize;

    // Upload the query ONCE into resident buffers; allocate the result buffer once.
    let d_pat = DeviceBuffer::from_host(&pat).expect("upload pat");
    let d_pstart = DeviceBuffer::from_host(&pstart).expect("upload pstart");
    let d_plen = DeviceBuffer::from_host(&plen).expect("upload plen");
    let mut d_counts = DeviceBuffer::<u32>::with_len(npat).expect("alloc counts");
    let stream = Stream::new().expect("stream");

    // Run the kernel twice reusing the SAME resident buffers — the zero-copy hot loop.
    for _ in 0..2 {
        ix.count_into(&d_pat, &d_pstart, &d_plen, &mut d_counts, npat, &stream)
            .expect("count_into");
        stream.sync().expect("stream sync");
    }

    // Download exactly once, at the end.
    let counts = d_counts.to_vec().expect("download counts");
    let total: u64 = counts.iter().map(|&c| c as u64).sum();

    println!("device-native DeviceFmIndex smoke through libchromofold.so — {path}");
    println!("  index: n={n}  sigma={sigma}  (buffers resident, kernel run 2x, 1 download)");
    println!("  sum of single-symbol counts = {total}  (expected n = {n})");
    assert_eq!(
        total, n as u64,
        "FM count invariant violated — device-native search returned wrong results"
    );
    println!(
        "PASS — safe DeviceFmIndex ran zero-host-round-trip FM-search on the GPU (invariant holds)."
    );
}

#[cfg(not(feature = "linked"))]
fn main() {
    // The device-native path is inherently GPU-resident; there is no honest-degrade for it.
    println!(
        "built without the `linked` feature — device-native path needs the engine, nothing to run."
    );
}
