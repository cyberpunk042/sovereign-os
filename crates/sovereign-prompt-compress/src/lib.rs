//! `sovereign-prompt-compress` — keep the words that carry information.
//!
//! Long prompts cost tokens, but not every token earns its place: a model that
//! can already predict a word with near-certainty learns little from seeing it.
//! Selective compression (the LLMLingua idea) exploits this — score each token by
//! its **surprisal** `−log p` under a small language model, then keep the
//! high-surprisal (informative) tokens and drop the predictable ones until the
//! prompt fits a budget. The kept tokens are returned **in their original order**,
//! so the compressed text still reads coherently.
//!
//! [`select_informative`] returns the indices to keep for a target `keep_ratio`;
//! [`select_to_budget`] keeps as many as fit in a token budget; [`compress`]
//! applies a selection to a token sequence. An optional `keep_anchors` flag always
//! retains the first and last token (often a delimiter or instruction boundary you
//! don't want to lose). Ties in surprisal break toward keeping the **earlier**
//! token, so removals are biased to the redundant middle.
//!
//! Inputs are the per-token log-probabilities (natural log) the model already
//! computes, so no extra pass is needed.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the prompt-compress surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Select the indices of the most-informative tokens to keep so that about
/// `keep_ratio` of them survive. `token_logprobs[i]` is the log-probability the
/// model assigned token `i` (lower = more surprising = more informative). The
/// returned indices are in ascending (original) order. If `keep_anchors` is set,
/// the first and last tokens are always kept.
///
/// `keep_ratio` is clamped to `[0, 1]`.
pub fn select_informative(
    token_logprobs: &[f64],
    keep_ratio: f64,
    keep_anchors: bool,
) -> Vec<usize> {
    let n = token_logprobs.len();
    if n == 0 {
        return Vec::new();
    }
    let ratio = keep_ratio.clamp(0.0, 1.0);
    let mut k = (ratio * n as f64).round() as usize;
    if keep_anchors {
        k = k.max(2.min(n));
    }
    keep_top_k(token_logprobs, k, keep_anchors)
}

/// Keep as many informative tokens as fit within `budget` tokens (anchors count
/// toward the budget). Equivalent to [`select_informative`] with
/// `keep_ratio = budget / n`, but expressed directly in token counts.
pub fn select_to_budget(token_logprobs: &[f64], budget: usize, keep_anchors: bool) -> Vec<usize> {
    let n = token_logprobs.len();
    let k = budget.min(n);
    keep_top_k(token_logprobs, k, keep_anchors)
}

/// Keep the `k` most-informative (lowest log-prob) indices, plus anchors if asked,
/// returned in ascending order.
fn keep_top_k(token_logprobs: &[f64], k: usize, keep_anchors: bool) -> Vec<usize> {
    let n = token_logprobs.len();
    if k >= n {
        return (0..n).collect();
    }
    if k == 0 && !keep_anchors {
        return Vec::new();
    }
    // rank by surprisal descending (lowest log-prob first); ties → earlier index.
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| {
        token_logprobs[a]
            .total_cmp(&token_logprobs[b])
            .then(a.cmp(&b))
    });

    let mut keep = vec![false; n];
    if keep_anchors {
        keep[0] = true;
        keep[n - 1] = true;
    }
    let mut kept = keep.iter().filter(|&&x| x).count();
    for &idx in &order {
        if kept >= k {
            break;
        }
        if !keep[idx] {
            keep[idx] = true;
            kept += 1;
        }
    }
    (0..n).filter(|&i| keep[i]).collect()
}

/// Apply a selection of indices to a token slice, returning the kept tokens.
pub fn compress<T: Clone>(tokens: &[T], keep_indices: &[usize]) -> Vec<T> {
    keep_indices
        .iter()
        .filter(|&&i| i < tokens.len())
        .map(|&i| tokens[i].clone())
        .collect()
}

/// The compression ratio achieved: `1 − kept / original` (fraction removed).
pub fn compression_ratio(original_len: usize, kept_len: usize) -> f64 {
    if original_len == 0 {
        0.0
    } else {
        1.0 - kept_len as f64 / original_len as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keep_ratio_one_keeps_all() {
        let lp = [-0.1, -2.0, -0.5, -3.0];
        let keep = select_informative(&lp, 1.0, false);
        assert_eq!(keep, vec![0, 1, 2, 3]);
    }

    #[test]
    fn keep_ratio_zero_keeps_none_without_anchors() {
        let lp = [-0.1, -2.0, -0.5];
        assert!(select_informative(&lp, 0.0, false).is_empty());
    }

    #[test]
    fn drops_predictable_keeps_informative() {
        // tokens 0 and 2 are predictable (high log-prob ~ 0); 1 and 3 surprising.
        let lp = [-0.05, -4.0, -0.05, -5.0];
        let keep = select_informative(&lp, 0.5, false); // keep 2 of 4
        // the two most surprising (1 and 3) should survive
        assert_eq!(keep, vec![1, 3]);
    }

    #[test]
    fn order_is_preserved() {
        let lp = [-3.0, -0.1, -4.0, -0.2, -5.0];
        let keep = select_informative(&lp, 0.6, false); // keep 3
        // indices returned ascending regardless of surprisal order
        assert!(keep.windows(2).all(|w| w[0] < w[1]));
    }

    #[test]
    fn anchors_always_kept() {
        // first and last are very predictable but anchors force their retention.
        let lp = [-0.01, -5.0, -4.0, -0.01];
        let keep = select_informative(&lp, 0.5, true); // keep ~2, but anchors force 0 and 3
        assert!(keep.contains(&0) && keep.contains(&3));
    }

    #[test]
    fn budget_interface() {
        let lp = [-1.0, -2.0, -3.0, -4.0, -5.0];
        let keep = select_to_budget(&lp, 2, false);
        assert_eq!(keep.len(), 2);
        // the two most surprising → indices 3 and 4
        assert_eq!(keep, vec![3, 4]);
    }

    #[test]
    fn compress_applies_selection() {
        let tokens = ["the", "quick", "brown", "fox"];
        let kept = compress(&tokens, &[0, 2, 3]);
        assert_eq!(kept, vec!["the", "brown", "fox"]);
    }

    #[test]
    fn compression_ratio_math() {
        assert!((compression_ratio(10, 4) - 0.6).abs() < 1e-9);
        assert_eq!(compression_ratio(0, 0), 0.0);
    }

    #[test]
    fn realistic_compression_keeps_content_words() {
        // surprisal: function words predictable, content words surprising.
        // "the cat sat on the mat" → keep cat, sat, mat (content).
        let tokens = ["the", "cat", "sat", "on", "the", "mat"];
        let lp = [-0.02, -4.0, -3.5, -0.05, -0.02, -4.2];
        let keep = select_informative(&lp, 0.5, false); // keep 3
        let compressed = compress(&tokens, &keep);
        assert!(compressed.contains(&"cat"));
        assert!(compressed.contains(&"mat"));
        assert!(!compressed.contains(&"the"));
    }

    #[test]
    fn empty_input() {
        assert!(select_informative(&[], 0.5, true).is_empty());
        assert!(compress::<u32>(&[], &[]).is_empty());
    }
}
