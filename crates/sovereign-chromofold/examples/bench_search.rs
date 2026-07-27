//! **Honest throughput positioning** (SDD-400, P1/P7): batched `count` on the same corpus,
//! provenance-A (GPU `HostFmSearch`) vs provenance-B (CPU-native `FmIndex`). Answers the
//! operator's "when does the GPU path pay off?" — and is written to report a NEGATIVE if
//! that is the truth at this scale.
//!
//! Honest measurement rules:
//! - Index build / load is EXCLUDED (P9 build ≠ query); only `count` is timed.
//! - provenance-A: one `HostFmSearch::count(K patterns)` = ONE host→device marshalling
//!   round-trip + ONE kernel doing K counts in parallel. This is the *host convenience
//!   layer* (per-call malloc/memcpy/sync), NOT the device-native async hot path — so a
//!   GPU loss here is a property of the marshalling layer, not the kernel. Stated plainly.
//! - provenance-B: K sequential CPU counts, single-threaded (it has no batch API).
//! - Warm up before timing; report the best of several repeats (least noise).
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run --release -p sovereign-chromofold --features linked --example bench_search -- \
//!       <parity.cffm> <parity.toks>

#[cfg(feature = "linked")]
fn read_tokens(path: &str) -> Vec<u32> {
    let raw = std::fs::read(path).expect("read .toks");
    let n = i64::from_le_bytes(raw[0..8].try_into().unwrap()) as usize;
    (0..n)
        .map(|i| {
            let o = 8 + i * 4;
            i32::from_le_bytes(raw[o..o + 4].try_into().unwrap()) as u32
        })
        .collect()
}

#[cfg(feature = "linked")]
fn best(reps: usize, mut f: impl FnMut()) -> f64 {
    use std::time::Instant;
    let mut b = f64::INFINITY;
    for _ in 0..reps {
        let t = Instant::now();
        f();
        b = b.min(t.elapsed().as_secs_f64());
    }
    b
}

#[cfg(feature = "linked")]
fn main() {
    use sovereign_chromofold::{FmIndex, HostFmSearch};

    let mut args = std::env::args().skip(1);
    let cffm = args.next().expect("usage: bench_search <cffm> <toks>");
    let toks_path = args.next().expect("usage: bench_search <cffm> <toks>");

    let toks = read_tokens(&toks_path);
    let blob = std::fs::read(&cffm).expect("read .cffm");
    let fm = FmIndex::build(&toks); // provenance-B (timing excludes this)
    let ix = HostFmSearch::load(&blob).expect("HostFmSearch::load"); // provenance-A (excluded)

    // A pool of real patterns (length 6, drawn across the corpus) — enough to fill the
    // largest batch. Deterministic stride, no rng.
    const PLEN: usize = 6;
    let pool: Vec<Vec<u32>> = (0..)
        .map(|k| (k * 613) % (toks.len() - PLEN))
        .take(4096)
        .map(|at| toks[at..at + PLEN].to_vec())
        .collect();

    // pre-flatten for provenance-A (shifted into the sentinel alphabet: symbol = token + 1).
    let flat: Vec<i32> = pool
        .iter()
        .flat_map(|p| p.iter().map(|&t| t as i32 + 1))
        .collect();

    // warm up both backends (CUDA context, caches).
    let _ = ix.count(&flat[..PLEN], &[0], &[PLEN as i32]);
    let _ = fm.count(&pool[0]);

    println!("throughput: batched count, provenance-A (GPU host layer) vs provenance-B (CPU)");
    println!(
        "  corpus {} tokens | pattern len {} | best of 9 | index build/load excluded",
        toks.len(),
        PLEN
    );
    println!(
        "  {:>6}  {:>12}  {:>12}  {:>12}  {:>12}  winner",
        "batch", "A GPU (ms)", "B CPU (ms)", "A pat/s", "B pat/s"
    );

    for &k in &[1usize, 16, 256, 1024, 4096] {
        let pstart: Vec<i32> = (0..k as i32).map(|i| i * PLEN as i32).collect();
        let plen: Vec<i32> = vec![PLEN as i32; k];
        let flat_k = &flat[..k * PLEN];

        let a = best(9, || {
            let _ = ix.count(flat_k, &pstart, &plen).expect("A.count");
        });
        let b = best(9, || {
            for p in &pool[..k] {
                std::hint::black_box(fm.count(p));
            }
        });
        let (a_ps, b_ps) = (k as f64 / a, k as f64 / b);
        let win = if a < b { "A (GPU)" } else { "B (CPU)" };
        println!(
            "  {:>6}  {:>12.3}  {:>12.3}  {:>12.0}  {:>12.0}  {}",
            k,
            a * 1e3,
            b * 1e3,
            a_ps,
            b_ps,
            win
        );
    }

    println!(
        "\nHonest caveats: A is the host convenience layer (per-call malloc/memcpy/sync), not the\n\
         device-native async API; B is single-threaded. Read the crossover, not the absolute win."
    );
}

#[cfg(not(feature = "linked"))]
fn main() {
    println!(
        "built without the `linked` feature — provenance-A absent, no throughput comparison to run."
    );
}
