//! `sovereign-bin-packing` — fit the most work into the fewest fixed-size bins.
//!
//! Pack requests into a batch's KV-cache budget, jobs onto fixed-memory workers,
//! chunks into pages: the shape is always the same one-dimensional question — given
//! items of various sizes and bins of a fixed capacity, use as few bins as possible.
//! Optimal bin packing is NP-hard, but a handful of greedy heuristics get very close
//! very fast, and this crate is those heuristics plus a lower bound to tell you how
//! close.
//!
//! - **Next-fit** keeps one open bin and starts a new one when an item does not fit
//!   — fastest, weakest.
//! - **First-fit** puts each item in the first bin it fits — better, still one pass.
//! - **Best-fit** puts each item in the fullest bin it still fits (tightest gap).
//! - **First-fit-decreasing** / **best-fit-decreasing** sort items largest-first
//!   before packing, which is what makes the classic guarantee: FFD never uses more
//!   than `11/9 · optimal + 6/9` bins. They are the ones to reach for by default.
//!
//! Every method returns a [`Packing`]: how many bins, which items landed in each,
//! and each bin's remaining space. [`lower_bound`] (total size divided by capacity,
//! rounded up) is a floor on the optimal bin count, so `bins / lower_bound` is a
//! quick optimality gauge. An item larger than a bin is reported via
//! [`PackError::ItemTooLarge`] rather than silently dropped.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the bin-packing surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The strategy used to assign items to bins.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Strategy {
    /// One open bin; open a new one only when the current item does not fit.
    NextFit,
    /// First bin (in creation order) the item fits into.
    FirstFit,
    /// Fullest bin the item still fits into.
    BestFit,
    /// First-fit after sorting items largest-first.
    FirstFitDecreasing,
    /// Best-fit after sorting items largest-first.
    BestFitDecreasing,
}

/// The result of packing: bins, with the original item indices in each.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Packing {
    /// Bin capacity used for this packing.
    pub capacity: u64,
    /// `bins[b]` = original item indices placed in bin `b`.
    pub bins: Vec<Vec<usize>>,
    /// Remaining free space in each bin (parallel to `bins`).
    pub remaining: Vec<u64>,
}

impl Packing {
    /// The number of bins used.
    pub fn num_bins(&self) -> usize {
        self.bins.len()
    }
    /// The total free space across all bins.
    pub fn total_free(&self) -> u64 {
        self.remaining.iter().sum()
    }
}

/// Errors from packing.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum PackError {
    /// The bin capacity was zero.
    ZeroCapacity,
    /// An item is larger than the bin capacity and can never be placed.
    ItemTooLarge {
        /// Index of the offending item.
        index: usize,
        /// Its size.
        size: u64,
        /// The bin capacity.
        capacity: u64,
    },
}

impl std::fmt::Display for PackError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PackError::ZeroCapacity => write!(f, "bin capacity must be positive"),
            PackError::ItemTooLarge {
                index,
                size,
                capacity,
            } => write!(f, "item {index} of size {size} exceeds capacity {capacity}"),
        }
    }
}
impl std::error::Error for PackError {}

/// A lower bound on the optimal number of bins: `ceil(sum(sizes) / capacity)`.
pub fn lower_bound(sizes: &[u64], capacity: u64) -> usize {
    if capacity == 0 {
        return 0;
    }
    let total: u64 = sizes.iter().sum();
    total.div_ceil(capacity) as usize
}

/// Validate inputs, returning the first oversize item if any.
fn validate(sizes: &[u64], capacity: u64) -> Result<(), PackError> {
    if capacity == 0 {
        return Err(PackError::ZeroCapacity);
    }
    for (i, &s) in sizes.iter().enumerate() {
        if s > capacity {
            return Err(PackError::ItemTooLarge {
                index: i,
                size: s,
                capacity,
            });
        }
    }
    Ok(())
}

