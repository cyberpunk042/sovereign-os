//! `fm` — a CPU-native FM-index (provenance-B, SDD-400 Q-400-F).
//!
//! A self-contained, `unsafe`-free Rust port of ChromoFold's compressed-domain
//! search, the sibling of the GPU engine (provenance-A, `sovereign-chromofold-sys`):
//! same answers, no GPU, no native library, always available. It builds the
//! Burrows–Wheeler transform of a token stream (via a suffix array), a cumulative
//! symbol table (`C`) and a wavelet-tree rank, and answers:
//!
//! - [`FmIndex::count`]  — occurrences of a pattern (FM backward search),
//! - [`FmIndex::ranges`] — the suffix-array `[lo, hi)` interval,
//! - [`FmIndex::locate`] — the text positions of every occurrence,
//! - [`FmIndex::predict`] — the derived next-token n-gram distribution.
//!
//! **Reference-grade, correctness-first — and it scales.** The suffix array is
//! prefix-doubling (O(n log² n)) and rank is a **wavelet tree** (O(log σ) per
//! query, O(n log σ) space) — the standard succinct FM-index structure — so the
//! index scales to real token vocabularies, not just small alphabets or tiny
//! test streams. The GPU hot path is still provenance-A; this is the honest,
//! verifiable CPU floor, proven correct against a naive substring oracle, a
//! brute-force suffix sort, and a naive rank — every correct FM-index
//! (ChromoFold's included) agrees with it.

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
    /// Wavelet tree over the BWT: `rank(sym, i)` = count of `sym` in `bwt[0..i]`
    /// in O(log σ) time, O(n log σ) space (replaces the dense σ·n `Occ`).
    wt: WaveletTree,
    /// Original token → compact symbol id (`1..=sigma`); the sentinel (`0`) is
    /// never a real token, so an absent token means zero occurrences.
    remap: BTreeMap<u32, usize>,
    /// The original tokens, kept for [`FmIndex::predict`].
    orig: Vec<u32>,
}

/// Suffix array of a sentinel-terminated sequence by **prefix doubling**
/// (O(n log² n)): sort suffixes by their first `2^r` symbols each round, using
/// the previous round's ranks as the comparison key, until every suffix has a
/// distinct rank. This replaces the earlier O(n² log n) direct-comparison sort,
/// so the CPU FM-index is usable on real (small-vocab) corpora, not just tiny
/// test streams. Verified against a brute-force suffix sort (tests) + the naive
/// substring oracle.
fn build_sa(s: &[u32]) -> Vec<u32> {
    let n = s.len();
    if n == 0 {
        return Vec::new();
    }
    let mut sa: Vec<u32> = (0..n as u32).collect();
    let mut rank: Vec<i64> = s.iter().map(|&x| x as i64).collect();
    let mut tmp = vec![0i64; n];
    let mut k = 1usize;
    loop {
        // Comparison key for suffix i at gap k: (rank[i], rank[i+k] or -1).
        let key = |i: usize| -> (i64, i64) { (rank[i], if i + k < n { rank[i + k] } else { -1 }) };
        sa.sort_by(|&a, &b| key(a as usize).cmp(&key(b as usize)));
        // Re-rank: equal keys share a rank, so ranks stay dense.
        tmp[sa[0] as usize] = 0;
        for w in 1..n {
            let prev = sa[w - 1] as usize;
            let cur = sa[w] as usize;
            tmp[cur] = tmp[prev] + i64::from(key(prev) < key(cur));
        }
        rank.copy_from_slice(&tmp);
        if rank[sa[n - 1] as usize] == n as i64 - 1 {
            break; // all suffixes distinctly ranked — SA is final
        }
        k <<= 1;
    }
    sa
}

/// A balanced wavelet tree over a symbol sequence, giving `rank(sym, i)` — the
/// count of `sym` in `seq[0..i]` — in O(log σ) time and O(n log σ) space. This is
/// the succinct rank structure a real FM-index uses; it replaces the dense σ·n
/// `Occ` table so the index scales to large token vocabularies, not just small
/// alphabets. Correctness is verified against a naive count (tests).
#[derive(Debug, Clone)]
struct WaveletTree {
    root: Option<Box<WtNode>>,
}

#[derive(Debug, Clone)]
struct WtNode {
    lo: u32,
    hi: u32,
    /// `prefix1[i]` = number of symbols among the first `i` arriving here that
    /// route RIGHT (symbol > mid). Empty for a leaf (`lo == hi`).
    prefix1: Vec<usize>,
    left: Option<Box<WtNode>>,
    right: Option<Box<WtNode>>,
}

impl WaveletTree {
    fn build(seq: &[u32], sigma_max: u32) -> Self {
        WaveletTree {
            root: Some(Box::new(WtNode::build(seq, 0, sigma_max))),
        }
    }

    /// Count of `sym` in the first `i` positions of the sequence.
    fn rank(&self, sym: u32, i: usize) -> usize {
        let mut node = self.root.as_deref();
        let mut pos = i;
        while let Some(nd) = node {
            if nd.lo == nd.hi {
                return pos; // leaf: pos = count of `sym` in seq[0..i]
            }
            let mid = nd.lo + (nd.hi - nd.lo) / 2;
            let ones = nd.prefix1[pos];
            if sym <= mid {
                pos -= ones; // rank0 — symbols routed left
                node = nd.left.as_deref();
            } else {
                pos = ones; // rank1 — symbols routed right
                node = nd.right.as_deref();
            }
        }
        pos
    }
}

