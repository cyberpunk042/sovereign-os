//! `fm` — a CPU-native FM-index (provenance-B, SDD-400 Q-400-F).
//!
//! A self-contained, `unsafe`-free Rust port of ChromoFold's compressed-domain
//! search, the sibling of the GPU engine (provenance-A, `sovereign-chromofold-sys`):
//! same answers, no GPU, no native library, always available. It builds the
//! Burrows–Wheeler transform of a token stream (via a suffix array), a cumulative
//! symbol table (`C`) and a rank table (`Occ`), and answers:
//!
//! - [`FmIndex::count`]  — occurrences of a pattern (FM backward search),
//! - [`FmIndex::ranges`] — the suffix-array `[lo, hi)` interval,
//! - [`FmIndex::locate`] — the text positions of every occurrence,
//! - [`FmIndex::predict`] — the derived next-token n-gram distribution.
//!
//! **Reference-grade, not the fast path.** Correctness over speed: the suffix
//! array is a direct suffix-comparison sort (O(n² log n)) and `Occ` is a dense
//! `σ·n` table. That is deliberate — this is the CPU *reference* backend, proven
//! correct against a naive substring oracle (every correct FM-index, ChromoFold's
//! included, agrees with it). A production build uses provenance-A (the GPU
//! engine) or a wavelet-tree rank; this is the honest, verifiable floor.

use std::collections::BTreeMap;

/// A CPU-native FM-index over a token stream (provenance-B).
#[derive(Debug, Clone)]
pub struct FmIndex {
    /// Length of the sentinel-terminated sequence (`orig_len + 1`).
    n: usize,
    /// Original token-stream length (without the sentinel).
    orig_len: usize,
    /// Suffix array over the sentinel-terminated remapped sequence.
    sa: Vec<u32>,
    /// `C[sym]` = number of sequence symbols strictly less than `sym`
    /// (symbols are `0`=sentinel and `1..=sigma`; length `sigma + 2`).
    c: Vec<usize>,
    /// `occ[sym][i]` = count of `sym` in `bwt[0..i]` (`(sigma+1) × (n+1)`).
    occ: Vec<Vec<usize>>,
    /// Original token → compact symbol id (`1..=sigma`); the sentinel (`0`) is
    /// never a real token, so an absent token means zero occurrences.
    remap: BTreeMap<u32, usize>,
    /// The original tokens, kept for [`FmIndex::predict`].
    orig: Vec<u32>,
}

/// Direct-comparison suffix array of a sentinel-terminated sequence. O(n² log n),
/// deliberately simple so it is obviously correct (the reference contract).
fn build_sa(s: &[u32]) -> Vec<u32> {
    let n = s.len();
    let mut sa: Vec<u32> = (0..n as u32).collect();
    sa.sort_by(|&a, &b| s[a as usize..].cmp(&s[b as usize..]));
    sa
}

impl FmIndex {
    /// Build the index over `tokens`. An empty stream is valid (every query
    /// returns zero) — no panic.
    #[must_use]
    pub fn build(tokens: &[u32]) -> Self {
        let orig_len = tokens.len();

        // Compact the distinct tokens to symbols 1..=sigma (sorted); 0 = sentinel.
        let mut distinct: Vec<u32> = tokens.to_vec();
        distinct.sort_unstable();
        distinct.dedup();
        let remap: BTreeMap<u32, usize> = distinct
            .iter()
            .enumerate()
            .map(|(i, &t)| (t, i + 1))
            .collect();
        let sigma = distinct.len();

        // Sentinel-terminated remapped sequence.
        let mut s: Vec<u32> = tokens.iter().map(|t| remap[t] as u32).collect();
        s.push(0);
        let n = s.len();

        let sa = build_sa(&s);
        let bwt: Vec<u32> = sa.iter().map(|&i| s[(i as usize + n - 1) % n]).collect();

        // C-table: total[sym] then prefix-sum → c[sym] = #symbols < sym.
        let mut total = vec![0usize; sigma + 1];
        for &x in &s {
            total[x as usize] += 1;
        }
        let mut c = vec![0usize; sigma + 2];
        for sym in 0..=sigma {
            c[sym + 1] = c[sym] + total[sym];
        }

        // Occ table: occ[sym][i] = count of sym in bwt[0..i].
        let mut occ = vec![vec![0usize; n + 1]; sigma + 1];
        for i in 0..n {
            for sym in 0..=sigma {
                occ[sym][i + 1] = occ[sym][i];
            }
            occ[bwt[i] as usize][i + 1] += 1;
        }

        Self {
            n,
            orig_len,
            sa,
            c,
            occ,
            remap,
            orig: tokens.to_vec(),
        }
    }

    /// The suffix-array `[lo, hi)` interval matching `pattern`, or `None` when the
    /// pattern is empty or does not occur. `count == hi - lo`.
    #[must_use]
    pub fn ranges(&self, pattern: &[u32]) -> Option<(usize, usize)> {
        if pattern.is_empty() {
            return None; // empty-pattern semantics are ambiguous; not supported
        }
        let mut lo = 0usize;
        let mut hi = self.n;
        for &t in pattern.iter().rev() {
            let sym = *self.remap.get(&t)?; // token absent → zero occurrences
            lo = self.c[sym] + self.occ[sym][lo];
            hi = self.c[sym] + self.occ[sym][hi];
            if lo >= hi {
                return None;
            }
        }
        Some((lo, hi))
    }

    /// Number of occurrences of `pattern` (FM backward search).
    #[must_use]
    pub fn count(&self, pattern: &[u32]) -> u64 {
        self.ranges(pattern).map_or(0, |(lo, hi)| (hi - lo) as u64)
    }

