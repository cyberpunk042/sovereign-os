//! `sovereign-knapsack` — pick the most valuable things that fit the budget.
//!
//! A budget and a set of candidates, each with a cost and a value: which subset
//! maximizes value without blowing the budget? This is the knapsack problem, and it
//! shows up everywhere a runtime allocates a scarce resource — which snippets to
//! pack into a context window, which entries to admit to a cache, which jobs to fund
//! under a quota.
//!
//! Two variants, two algorithms. When items are **indivisible** — you take a thing
//! whole or not at all — it is **0/1 knapsack**, solved exactly by a dynamic program
//! over the budget: for each item, the best value at every capacity is the better of
//! skipping it or taking it and spending its weight. [`knapsack_01`] returns the
//! chosen items and their total value and weight. When items are **divisible** — you
//! can take a fraction and get a proportional share of the value — the greedy by
//! **value density** (value per unit weight) is optimal: take the densest items
//! whole until one no longer fits, then take the fitting fraction of it.
//! [`knapsack_fractional`] returns that fill. Because fractional relaxes the 0/1
//! constraint, its value is always an upper bound on the 0/1 answer.
//!
//! Items with non-positive weight or value, or weight beyond the capacity, are
//! handled gracefully — a free positive-value item is always taken, an unaffordable
//! one is skipped. Results report original item indices so they map back to the
//! input.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the knapsack surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The result of a 0/1 knapsack solve.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Selection {
    /// Indices of the chosen items (ascending).
    pub items: Vec<usize>,
    /// Total value of the chosen items.
    pub total_value: f64,
    /// Total weight of the chosen items (`<= capacity`).
    pub total_weight: u64,
}

/// The result of a fractional knapsack solve.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct FractionalFill {
    /// `(item index, fraction taken in (0, 1])`, densest first.
    pub parts: Vec<(usize, f64)>,
    /// Total value collected.
    pub total_value: f64,
    /// Total weight used (`<= capacity`).
    pub total_weight: f64,
}

/// Solve 0/1 knapsack: choose a subset of `(weight, value)` items maximizing value
/// within `capacity`. Items with zero weight and positive value are always taken;
/// items heavier than the capacity are skipped.
pub fn knapsack_01(items: &[(u64, f64)], capacity: u64) -> Selection {
    let cap = capacity as usize;
    let n = items.len();

    // dp[w] = best value at exactly-or-below capacity w using items processed so far.
    let mut dp = vec![0.0f64; cap + 1];
    // take[i][w] = was item i taken to achieve dp[w] at stage i.
    let mut take = vec![vec![false; cap + 1]; n];

    for (i, &(wt, val)) in items.iter().enumerate() {
        let w = wt as usize;
        // iterate capacity descending so each item is used at most once.
        for c in (0..=cap).rev() {
            if w <= c && val > 0.0 {
                let cand = dp[c - w] + val;
                if cand > dp[c] {
                    dp[c] = cand;
                    take[i][c] = true;
                }
            }
        }
        // propagate "taken" markers for capacities where this item improved nothing
        // are already false; but dp carries forward best regardless.
    }

    // reconstruct by walking items backward.
    let mut items_out = Vec::new();
    let mut c = cap;
    for i in (0..n).rev() {
        if take[i][c] {
            items_out.push(i);
            c -= items[i].0 as usize;
        }
    }
    items_out.sort_unstable();
    let total_weight: u64 = items_out.iter().map(|&i| items[i].0).sum();
    let total_value: f64 = items_out.iter().map(|&i| items[i].1).sum();

    Selection {
        items: items_out,
        total_value,
        total_weight,
    }
}

