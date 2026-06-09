//! `sovereign-diversity` — is the model exploring, or repeating itself?
//!
//! Sample a model many times and you want *variety* — many distinct, valid
//! answers, not the same one reworded. A temperature set too low (or a collapsed
//! model) produces near-identical outputs; too high produces noise. These metrics
//! quantify where on that spectrum a set of generations sits.
//!
//! - **distinct-n** ([`distinct_n`]): the number of *distinct* word n-grams across
//!   all generations divided by the total n-gram count — `1.0` means no n-gram is
//!   ever repeated, low values mean heavy reuse. The standard lexical-diversity
//!   measure.
//! - **Self-BLEU** ([`self_bleu`]): the average BLEU of each generation scored
//!   against all the others. High Self-BLEU means the outputs look like each other
//!   (low diversity); low Self-BLEU means they differ. Delegates the BLEU
//!   computation to [`sovereign_text_eval`].
//! - **unique ratio** ([`unique_ratio`]): the fraction of generations that are
//!   exactly distinct strings — a blunt but useful collapse detector.
//!
//! All take the generations as already-tokenized word slices (or strings via the
//! `_str` helpers), and return values in `[0, 1]`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::HashSet;

/// Schema version of the diversity surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// distinct-n over a set of tokenized generations: distinct word `n`-grams across
/// all generations divided by the total number of n-grams. Returns `1.0` when
/// there are no n-grams (nothing could repeat).
pub fn distinct_n(generations: &[Vec<&str>], n: usize) -> f64 {
    if n == 0 {
        return 1.0;
    }
    let mut distinct: HashSet<String> = HashSet::new();
    let mut total = 0usize;
    for g in generations {
        if g.len() < n {
            continue;
        }
        for w in g.windows(n) {
            distinct.insert(w.join("\u{1f}"));
            total += 1;
        }
    }
    if total == 0 {
        return 1.0;
    }
    distinct.len() as f64 / total as f64
}

/// distinct-n over generations given as whitespace-tokenizable strings.
pub fn distinct_n_str(generations: &[&str], n: usize) -> f64 {
    let toks: Vec<Vec<String>> = generations
        .iter()
        .map(|g| g.split_whitespace().map(|w| w.to_lowercase()).collect())
        .collect();
    let refs: Vec<Vec<&str>> = toks
        .iter()
        .map(|g| g.iter().map(String::as_str).collect())
        .collect();
    distinct_n(&refs, n)
}

/// Self-BLEU: the mean BLEU (up to `max_n`-grams) of each generation against the
/// concatenation-free set of the *others*. Higher means the generations resemble
/// each other (less diverse). Returns 0.0 for fewer than two generations.
pub fn self_bleu(generations: &[Vec<&str>], max_n: usize) -> f64 {
    let k = generations.len();
    if k < 2 {
        return 0.0;
    }
    let mut total = 0.0;
    for i in 0..k {
        // best BLEU of generation i against any other generation (a common
        // Self-BLEU variant: max overlap with the rest).
        let mut best = 0.0f64;
        for j in 0..k {
            if i == j {
                continue;
            }
            let b = sovereign_text_eval::bleu(&generations[i], &generations[j], max_n);
            if b > best {
                best = b;
            }
        }
        total += best;
    }
    total / k as f64
}

/// Self-BLEU over string generations.
pub fn self_bleu_str(generations: &[&str], max_n: usize) -> f64 {
    let toks: Vec<Vec<String>> = generations
        .iter()
        .map(|g| g.split_whitespace().map(|w| w.to_lowercase()).collect())
        .collect();
    let refs: Vec<Vec<&str>> = toks
        .iter()
        .map(|g| g.iter().map(String::as_str).collect())
        .collect();
    self_bleu(&refs, max_n)
}

/// The fraction of generations that are exactly-distinct strings (`1.0` = all
/// unique, low = many duplicates). Returns 0.0 for an empty set.
pub fn unique_ratio(generations: &[&str]) -> f64 {
    if generations.is_empty() {
        return 0.0;
    }
    let distinct: HashSet<&str> = generations.iter().copied().collect();
    distinct.len() as f64 / generations.len() as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn distinct_n_all_unique() {
        let gens = vec![vec!["a", "b", "c"], vec!["d", "e", "f"]];
        // every bigram unique → 1.0
        assert!(approx(distinct_n(&gens, 2), 1.0));
    }

    #[test]
    fn distinct_n_with_repetition() {
        // identical generations → bigrams all repeat → low distinct-n
        let gens = vec![vec!["a", "b", "c"], vec!["a", "b", "c"]];
        // 4 bigrams total, 2 distinct → 0.5
        assert!(approx(distinct_n(&gens, 2), 0.5));
    }

    #[test]
    fn distinct_n_str_lowercases() {
        let d = distinct_n_str(&["The Cat", "the cat"], 1);
        // unigrams: the, cat, the, cat → 2 distinct / 4 = 0.5
        assert!(approx(d, 0.5));
    }

    #[test]
    fn self_bleu_high_for_similar_outputs() {
        let similar = vec![
            vec!["the", "cat", "sat", "on", "the", "mat"],
            vec!["the", "cat", "sat", "on", "the", "mat"],
            vec!["the", "cat", "sat", "on", "the", "rug"],
        ];
        let diverse = vec![
            vec!["the", "cat", "sat", "down"],
            vec!["a", "dog", "ran", "fast"],
            vec!["birds", "fly", "south", "today"],
        ];
        let s_sim = self_bleu(&similar, 4);
        let s_div = self_bleu(&diverse, 4);
        assert!(s_sim > s_div, "similar {s_sim} diverse {s_div}");
        // identical pair → near 1.0
        assert!(s_sim > 0.5);
    }

    #[test]
    fn self_bleu_str_interface() {
        let s = self_bleu_str(&["one two three", "one two three", "four five six"], 2);
        assert!(s > 0.0);
    }

    #[test]
    fn unique_ratio_detects_collapse() {
        // all identical → ratio 1/3
        assert!(approx(unique_ratio(&["x", "x", "x"]), 1.0 / 3.0));
        // all distinct → 1.0
        assert!(approx(unique_ratio(&["a", "b", "c"]), 1.0));
    }

    #[test]
    fn edge_cases() {
        assert!(approx(distinct_n(&[], 2), 1.0));
        assert!(approx(self_bleu(&[vec!["a"]], 4), 0.0)); // <2 gens
        assert!(approx(unique_ratio(&[]), 0.0));
    }

    #[test]
    fn distinct_n_drops_with_lower_temperature_analogy() {
        // a "low temperature" set repeats; a "high temperature" set varies.
        let low = vec![vec!["go", "left"], vec!["go", "left"], vec!["go", "left"]];
        let high = vec![
            vec!["go", "left"],
            vec!["turn", "right"],
            vec!["stop", "now"],
        ];
        assert!(distinct_n(&low, 2) < distinct_n(&high, 2));
    }
}
