//! `sovereign-context-pack` — fit the most useful context into the window.
//!
//! A retrieval step usually returns more candidate chunks than fit in the model's
//! context window. Choosing which to keep is not "take the top-k until full":
//! chunks differ in *both* length and relevance, so a long, slightly-more-relevant
//! chunk can crowd out two short chunks that together carry more value. That is a
//! **0/1 knapsack** problem — maximize total relevance subject to total tokens ≤
//! budget — and this crate solves it exactly with the classic dynamic program
//! (`O(n · budget)` over integer token counts), recovering which items were
//! chosen.
//!
//! [`pack`] takes the candidate [`Item`]s (each a token count and a relevance
//! value) and a token budget and returns a [`Packing`] with the selected item
//! indices, the total value, and the tokens used. It strictly dominates greedy
//! by-value or by-density selection on adversarial inputs while matching them on
//! easy ones.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the context-pack surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A candidate context chunk: how many tokens it costs and how relevant it is.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Item {
    /// Token cost of including this item.
    pub tokens: usize,
    /// Relevance value (higher is better); must be non-negative for the DP to be
    /// meaningful (negative-value items are simply never selected).
    pub value: f64,
}

impl Item {
    /// A new item.
    pub fn new(tokens: usize, value: f64) -> Self {
        Self { tokens, value }
    }
}

/// The result of packing.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Packing {
    /// Indices (into the input `items`) chosen, in ascending order.
    pub selected: Vec<usize>,
    /// Sum of the selected items' values.
    pub total_value: f64,
    /// Sum of the selected items' token counts (≤ budget).
    pub total_tokens: usize,
}

/// Select the subset of `items` with maximum total value whose token counts sum
/// to at most `budget`. Exact 0/1 knapsack. Items with zero tokens and positive
/// value are always taken; items with non-positive value are never taken.
pub fn pack(items: &[Item], budget: usize) -> Packing {
    let n = items.len();
    // value-scaled DP needs integer-ish handling for floats; we keep a 2-D table
    // of best value reachable using the first i items within capacity w.
    // dp[w] after processing all items = best value with capacity w.
    // We track choices with a full 2-D keep table for exact reconstruction.
    let mut dp = vec![vec![0.0f64; budget + 1]; n + 1];
    let mut keep = vec![vec![false; budget + 1]; n + 1];

    for i in 1..=n {
        let it = &items[i - 1];
        for w in 0..=budget {
            // option 1: skip item i-1
            let mut best = dp[i - 1][w];
            let mut took = false;
            // option 2: take it, if it fits and adds positive value
            if it.tokens <= w && it.value > 0.0 {
                let cand = dp[i - 1][w - it.tokens] + it.value;
                if cand > best {
                    best = cand;
                    took = true;
                }
            }
            dp[i][w] = best;
            keep[i][w] = took;
        }
    }

    // reconstruct
    let mut selected = Vec::new();
    let mut w = budget;
    for i in (1..=n).rev() {
        if keep[i][w] {
            selected.push(i - 1);
            w -= items[i - 1].tokens;
        }
    }
    selected.reverse();
    let total_value: f64 = selected.iter().map(|&i| items[i].value).sum();
    let total_tokens: usize = selected.iter().map(|&i| items[i].tokens).sum();
    Packing {
        selected,
        total_value,
        total_tokens,
    }
}

