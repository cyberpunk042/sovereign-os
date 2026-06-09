//! `sovereign-bpe-train` — learn BPE merge rules from a corpus.
//!
//! [`sovereign-tokenizer`] *applies* a merge table; this crate *learns* one.
//! It runs textbook byte-pair encoding training: start with the corpus as a
//! sequence of single bytes, then repeatedly find the most frequent adjacent
//! pair of symbols, record it as a merge rule, and fuse every occurrence into
//! one symbol — `num_merges` times (or until no pair repeats). The ordered
//! rule list is exactly what [`Tokenizer::from_merges`] consumes.
//!
//! Ties (pairs with equal frequency) are broken by the lexicographically
//! smallest pair, so training is deterministic. The resulting tokenizer is
//! lossless — it inherits the byte-level base vocabulary — and compresses the
//! training corpus into fewer tokens than raw bytes; both are pinned as tests.
//!
//! [`sovereign-tokenizer`]: https://docs.rs/sovereign-tokenizer
//! [`Tokenizer::from_merges`]: sovereign_tokenizer::Tokenizer::from_merges
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_tokenizer::Tokenizer;
use std::collections::HashMap;

/// Schema version of the BPE-training surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// An ordered pair of byte-sequence symbols (a merge rule's left and right).
pub type Pair = (Vec<u8>, Vec<u8>);

/// Learn up to `num_merges` ordered merge rules from `corpus`.
///
/// Stops early if no adjacent pair occurs more than once (further merging
/// would not compress). Returns the rules highest-priority first.
pub fn train(corpus: &str, num_merges: usize) -> Vec<Pair> {
    let mut symbols: Vec<Vec<u8>> = corpus.bytes().map(|b| vec![b]).collect();
    let mut merges = Vec::new();

    for _ in 0..num_merges {
        // count adjacent pairs
        let mut counts: HashMap<Pair, usize> = HashMap::new();
        for w in symbols.windows(2) {
            *counts.entry((w[0].clone(), w[1].clone())).or_insert(0) += 1;
        }

        // pick the most frequent pair; ties → lexicographically smallest pair
        let mut best: Option<(Pair, usize)> = None;
        for (pair, &count) in &counts {
            let better = match &best {
                None => true,
                Some((bp, bc)) => count > *bc || (count == *bc && pair < bp),
            };
            if better {
                best = Some((pair.clone(), count));
            }
        }

        let Some((pair, count)) = best else { break };
        if count < 2 {
            break; // nothing repeats → no compression to gain
        }

        merges.push(pair.clone());
        symbols = apply_merge(&symbols, &pair);
    }
    merges
}

/// Train and wrap the learned rules into a ready-to-use [`Tokenizer`].
pub fn train_tokenizer(corpus: &str, num_merges: usize) -> Tokenizer {
    Tokenizer::from_merges(train(corpus, num_merges))
}

/// Replace every adjacent occurrence of `pair` with its fused symbol.
fn apply_merge(symbols: &[Vec<u8>], pair: &Pair) -> Vec<Vec<u8>> {
    let mut merged = pair.0.clone();
    merged.extend_from_slice(&pair.1);

    let mut out = Vec::with_capacity(symbols.len());
    let mut i = 0;
    while i < symbols.len() {
        if i + 1 < symbols.len() && symbols[i] == pair.0 && symbols[i + 1] == pair.1 {
            out.push(merged.clone());
            i += 2;
        } else {
            out.push(symbols[i].clone());
            i += 1;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_merges_yields_no_rules() {
        assert!(train("abababab", 0).is_empty());
    }

    #[test]
    fn learns_the_most_frequent_pair_first() {
        // In "ababab" the pair (a,b) is by far the most frequent.
        let merges = train("ababab", 1);
        assert_eq!(merges.len(), 1);
        assert_eq!(merges[0], (b"a".to_vec(), b"b".to_vec()));
    }

    #[test]
    fn merges_chain_on_repetition() {
        // "ababab": merge (a,b)->ab, then (ab,ab)->abab.
        let merges = train("ababab", 2);
        assert_eq!(merges.len(), 2);
        assert_eq!(merges[0], (b"a".to_vec(), b"b".to_vec()));
        assert_eq!(merges[1], (b"ab".to_vec(), b"ab".to_vec()));
    }

    #[test]
    fn training_compresses_the_corpus() {
        let corpus = "the theme of the theatre is the theory";
        let raw = Tokenizer::default().encode(corpus).len();
        let trained = train_tokenizer(corpus, 20).encode(corpus).len();
        assert!(trained < raw, "trained {trained} should be < raw {raw}");
    }

    #[test]
    fn trained_tokenizer_is_lossless() {
        let corpus = "hello world, héllo 世界 🌍, hello again";
        let tok = train_tokenizer(corpus, 30);
        for text in [corpus, "hello", "🌍", "unseen text!"] {
            assert_eq!(
                tok.decode(&tok.encode(text)).unwrap(),
                text,
                "text {text:?}"
            );
        }
    }

    #[test]
    fn stops_when_nothing_repeats() {
        // "abcdef": no pair repeats → at most a few merges then stop early.
        let merges = train("abcdef", 100);
        assert!(
            merges.is_empty(),
            "no repeated pair → no merges, got {merges:?}"
        );
    }

    #[test]
    fn training_is_deterministic() {
        let corpus = "mississippi river, mississippi delta";
        assert_eq!(train(corpus, 15), train(corpus, 15));
    }

    #[test]
    fn vocab_grows_by_the_number_of_merges() {
        let corpus = "aaaa bbbb aaaa bbbb cccc aaaa";
        let merges = train(corpus, 5);
        let tok = train_tokenizer(corpus, 5);
        assert_eq!(tok.vocab_size(), 256 + merges.len());
    }
}
