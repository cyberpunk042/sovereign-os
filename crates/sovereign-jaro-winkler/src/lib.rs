//! `sovereign-jaro-winkler` — transposition-aware string similarity.
//!
//! Levenshtein distance counts edits; the **Jaro** similarity instead scores how
//! many characters two strings *share* and how out-of-order those shared
//! characters are, returning a value in `[0, 1]` (1 = identical, 0 = nothing in
//! common). Two characters count as "matching" only if they are equal and lie
//! within a window of `⌊max(|s1|, |s2|) / 2⌋ − 1` positions of each other; among
//! the matched characters, each pair that appears in a different relative order is
//! half a *transposition*. The score blends three ratios — matches over each
//! length, and the non-transposed fraction — so it is sensitive to small
//! reorderings in a way edit distance is not.
//!
//! **Jaro-Winkler** adds a bonus for a shared prefix (up to four characters),
//! because real-world near-duplicates — names, identifiers, typos — tend to agree
//! at the start: `jw = jaro + ℓ · p · (1 − jaro)`, with prefix length `ℓ ≤ 4` and
//! a scaling factor `p` (the standard `0.1`). This makes it a strong ranker for
//! short strings where Levenshtein is coarse.
//!
//! Both operate over Unicode scalar values (`char`s), so multi-byte text is
//! compared character-wise, not byte-wise.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the jaro-winkler surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The standard Winkler prefix-scaling factor.
pub const DEFAULT_PREFIX_WEIGHT: f64 = 0.1;

/// The maximum common-prefix length the Winkler bonus considers.
pub const MAX_PREFIX: usize = 4;

/// The Jaro similarity of `a` and `b`, in `[0.0, 1.0]`.
pub fn jaro(a: &str, b: &str) -> f64 {
    let s1: Vec<char> = a.chars().collect();
    let s2: Vec<char> = b.chars().collect();
    let (l1, l2) = (s1.len(), s2.len());

    if l1 == 0 && l2 == 0 {
        return 1.0; // two empty strings are identical
    }
    if l1 == 0 || l2 == 0 {
        return 0.0;
    }
    if s1 == s2 {
        return 1.0;
    }

    // matching window: characters further apart than this never match.
    let window = (l1.max(l2) / 2).saturating_sub(1);

    let mut s1_matched = vec![false; l1];
    let mut s2_matched = vec![false; l2];
    let mut matches = 0usize;

    for (i, &c1) in s1.iter().enumerate() {
        let lo = i.saturating_sub(window);
        let hi = (i + window + 1).min(l2);
        for j in lo..hi {
            if !s2_matched[j] && s2[j] == c1 {
                s1_matched[i] = true;
                s2_matched[j] = true;
                matches += 1;
                break;
            }
        }
    }

    if matches == 0 {
        return 0.0;
    }

    // count transpositions: walk both matched subsequences in order and compare.
    let mut transpositions = 0usize;
    let mut k = 0usize;
    for i in 0..l1 {
        if s1_matched[i] {
            while !s2_matched[k] {
                k += 1;
            }
            if s1[i] != s2[k] {
                transpositions += 1;
            }
            k += 1;
        }
    }
    let t = transpositions as f64 / 2.0;
    let m = matches as f64;
    (m / l1 as f64 + m / l2 as f64 + (m - t) / m) / 3.0
}

/// The Jaro-Winkler similarity with the standard prefix weight (`0.1`).
pub fn jaro_winkler(a: &str, b: &str) -> f64 {
    jaro_winkler_with(a, b, DEFAULT_PREFIX_WEIGHT)
}

/// The Jaro-Winkler similarity with a custom prefix-scaling factor `p`.
///
/// # Panics
/// Panics if `p` is outside `[0, 0.25]` (above `0.25` the score could exceed 1).
pub fn jaro_winkler_with(a: &str, b: &str, p: f64) -> f64 {
    assert!(
        (0.0..=0.25).contains(&p),
        "prefix weight must be in [0, 0.25]"
    );
    let j = jaro(a, b);
    // shared prefix length, capped at MAX_PREFIX.
    let prefix = a
        .chars()
        .zip(b.chars())
        .take(MAX_PREFIX)
        .take_while(|(x, y)| x == y)
        .count();
    j + prefix as f64 * p * (1.0 - j)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-3
    }

    #[test]
    fn canonical_martha_marhta() {
        // the textbook reference values
        assert!(
            approx(jaro("MARTHA", "MARHTA"), 0.944),
            "{}",
            jaro("MARTHA", "MARHTA")
        );
        assert!(
            approx(jaro_winkler("MARTHA", "MARHTA"), 0.961),
            "{}",
            jaro_winkler("MARTHA", "MARHTA")
        );
    }

    #[test]
    fn canonical_dixon_dicksonx() {
        assert!(
            approx(jaro("DIXON", "DICKSONX"), 0.767),
            "{}",
            jaro("DIXON", "DICKSONX")
        );
        assert!(
            approx(jaro_winkler("DIXON", "DICKSONX"), 0.813),
            "{}",
            jaro_winkler("DIXON", "DICKSONX")
        );
    }

    #[test]
    fn canonical_crate_trace() {
        // shares all chars but heavily transposed
        let j = jaro("CRATE", "TRACE");
        assert!(approx(j, 0.733), "{j}");
    }

    #[test]
    fn identical_strings_score_one() {
        assert_eq!(jaro("hello", "hello"), 1.0);
        assert_eq!(jaro_winkler("hello", "hello"), 1.0);
    }

    #[test]
    fn disjoint_strings_score_zero() {
        assert_eq!(jaro("abc", "xyz"), 0.0);
        assert_eq!(jaro_winkler("abc", "xyz"), 0.0);
    }

    #[test]
    fn empty_string_cases() {
        assert_eq!(jaro("", ""), 1.0);
        assert_eq!(jaro("a", ""), 0.0);
        assert_eq!(jaro("", "a"), 0.0);
    }

    #[test]
    fn winkler_boosts_common_prefix() {
        // same Jaro base, but the one with a longer shared prefix scores higher
        let a = jaro_winkler("prefix-match", "prefix-mxtch");
        let plain = jaro("prefix-match", "prefix-mxtch");
        assert!(a >= plain, "winkler {a} should be >= jaro {plain}");
    }

    #[test]
    fn winkler_never_below_jaro_and_within_unit() {
        for (a, b) in [
            ("martha", "marhta"),
            ("kitten", "sitting"),
            ("foo", "food"),
            ("alpha", "alpine"),
        ] {
            let j = jaro(a, b);
            let jw = jaro_winkler(a, b);
            assert!(jw >= j - 1e-12, "{a}/{b}: jw {jw} < j {j}");
            assert!((0.0..=1.0).contains(&jw), "{a}/{b}: jw {jw} out of range");
        }
    }

    #[test]
    fn symmetric() {
        // Jaro is symmetric in its arguments
        for (a, b) in [("abcd", "abdc"), ("hello", "hallo"), ("xy", "yx")] {
            assert!(approx(jaro(a, b), jaro(b, a)), "asymmetry on {a}/{b}");
        }
    }

    #[test]
    fn handles_multibyte_chars() {
        // identical multibyte strings → 1.0; one transposition handled char-wise
        assert_eq!(jaro("café", "café"), 1.0);
        let j = jaro("café", "cafë");
        assert!(j > 0.0 && j < 1.0, "{j}");
    }

    #[test]
    #[should_panic(expected = "prefix weight")]
    fn rejects_too_large_prefix_weight() {
        jaro_winkler_with("a", "b", 0.5);
    }
}
