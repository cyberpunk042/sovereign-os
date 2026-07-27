//! **P5 payoff** (SDD-400): does the device-native path (resident buffers, zero host
//! round-trip) beat the host convenience layer (per-call malloc/memcpy/sync/free)? Batched
//! count on one corpus, three ways, honest timing:
//! - HOST     : `HostFmSearch::count` — full per-call marshalling (upload query, download result).
//! - DEVICE   : `DeviceFmIndex::count_into` — query uploaded ONCE (excluded), timed loop is
//!              kernel + `stream.sync()` only, result kept on device (the device-resident-consumer
//!              scenario). This is the P5 hot loop.
//! - CPU      : `FmIndex::count` — K sequential CPU counts (single-threaded reference).
//! Index build/load and the one-time device upload are EXCLUDED from the timed region (P9).
//!
//! Run (this box):
//!   RUSTFLAGS="-L <chromoFold>/packaging/build" \
//!   LD_LIBRARY_PATH="<chromoFold>/packaging/build:/usr/local/cuda/lib64" \
//!   cargo run --release -p sovereign-chromofold --features linked --example bench_search_device -- \
//!       <cffm> <toks>

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
    use sovereign_chromofold::{DeviceBuffer, DeviceFmIndex, FmIndex, HostFmSearch};

    let mut args = std::env::args().skip(1);
    let cffm = args
        .next()
        .expect("usage: bench_search_device <cffm> <toks>");
    let toks_path = args
        .next()
        .expect("usage: bench_search_device <cffm> <toks>");

    let toks = read_tokens(&toks_path);
    let blob = std::fs::read(&cffm).expect("read .cffm");
    let fm = FmIndex::build(&toks);
    let host = HostFmSearch::load(&blob).expect("HostFmSearch::load");
    let dev = DeviceFmIndex::load(&blob).expect("DeviceFmIndex::load");

    const PLEN: usize = 6;
    let pool: Vec<Vec<u32>> = (0..)
        .map(|k| (k * 613) % (toks.len() - PLEN))
        .take(4096)
        .map(|at| toks[at..at + PLEN].to_vec())
        .collect();
    // flattened + shifted (sentinel alphabet) once, for both A-variants.
    let flat: Vec<i32> = pool
        .iter()
        .flat_map(|p| p.iter().map(|&t| t as i32 + 1))
        .collect();
    let pstart_all: Vec<i32> = (0..4096i32).map(|i| i * PLEN as i32).collect();
    let plen_all: Vec<i32> = vec![PLEN as i32; 4096];

    println!(
        "P5 payoff: HOST layer vs DEVICE-native vs CPU (batched count, best of 9, build/load excluded)"
    );
    println!("  corpus {} tokens | pattern len {}", toks.len(), PLEN);
    println!(
        "  {:>6}  {:>11}  {:>11}  {:>11}   {:>10}  winner(GPU)",
        "batch", "HOST (ms)", "DEVICE (ms)", "CPU (ms)", "dev speedup"
    );

    for &k in &[1usize, 16, 256, 1024, 4096] {
        let flat_k = &flat[..k * PLEN];
        let pstart = &pstart_all[..k];
        let plen = &plen_all[..k];

        // DEVICE: upload the query ONCE (excluded), then time kernel + sync, result stays resident.
        let d_pat = DeviceBuffer::from_host(flat_k).expect("d_pat");
        let d_pstart = DeviceBuffer::from_host(pstart).expect("d_pstart");
        let d_plen = DeviceBuffer::from_host(plen).expect("d_plen");
        let mut d_counts = DeviceBuffer::<u32>::with_len(k).expect("d_counts");
        let stream = sovereign_chromofold::Stream::new().expect("stream");
        // warm up.
        dev.count_into(&d_pat, &d_pstart, &d_plen, &mut d_counts, k, &stream)
            .unwrap();
        stream.sync().unwrap();
        let _ = host.count(flat_k, pstart, plen);
        let _ = fm.count(&pool[0]);

        let d = best(9, || {
            dev.count_into(&d_pat, &d_pstart, &d_plen, &mut d_counts, k, &stream)
                .unwrap();
            stream.sync().unwrap();
        });
        let h = best(9, || {
            let _ = host.count(flat_k, pstart, plen).unwrap();
        });
        let c = best(9, || {
            for p in &pool[..k] {
                std::hint::black_box(fm.count(p));
            }
        });
        let win = if d <= h && d <= c {
            "DEVICE"
        } else if c <= h {
            "CPU"
        } else {
            "HOST"
        };
        println!(
            "  {:>6}  {:>11.3}  {:>11.3}  {:>11.3}   {:>9.2}x  {}",
            k,
            h * 1e3,
            d * 1e3,
            c * 1e3,
            h / d,
            win
        );
    }

    println!(
        "\nHonest: DEVICE excludes the one-time query upload (the device-resident-consumer case) and keeps\n\
         results on device; HOST pays upload+download every call; CPU is single-threaded. The HOST/DEVICE\n\
         ratio is the marshalling the P5 path removes from the hot loop."
    );
}

#[cfg(not(feature = "linked"))]
fn main() {
    println!(
        "built without the `linked` feature — device-native path needs the engine, nothing to run."
    );
}