    /// Text positions of every occurrence of `pattern`, ascending.
    #[must_use]
    pub fn locate(&self, pattern: &[u32]) -> Vec<usize> {
        match self.ranges(pattern) {
            None => Vec::new(),
            Some((lo, hi)) => {
                let mut v: Vec<usize> = (lo..hi).map(|r| self.sa[r] as usize).collect();
                v.sort_unstable();
                v
            }
        }
    }

    /// The derived next-token distribution after `context` — the on-CPU n-gram
    /// draft model: over every occurrence of `context`, tally the following token
    /// and normalize. Returned highest-probability first (ties by token id).
    #[must_use]
    pub fn predict(&self, context: &[u32]) -> Vec<(u32, f32)> {
        let clen = context.len();
        let mut counts: BTreeMap<u32, usize> = BTreeMap::new();
        let mut total = 0usize;
        for p in self.locate(context) {
            let nxt = p + clen;
            if nxt < self.orig_len {
                *counts.entry(self.orig[nxt]).or_default() += 1;
                total += 1;
            }
        }
        if total == 0 {
            return Vec::new();
        }
        let mut v: Vec<(u32, f32)> = counts
            .into_iter()
            .map(|(t, c)| (t, c as f32 / total as f32))
            .collect();
        v.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.0.cmp(&b.0))
        });
        v
    }

    /// Original token-stream length (without the sentinel).
    #[must_use]
    pub fn len(&self) -> usize {
        self.orig_len
    }

    /// Whether the indexed token stream is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.orig_len == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The unarguable oracle: naive sliding-window substring search.
    fn naive_count(text: &[u32], pat: &[u32]) -> u64 {
        if pat.is_empty() || pat.len() > text.len() {
            return 0;
        }
        (0..=text.len() - pat.len())
            .filter(|&i| &text[i..i + pat.len()] == pat)
            .count() as u64
    }
    fn naive_locate(text: &[u32], pat: &[u32]) -> Vec<usize> {
        if pat.is_empty() || pat.len() > text.len() {
            return Vec::new();
        }
        (0..=text.len() - pat.len())
            .filter(|&i| &text[i..i + pat.len()] == pat)
            .collect()
    }

    #[test]
    fn matches_the_naive_oracle_on_a_known_case() {
        // "abracadabra"-style token stream.
        let text: Vec<u32> = "abracadabra".bytes().map(u32::from).collect();
        let idx = FmIndex::build(&text);
        for pat_s in ["a", "abra", "bra", "cad", "ra", "x", "abracadabra"] {
            let pat: Vec<u32> = pat_s.bytes().map(u32::from).collect();
            assert_eq!(idx.count(&pat), naive_count(&text, &pat), "count {pat_s:?}");
            assert_eq!(
                idx.locate(&pat),
                naive_locate(&text, &pat),
                "locate {pat_s:?}"
            );
        }
        assert_eq!(idx.count(&[b'a' as u32]), 5);
        assert_eq!(
            idx.locate(&"abra".bytes().map(u32::from).collect::<Vec<_>>()),
            vec![0, 7]
        );
    }

    #[test]
    fn matches_the_naive_oracle_on_randomized_streams() {
        // deterministic LCG — no external rng, reproducible.
        let mut state: u64 = 0x9e3779b97f4a7c15;
        let mut next = |m: u64| {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) % m
        };
        for _ in 0..200 {
            let n = (next(40) + 1) as usize;
            let sigma = (next(4) + 1) as u32; // small alphabet → many repeats
            let text: Vec<u32> = (0..n).map(|_| next(sigma as u64) as u32).collect();
            let idx = FmIndex::build(&text);
            for _ in 0..20 {
                let m = (next(5) + 1) as usize;
                let pat: Vec<u32> = (0..m).map(|_| next(sigma as u64) as u32).collect();
                assert_eq!(
                    idx.count(&pat),
                    naive_count(&text, &pat),
                    "count mismatch text={text:?} pat={pat:?}"
                );
                assert_eq!(
                    idx.locate(&pat),
                    naive_locate(&text, &pat),
                    "locate mismatch text={text:?} pat={pat:?}"
                );
            }
        }
    }

    #[test]
    fn edge_cases_do_not_panic() {
        let empty = FmIndex::build(&[]);
        assert_eq!(empty.count(&[1]), 0);
        assert!(empty.locate(&[1]).is_empty());
        assert_eq!(empty.count(&[]), 0);
        assert!(empty.is_empty());

        let single = FmIndex::build(&[42]);
        assert_eq!(single.count(&[42]), 1);
        assert_eq!(single.locate(&[42]), vec![0]);
        assert_eq!(single.count(&[7]), 0); // token never seen
        assert_eq!(single.len(), 1);
    }

    #[test]
    fn predict_gives_the_ngram_distribution() {
        // "a b a b a c" — after "a": b (twice), c (once) → b:2/3, c:1/3.
        let text = vec![0u32, 1, 0, 1, 0, 2];
        let idx = FmIndex::build(&text);
        let p = idx.predict(&[0]);
        assert_eq!(p[0], (1, 2.0 / 3.0));
        assert_eq!(p[1], (2, 1.0 / 3.0));
        // context with no in-range continuation → empty.
        assert!(idx.predict(&[2]).is_empty()); // 2 is last, nothing follows
        assert!(idx.predict(&[9]).is_empty()); // absent context
    }

    #[test]
    fn ranges_width_equals_count() {
        let text: Vec<u32> = "mississippi".bytes().map(u32::from).collect();
        let idx = FmIndex::build(&text);
        for pat_s in ["i", "ss", "issi", "p", "ppi"] {
            let pat: Vec<u32> = pat_s.bytes().map(u32::from).collect();
            let (lo, hi) = idx.ranges(&pat).unwrap();
            assert_eq!((hi - lo) as u64, idx.count(&pat));
        }
    }
}
