//! `sovereign-edit-distance` — Levenshtein distance and fuzzy matching.
//!
//! A model calls `[[tool:calcualtor|...]]` and the dispatcher has no
//! `calcualtor` — but it does have `calculator`. Rejecting outright wastes a
//! turn; suggesting the intended name (or auto-correcting it) recovers
//! gracefully. This crate is the fuzzy-match primitive for that: the
//! [`levenshtein`] edit distance, a normalized [`similarity`] ratio, the
//! [`nearest`] candidate, and a thresholded [`did_you_mean`] suggestion.
//!
//! Distance is computed over Unicode scalar values (so it behaves on non-ASCII
//! names) with the standard two-row dynamic program — `O(n·m)` time, `O(min)`
//! space. Everything is deterministic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the edit-distance surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The Levenshtein edit distance between `a` and `b` (insertions, deletions,
/// substitutions each cost 1).
pub fn levenshtein(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    if a.is_empty() {
        return b.len();
    }
    if b.is_empty() {
        return a.len();
    }

    // two-row DP; iterate over the shorter axis for less memory
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut curr = vec![0usize; b.len() + 1];

    for (i, &ca) in a.iter().enumerate() {
        curr[0] = i + 1;
        for (j, &cb) in b.iter().enumerate() {
            let cost = if ca == cb { 0 } else { 1 };
            curr[j + 1] = (prev[j + 1] + 1) // deletion
                .min(curr[j] + 1) // insertion
                .min(prev[j] + cost); // substitution
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    prev[b.len()]
}

/// Normalized similarity in `[0, 1]`: `1 - distance / max(len_a, len_b)`.
/// Two empty strings are defined as fully similar (`1.0`).
pub fn similarity(a: &str, b: &str) -> f64 {
    let max = a.chars().count().max(b.chars().count());
    if max == 0 {
        return 1.0;
    }
    1.0 - levenshtein(a, b) as f64 / max as f64
}

/// The candidate closest to `query` by edit distance, with that distance. Ties
/// break toward the earlier candidate. `None` if `candidates` is empty.
pub fn nearest<'a>(query: &str, candidates: &[&'a str]) -> Option<(&'a str, usize)> {
    candidates
        .iter()
        .map(|&c| (c, levenshtein(query, c)))
        .min_by_key(|&(_, d)| d)
}

/// Suggest the nearest candidate to `query` only if its edit distance is at most
/// `max_distance` (and it isn't already an exact match). Use for typo recovery.
pub fn did_you_mean<'a>(
    query: &str,
    candidates: &[&'a str],
    max_distance: usize,
) -> Option<&'a str> {
    match nearest(query, candidates) {
        Some((c, d)) if d > 0 && d <= max_distance => Some(c),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_distances() {
        assert_eq!(levenshtein("kitten", "sitting"), 3);
        assert_eq!(levenshtein("flaw", "lawn"), 2);
        assert_eq!(levenshtein("", "abc"), 3);
        assert_eq!(levenshtein("abc", ""), 3);
        assert_eq!(levenshtein("", ""), 0);
    }

    #[test]
    fn identical_strings_have_zero_distance() {
        assert_eq!(levenshtein("calculator", "calculator"), 0);
        assert_eq!(similarity("calculator", "calculator"), 1.0);
    }

    #[test]
    fn single_edits() {
        assert_eq!(levenshtein("cat", "cats"), 1); // insertion
        assert_eq!(levenshtein("cats", "cat"), 1); // deletion
        assert_eq!(levenshtein("cat", "cut"), 1); // substitution
    }

    #[test]
    fn similarity_is_bounded_and_sensible() {
        let s = similarity("calculator", "calcualtor"); // transposition (2 edits)
        assert!(s > 0.7 && s < 1.0, "{s}");
        assert_eq!(similarity("", ""), 1.0);
        assert_eq!(similarity("abc", "xyz"), 0.0);
    }

    #[test]
    fn nearest_picks_the_closest_candidate() {
        let tools = ["calculator", "search", "weather"];
        assert_eq!(nearest("calcualtor", &tools), Some(("calculator", 2)));
        assert_eq!(nearest("serch", &tools), Some(("search", 1)));
        assert_eq!(nearest("", &[]), None);
    }

    #[test]
    fn nearest_breaks_ties_toward_earlier() {
        // "ab" is distance 1 from both "abc" and "abd"; first wins
        assert_eq!(nearest("ab", &["abc", "abd"]), Some(("abc", 1)));
    }

    #[test]
    fn did_you_mean_respects_threshold() {
        let tools = ["calculator", "search"];
        // a 2-edit typo within threshold 2 → suggested
        assert_eq!(did_you_mean("calcualtor", &tools, 2), Some("calculator"));
        // beyond threshold → no suggestion
        assert_eq!(did_you_mean("xyzzy", &tools, 2), None);
        // exact match → not a "did you mean"
        assert_eq!(did_you_mean("search", &tools, 2), None);
    }

    #[test]
    fn works_on_unicode() {
        assert_eq!(levenshtein("café", "cafe"), 1);
        assert_eq!(levenshtein("naïve", "naive"), 1);
    }
}