/// Pack `sizes` into bins of `capacity` using `strategy`.
pub fn pack(sizes: &[u64], capacity: u64, strategy: Strategy) -> Result<Packing, PackError> {
    validate(sizes, capacity)?;

    // order of item indices to place.
    let mut order: Vec<usize> = (0..sizes.len()).collect();
    if matches!(
        strategy,
        Strategy::FirstFitDecreasing | Strategy::BestFitDecreasing
    ) {
        // largest first; ties by index for determinism.
        order.sort_by(|&a, &b| sizes[b].cmp(&sizes[a]).then(a.cmp(&b)));
    }

    let mut bins: Vec<Vec<usize>> = Vec::new();
    let mut remaining: Vec<u64> = Vec::new();

    for &i in &order {
        let s = sizes[i];
        match strategy {
            Strategy::NextFit => {
                // only the last bin is open.
                if let Some(&last) = remaining.last() {
                    if last >= s {
                        let b = bins.len() - 1;
                        bins[b].push(i);
                        remaining[b] -= s;
                        continue;
                    }
                }
                bins.push(vec![i]);
                remaining.push(capacity - s);
            }
            Strategy::FirstFit | Strategy::FirstFitDecreasing => {
                let mut placed = false;
                for b in 0..bins.len() {
                    if remaining[b] >= s {
                        bins[b].push(i);
                        remaining[b] -= s;
                        placed = true;
                        break;
                    }
                }
                if !placed {
                    bins.push(vec![i]);
                    remaining.push(capacity - s);
                }
            }
            Strategy::BestFit | Strategy::BestFitDecreasing => {
                // the bin with the least remaining space that still fits.
                let mut best: Option<usize> = None;
                for b in 0..bins.len() {
                    if remaining[b] >= s
                        && (best.is_none() || remaining[b] < remaining[best.unwrap()])
                    {
                        best = Some(b);
                    }
                }
                match best {
                    Some(b) => {
                        bins[b].push(i);
                        remaining[b] -= s;
                    }
                    None => {
                        bins.push(vec![i]);
                        remaining.push(capacity - s);
                    }
                }
            }
        }
    }

    Ok(Packing {
        capacity,
        bins,
        remaining,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Validate a packing: every item placed exactly once, no bin over capacity.
    fn is_valid(p: &Packing, sizes: &[u64]) -> bool {
        let mut seen = vec![false; sizes.len()];
        for (b, items) in p.bins.iter().enumerate() {
            let used: u64 = items.iter().map(|&i| sizes[i]).sum();
            if used > p.capacity {
                return false;
            }
            if p.capacity - used != p.remaining[b] {
                return false;
            }
            for &i in items {
                if seen[i] {
                    return false; // placed twice
                }
                seen[i] = true;
            }
        }
        seen.iter().all(|&x| x)
    }

    const ALL: [Strategy; 5] = [
        Strategy::NextFit,
        Strategy::FirstFit,
        Strategy::BestFit,
        Strategy::FirstFitDecreasing,
        Strategy::BestFitDecreasing,
    ];

    #[test]
    fn all_strategies_produce_valid_packings() {
        let sizes = [4, 8, 1, 4, 2, 1, 6, 3, 5, 7];
        for &strat in &ALL {
            let p = pack(&sizes, 10, strat).unwrap();
            assert!(is_valid(&p, &sizes), "{strat:?} invalid");
        }
    }

    #[test]
    fn lower_bound_floor() {
        let sizes = [5, 5, 5, 5];
        assert_eq!(lower_bound(&sizes, 10), 2); // 20/10
        for &strat in &ALL {
            let p = pack(&sizes, 10, strat).unwrap();
            assert!(p.num_bins() >= lower_bound(&sizes, 10));
        }
    }

    #[test]
    fn perfect_fit_uses_minimum() {
        // items that pack exactly into 2 bins of 10.
        let sizes = [6, 4, 7, 3];
        let p = pack(&sizes, 10, Strategy::FirstFitDecreasing).unwrap();
        assert_eq!(p.num_bins(), 2);
        assert_eq!(p.total_free(), 0);
    }

    #[test]
    fn next_fit_opens_new_bin_eagerly() {
        // 3 then 3 then 3 with capacity 10 but interleaved big item.
        let sizes = [3, 8, 3];
        let p = pack(&sizes, 10, Strategy::NextFit).unwrap();
        // next-fit: [3] open; 8 doesn't fit (7 left) → new bin [8]; 3 fits → [8,3]? no, 8 leaves 2, 3 doesn't fit → new bin.
        // So 3 bins.
        assert_eq!(p.num_bins(), 3);
        // first-fit would reuse the first bin for the last 3.
        let pf = pack(&sizes, 10, Strategy::FirstFit).unwrap();
        assert_eq!(pf.num_bins(), 2);
    }

    #[test]
    fn ffd_beats_or_ties_first_fit_on_hard_case() {
        // a classic case where decreasing order helps.
        let sizes = [2, 5, 4, 7, 1, 3, 8];
        let ff = pack(&sizes, 10, Strategy::FirstFit).unwrap();
        let ffd = pack(&sizes, 10, Strategy::FirstFitDecreasing).unwrap();
        assert!(ffd.num_bins() <= ff.num_bins());
        assert!(is_valid(&ffd, &sizes));
    }

    #[test]
    fn item_too_large_rejected() {
        let sizes = [3, 12, 4];
        assert_eq!(
            pack(&sizes, 10, Strategy::FirstFit),
            Err(PackError::ItemTooLarge {
                index: 1,
                size: 12,
                capacity: 10
            })
        );
    }

    #[test]
    fn zero_capacity_rejected() {
        assert_eq!(
            pack(&[1, 2], 0, Strategy::FirstFit),
            Err(PackError::ZeroCapacity)
        );
    }

    #[test]
    fn empty_items() {
        let p = pack(&[], 10, Strategy::BestFitDecreasing).unwrap();
        assert_eq!(p.num_bins(), 0);
        assert_eq!(lower_bound(&[], 10), 0);
    }

    #[test]
    fn exact_capacity_items() {
        // each item exactly fills a bin.
        let sizes = [10, 10, 10];
        let p = pack(&sizes, 10, Strategy::FirstFit).unwrap();
        assert_eq!(p.num_bins(), 3);
        assert_eq!(p.total_free(), 0);
    }

    #[test]
    fn best_fit_tightens_gaps() {
        // best-fit should never use more bins than first-fit here, and packs tightly.
        let sizes = [6, 3, 7, 4, 2, 8, 1, 5];
        let bf = pack(&sizes, 10, Strategy::BestFit).unwrap();
        assert!(is_valid(&bf, &sizes));
        assert!(bf.num_bins() <= pack(&sizes, 10, Strategy::NextFit).unwrap().num_bins());
    }

    #[test]
    fn near_optimal_on_random() {
        // FFD should stay within the 11/9 + small slack of the lower bound.
        let mut s = 0x1234_9876_ABCDu64;
        let mut rng = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        let sizes: Vec<u64> = (0..500).map(|_| 1 + (rng() % 100)).collect();
        let cap = 100;
        let p = pack(&sizes, cap, Strategy::FirstFitDecreasing).unwrap();
        assert!(is_valid(&p, &sizes));
        let lb = lower_bound(&sizes, cap);
        // FFD guarantee: <= 11/9 * OPT + 6/9; OPT >= lb, so be generous.
        assert!(
            (p.num_bins() as f64) <= 1.25 * lb as f64 + 5.0,
            "bins {} lb {lb}",
            p.num_bins()
        );
    }

    #[test]
    fn serde_round_trip() {
        let p = pack(&[3, 7, 2, 8], 10, Strategy::BestFitDecreasing).unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: Packing = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