/// Solve fractional knapsack: items are divisible, greedy by value density.
pub fn knapsack_fractional(items: &[(f64, f64)], capacity: f64) -> FractionalFill {
    // (index, weight, value, density), keeping only positive-weight positive-value.
    let mut cands: Vec<(usize, f64, f64, f64)> = items
        .iter()
        .enumerate()
        .filter(|&(_, &(w, v))| w > 0.0 && v > 0.0 && w.is_finite() && v.is_finite())
        .map(|(i, &(w, v))| (i, w, v, v / w))
        .collect();
    // densest first; ties by index for determinism.
    cands.sort_by(|a, b| b.3.total_cmp(&a.3).then(a.0.cmp(&b.0)));

    let mut remaining = capacity.max(0.0);
    let mut parts = Vec::new();
    let mut total_value = 0.0;
    let mut total_weight = 0.0;
    for (idx, w, v, _) in cands {
        if remaining <= 0.0 {
            break;
        }
        if w <= remaining {
            parts.push((idx, 1.0));
            total_value += v;
            total_weight += w;
            remaining -= w;
        } else {
            let frac = remaining / w;
            parts.push((idx, frac));
            total_value += v * frac;
            total_weight += w * frac;
            remaining = 0.0;
        }
    }

    FractionalFill {
        parts,
        total_value,
        total_weight,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Brute-force 0/1 optimum value (small n).
    fn brute_01(items: &[(u64, f64)], cap: u64) -> f64 {
        let n = items.len();
        let mut best = 0.0f64;
        for mask in 0u32..(1 << n) {
            let mut w = 0u64;
            let mut v = 0.0;
            for i in 0..n {
                if mask & (1 << i) != 0 {
                    w += items[i].0;
                    v += items[i].1;
                }
            }
            if w <= cap {
                best = best.max(v);
            }
        }
        best
    }

    #[test]
    fn basic_knapsack() {
        // classic: capacity 10, items (weight, value).
        let items = [(2, 3.0), (3, 4.0), (4, 5.0), (5, 6.0)];
        let s = knapsack_01(&items, 10);
        // best is items {1,3} (3+5=8 weight, 4+6=10) or {0,2,? } — optimum value 13.
        assert_eq!(s.total_value, 13.0);
        assert!(s.total_weight <= 10);
    }

    #[test]
    fn reconstruction_consistent() {
        let items = [(1, 1.0), (3, 4.0), (4, 5.0), (5, 7.0)];
        let s = knapsack_01(&items, 7);
        let w: u64 = s.items.iter().map(|&i| items[i].0).sum();
        let v: f64 = s.items.iter().map(|&i| items[i].1).sum();
        assert_eq!(w, s.total_weight);
        assert!((v - s.total_value).abs() < 1e-9);
        assert!(s.total_weight <= 7);
    }

    #[test]
    fn matches_brute_force() {
        let mut st = 0x51ED_2716u64;
        let mut rng = || {
            st ^= st << 13;
            st ^= st >> 7;
            st ^= st << 17;
            st
        };
        for _ in 0..200 {
            let n = 1 + (rng() % 12) as usize;
            let items: Vec<(u64, f64)> = (0..n)
                .map(|_| (1 + rng() % 10, 1.0 + (rng() % 20) as f64))
                .collect();
            let cap = 5 + rng() % 30;
            let got = knapsack_01(&items, cap).total_value;
            let want = brute_01(&items, cap);
            assert!((got - want).abs() < 1e-9, "got {got} want {want}");
        }
    }

    #[test]
    fn zero_capacity() {
        let s = knapsack_01(&[(1, 5.0), (2, 8.0)], 0);
        assert!(s.items.is_empty());
        assert_eq!(s.total_value, 0.0);
    }

    #[test]
    fn item_heavier_than_capacity_skipped() {
        let s = knapsack_01(&[(100, 50.0), (2, 3.0)], 5);
        assert_eq!(s.items, vec![1]);
        assert_eq!(s.total_value, 3.0);
    }

    #[test]
    fn zero_weight_item_always_taken() {
        let s = knapsack_01(&[(0, 7.0), (3, 2.0)], 2);
        assert!(s.items.contains(&0));
        assert!(s.total_value >= 7.0);
    }

    #[test]
    fn empty_items() {
        let s = knapsack_01(&[], 10);
        assert!(s.items.is_empty());
        let f = knapsack_fractional(&[], 10.0);
        assert!(f.parts.is_empty());
    }

    #[test]
    fn fractional_fills_completely() {
        // densest items first; the last item is taken fractionally.
        let items = [(10.0, 60.0), (20.0, 100.0), (30.0, 120.0)]; // densities 6,5,4
        let f = knapsack_fractional(&items, 50.0);
        // take item0 (10) + item1 (20) = 30 weight, 160 value; 20 capacity left,
        // take 20/30 of item2 → +80 value. total 240.
        assert!(
            (f.total_value - 240.0).abs() < 1e-9,
            "value {}",
            f.total_value
        );
        assert!((f.total_weight - 50.0).abs() < 1e-9);
    }

    #[test]
    fn fractional_upper_bounds_integer() {
        let items_i = [(10u64, 60.0), (20, 100.0), (30, 120.0)];
        let items_f = [(10.0, 60.0), (20.0, 100.0), (30.0, 120.0)];
        let i = knapsack_01(&items_i, 50);
        let f = knapsack_fractional(&items_f, 50.0);
        // LP relaxation is an upper bound on the integer optimum.
        assert!(f.total_value + 1e-9 >= i.total_value);
    }

    #[test]
    fn serde_round_trip() {
        let s = knapsack_01(&[(2, 3.0), (3, 4.0)], 5);
        let j = serde_json::to_string(&s).unwrap();
        let back: Selection = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        let f = knapsack_fractional(&[(2.0, 3.0)], 1.0);
        let jf = serde_json::to_string(&f).unwrap();
        let backf: FractionalFill = serde_json::from_str(&jf).unwrap();
        assert_eq!(f, backf);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