impl WtNode {
    fn build(seq: &[u32], lo: u32, hi: u32) -> WtNode {
        if lo == hi {
            return WtNode {
                lo,
                hi,
                prefix1: Vec::new(),
                left: None,
                right: None,
            };
        }
        let mid = lo + (hi - lo) / 2;
        let mut prefix1 = Vec::with_capacity(seq.len() + 1);
        prefix1.push(0);
        let mut left_seq = Vec::new();
        let mut right_seq = Vec::new();
        let mut ones = 0usize;
        for &s in seq {
            if s > mid {
                ones += 1;
                right_seq.push(s);
            } else {
                left_seq.push(s);
            }
            prefix1.push(ones);
        }
        WtNode {
            lo,
            hi,
            prefix1,
            left: Some(Box::new(WtNode::build(&left_seq, lo, mid))),
            right: Some(Box::new(WtNode::build(&right_seq, mid + 1, hi))),
        }
    }
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

        // Wavelet tree over the BWT for O(log σ) rank (replaces the dense Occ).
        let wt = WaveletTree::build(&bwt, sigma as u32);

        Self {
            n,
            orig_len,
            sa,
            c,
            wt,
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
            lo = self.c[sym] + self.wt.rank(sym as u32, lo);
            hi = self.c[sym] + self.wt.rank(sym as u32, hi);
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

    /// Prompt-lookup speculative-decoding draft: the tokens that most recently
    /// followed the longest suffix (length `min_ngram..=max_ngram`) of the indexed
    /// stream that *also occurs earlier* in it — up to `max_draft` tokens.
    ///
    /// This is the FM-index realization of `sovereign-ngram-speculative`'s
    /// prompt-lookup draft (SDD-400's speculative-decoding use-case): the identical
    /// result, found by O(log) compressed-domain `locate` instead of an O(n) scan.
    /// Empty when nothing matches. A drop-in draft source for `sovereign-spec-decode`
    /// verification — proven equivalent to `NgramSpeculator::propose` in tests.
    #[must_use]
    pub fn propose_draft(&self, max_ngram: usize, min_ngram: usize, max_draft: usize) -> Vec<u32> {
        let ctx = &self.orig;
        let len = ctx.len();
        let max_ngram = max_ngram.max(1);
        let min_ngram = min_ngram.max(1);
        let hi = max_ngram.min(len.saturating_sub(1)); // need room before the suffix
        for n in (min_ngram..=hi).rev() {
            let suffix = &ctx[len - n..];
            // latest occurrence starting strictly before the current suffix (i < len - n)
            let start = self.locate(suffix).into_iter().rev().find(|&i| i < len - n);
            if let Some(start) = start {
                let after = start + n;
                let take = max_draft.min(len - after);
                if take > 0 {
                    return ctx[after..after + take].to_vec();
                }
            }
        }
        Vec::new()
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

    // Brute-force suffix array: obviously correct, the SA equivalence oracle.
    fn build_sa_bruteforce(s: &[u32]) -> Vec<u32> {
        let mut sa: Vec<u32> = (0..s.len() as u32).collect();
        sa.sort_by(|&a, &b| s[a as usize..].cmp(&s[b as usize..]));
        sa
    }

    #[test]
    fn propose_draft_matches_ngram_speculative() {
        // Proof of the spec-decode integration: the FM-index draft is byte-for-byte
        // the existing prompt-lookup draft (sovereign-ngram-speculative), found by
        // compressed-domain search instead of a linear scan.
        use sovereign_ngram_speculative::NgramSpeculator;
        let mut state: u64 = 0x1a2b3c4d5e6f7081;
        let mut next = |m: u64| {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) % m
        };
        for _ in 0..300 {
            let n = (next(50) + 1) as usize;
            let sigma = (next(4) + 1) as u32; // small alphabet → real repeats
            let ctx: Vec<u32> = (0..n).map(|_| next(sigma as u64) as u32).collect();
            let idx = FmIndex::build(&ctx);
            for &(maxg, ming, maxd) in &[(1usize, 1usize, 3usize), (3, 1, 4), (5, 2, 8), (4, 4, 2)]
            {
                let fm = idx.propose_draft(maxg, ming, maxd);
                let spec = NgramSpeculator::new(maxg, ming, maxd).propose(&ctx);
                assert_eq!(
                    fm, spec,
                    "draft mismatch ctx={ctx:?} ({maxg},{ming},{maxd})"
                );
            }
        }
    }

    #[test]
    fn wavelet_tree_rank_matches_naive() {
        let mut state: u64 = 0xb5297a4d1c8f2e6b;
        let mut next = |m: u64| {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) % m
        };
        for _ in 0..300 {
            let n = (next(80) + 1) as usize;
            let sigma_max = next(20) as u32; // includes σ=0 (single-symbol) edge
            let seq: Vec<u32> = (0..n).map(|_| next(sigma_max as u64 + 1) as u32).collect();
            let wt = WaveletTree::build(&seq, sigma_max);
            for _ in 0..30 {
                let sym = next(sigma_max as u64 + 1) as u32;
                let i = next(n as u64 + 1) as usize;
                let naive = seq[..i].iter().filter(|&&x| x == sym).count();
                assert_eq!(wt.rank(sym, i), naive, "rank({sym},{i}) seq={seq:?}");
            }
        }
    }

    #[test]
    fn prefix_doubling_sa_equals_bruteforce_sa() {
        let mut state: u64 = 0x243f6a8885a308d3;
        let mut next = |m: u64| {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (state >> 33) % m
        };
        for _ in 0..300 {
            let n = (next(60) + 1) as usize;
            let sigma = (next(5) + 1) as u32;
            // sentinel-terminated remapped sequence, exactly as FmIndex::build forms it.
            let mut s: Vec<u32> = (0..n).map(|_| next(sigma as u64) as u32 + 1).collect();
            s.push(0);
            assert_eq!(
                build_sa(&s),
                build_sa_bruteforce(&s),
                "prefix-doubling SA diverged from brute force for {s:?}"
            );
        }
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