/// Greedy by value-density (`value / tokens`) — provided for comparison. Not
/// optimal in general, but `O(n log n)` and a reasonable fallback for very large
/// budgets where the exact DP table is too big.
pub fn pack_greedy(items: &[Item], budget: usize) -> Packing {
    let mut order: Vec<usize> = (0..items.len())
        .filter(|&i| items[i].value > 0.0 && items[i].tokens <= budget)
        .collect();
    order.sort_by(|&a, &b| {
        let da = items[a].value / items[a].tokens.max(1) as f64;
        let db = items[b].value / items[b].tokens.max(1) as f64;
        db.total_cmp(&da).then(a.cmp(&b))
    });
    let mut selected = Vec::new();
    let mut used = 0usize;
    for i in order {
        if used + items[i].tokens <= budget {
            used += items[i].tokens;
            selected.push(i);
        }
    }
    selected.sort_unstable();
    let total_value: f64 = selected.iter().map(|&i| items[i].value).sum();
    Packing {
        selected,
        total_value,
        total_tokens: used,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn takes_everything_when_it_fits() {
        let items = [Item::new(10, 1.0), Item::new(20, 2.0), Item::new(5, 0.5)];
        let p = pack(&items, 100);
        assert_eq!(p.selected, vec![0, 1, 2]);
        assert!(approx(p.total_value, 3.5));
        assert_eq!(p.total_tokens, 35);
    }

    #[test]
    fn respects_budget() {
        let items = [Item::new(10, 1.0), Item::new(10, 1.0), Item::new(10, 1.0)];
        let p = pack(&items, 20);
        assert_eq!(p.total_tokens, 20);
        assert_eq!(p.selected.len(), 2);
    }

    #[test]
    fn knapsack_beats_greedy_on_adversarial_input() {
        // classic case: a high-density small item blocks two items that together
        // are better. budget 10.
        // item A: tokens 6, value 7  (density 1.167)
        // item B: tokens 5, value 5  (density 1.0)
        // item C: tokens 5, value 5  (density 1.0)
        // greedy by density takes A (6), then can't fit B or C (need 5, only 4
        // left) → value 7. Optimal takes B+C (10) → value 10.
        let items = [Item::new(6, 7.0), Item::new(5, 5.0), Item::new(5, 5.0)];
        let opt = pack(&items, 10);
        let greedy = pack_greedy(&items, 10);
        assert!(approx(opt.total_value, 10.0), "opt {}", opt.total_value);
        assert!(opt.total_value >= greedy.total_value);
        assert!(
            opt.total_value > greedy.total_value,
            "knapsack should win here"
        );
        assert_eq!(opt.selected, vec![1, 2]);
    }

    #[test]
    fn picks_higher_value_within_budget() {
        // two items, only one fits
        let items = [Item::new(8, 3.0), Item::new(8, 5.0)];
        let p = pack(&items, 8);
        assert_eq!(p.selected, vec![1]); // the value-5 item
        assert!(approx(p.total_value, 5.0));
    }

    #[test]
    fn zero_token_positive_items_always_taken() {
        let items = [Item::new(0, 2.0), Item::new(100, 1.0)];
        let p = pack(&items, 5);
        assert!(p.selected.contains(&0)); // free value
        assert!(!p.selected.contains(&1)); // doesn't fit
    }

    #[test]
    fn non_positive_value_items_skipped() {
        let items = [Item::new(1, 0.0), Item::new(1, -3.0), Item::new(1, 2.0)];
        let p = pack(&items, 10);
        assert_eq!(p.selected, vec![2]);
    }

    #[test]
    fn zero_budget_selects_only_free_items() {
        let items = [Item::new(0, 1.0), Item::new(1, 5.0)];
        let p = pack(&items, 0);
        assert_eq!(p.selected, vec![0]);
        assert_eq!(p.total_tokens, 0);
    }

    #[test]
    fn empty_items() {
        let p = pack(&[], 100);
        assert!(p.selected.is_empty());
        assert_eq!(p.total_value, 0.0);
    }

    #[test]
    fn greedy_matches_optimal_on_easy_cases() {
        let items = [Item::new(3, 3.0), Item::new(3, 2.0), Item::new(3, 1.0)];
        let opt = pack(&items, 6);
        let greedy = pack_greedy(&items, 6);
        assert!(approx(opt.total_value, greedy.total_value));
    }

    #[test]
    fn serde_round_trip() {
        let items = [Item::new(2, 1.0), Item::new(3, 4.0)];
        let p = pack(&items, 5);
        let j = serde_json::to_string(&p).unwrap();
        let back: Packing = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
