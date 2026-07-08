//! `sovereign-tokenizer` — a byte-level BPE tokenizer.
//!
//! The decode stack speaks token ids; this crate is the boundary that turns
//! text into those ids and back. It is **byte-level**: the base vocabulary is
//! all 256 byte values, so every possible input has a representation and
//! encoding is lossless — `decode(encode(text)) == text`, always, pinned as a
//! test.
//!
//! Encoding is classic Byte-Pair Encoding. Start with the text as a sequence
//! of single-byte symbols, then repeatedly find the adjacent pair with the
//! **lowest merge rank** (highest priority) and fuse it into one symbol,
//! until no adjacent pair is a known merge. The merge list is ordered: a rule
//! learned earlier wins over one learned later, and that ordering is what
//! makes BPE deterministic — also pinned as a test. Each surviving symbol maps
//! to its vocabulary id.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the tokenizer surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Number of base (single-byte) tokens.
pub const BASE_TOKENS: usize = 256;

/// Things that can go wrong decoding.
#[derive(Debug, Error, PartialEq)]
pub enum TokenizerError {
    /// A token id had no vocabulary entry.
    #[error("unknown token id {0}")]
    UnknownId(u32),
}

/// A byte-level BPE tokenizer: a vocabulary plus a ranked merge table.
///
/// Serialized form is just the ordered merge list (the lookup tables are
/// rebuilt on load), since maps keyed by byte-sequence tuples don't round-trip
/// through JSON.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(from = "TokenizerData", into = "TokenizerData")]
pub struct Tokenizer {
    /// The ordered merge rules (the serializable source of truth).
    merges: Vec<(Vec<u8>, Vec<u8>)>,
    /// id → token bytes (index is the id).
    id_to_token: Vec<Vec<u8>>,
    /// token bytes → id.
    token_to_id: HashMap<Vec<u8>, u32>,
    /// (left, right) byte-sequence pair → merge rank (lower = higher priority).
    merge_rank: HashMap<(Vec<u8>, Vec<u8>), usize>,
    /// Reserved **special tokens** (e.g. `<bos>`, `<eos>`), occupying ids at the
    /// top of the vocabulary (`bpe_vocab_size + index`). They are never produced
    /// by [`encode`](Self::encode) (control markers, not text) and decode to
    /// nothing.
    specials: Vec<String>,
}

/// The serializable projection of a [`Tokenizer`] — its merge list plus any
/// registered special tokens.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct TokenizerData {
    merges: Vec<(Vec<u8>, Vec<u8>)>,
    /// Special tokens, in id order. Defaulted for backward-compatible loading.
    #[serde(default)]
    specials: Vec<String>,
}

impl From<TokenizerData> for Tokenizer {
    fn from(data: TokenizerData) -> Self {
        Tokenizer::from_merges(data.merges).with_specials(data.specials)
    }
}

impl From<Tokenizer> for TokenizerData {
    fn from(tok: Tokenizer) -> Self {
        TokenizerData {
            merges: tok.merges,
            specials: tok.specials,
        }
    }
}

impl Default for Tokenizer {
    fn default() -> Self {
        Self::from_merges(Vec::new())
    }
}

impl Tokenizer {
    /// Build a tokenizer from an ordered list of merge rules. The 256 base
    /// byte tokens are always present (ids `0..256`); each merge appends a new
    /// token (id `256 + rank`) for the fused byte sequence. Earlier merges
    /// have higher priority.
    pub fn from_merges(merges: Vec<(Vec<u8>, Vec<u8>)>) -> Self {
        let mut id_to_token: Vec<Vec<u8>> =
            (0..BASE_TOKENS as u16).map(|b| vec![b as u8]).collect();
        let mut token_to_id: HashMap<Vec<u8>, u32> = id_to_token
            .iter()
            .enumerate()
            .map(|(i, t)| (t.clone(), i as u32))
            .collect();
        let mut merge_rank = HashMap::new();

        for (rank, (a, b)) in merges.iter().enumerate() {
            let mut merged = a.clone();
            merged.extend_from_slice(b);
            merge_rank.insert((a.clone(), b.clone()), rank);
            token_to_id.entry(merged.clone()).or_insert_with(|| {
                let id = id_to_token.len() as u32;
                id_to_token.push(merged);
                id
            });
        }

        Self {
            merges,
            id_to_token,
            token_to_id,
            merge_rank,
            specials: Vec::new(),
        }
    }

    /// Register **special tokens** (in order), each reserved at a fresh id above
    /// the BPE vocabulary. Duplicates (and names already registered) are
    /// ignored. Returns `self` for chaining. Use [`special_id`](Self::special_id)
    /// to look one up — e.g. an `<eos>` to pass as a stop token to generation.
    pub fn with_specials<I, S>(mut self, names: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        for name in names {
            let name = name.into();
            if !name.is_empty() && !self.specials.contains(&name) {
                self.specials.push(name);
            }
        }
        self
    }

    /// The BPE vocabulary size (base bytes + merged tokens), excluding specials.
    pub fn bpe_vocab_size(&self) -> usize {
        self.id_to_token.len()
    }

    /// Total vocabulary size (base bytes + merged tokens + special tokens).
    pub fn vocab_size(&self) -> usize {
        self.id_to_token.len() + self.specials.len()
    }

    /// The id of the special token named `name`, if registered.
    pub fn special_id(&self, name: &str) -> Option<u32> {
        self.specials
            .iter()
            .position(|s| s == name)
            .map(|i| (self.id_to_token.len() + i) as u32)
    }

    /// The name of the special token with id `id`, if `id` is a special.
    pub fn special_name(&self, id: u32) -> Option<&str> {
        let base = self.id_to_token.len() as u32;
        (id >= base)
            .then(|| self.specials.get((id - base) as usize).map(String::as_str))
            .flatten()
    }

    /// The bytes of a token id, if it exists.
    pub fn token_bytes(&self, id: u32) -> Option<&[u8]> {
        self.id_to_token.get(id as usize).map(|v| v.as_slice())
    }

    /// Encode text into token ids via greedy lowest-rank-first BPE merging.
    pub fn encode(&self, text: &str) -> Vec<u32> {
        if text.is_empty() {
            return Vec::new();
        }
        // Start from single-byte symbols.
        let mut symbols: Vec<Vec<u8>> = text.bytes().map(|b| vec![b]).collect();

        loop {
            // Find the adjacent pair with the smallest merge rank.
            let mut best: Option<(usize, usize)> = None; // (index, rank)
            for i in 0..symbols.len().saturating_sub(1) {
                let key = (symbols[i].clone(), symbols[i + 1].clone());
                if let Some(&rank) = self.merge_rank.get(&key) {
                    if best.is_none_or(|(_, br)| rank < br) {
                        best = Some((i, rank));
                    }
                }
            }
            let Some((i, _)) = best else { break };
            // Fuse symbols[i] and symbols[i+1].
            let mut fused = std::mem::take(&mut symbols[i]);
            fused.extend_from_slice(&symbols[i + 1]);
            symbols[i] = fused;
            symbols.remove(i + 1);
        }

        // Map symbols to ids (every symbol is in vocab: base bytes always are,
        // merged symbols were registered when their rule was added).
        symbols.iter().map(|s| self.token_to_id[s]).collect()
    }

    /// Decode token ids back into a string (lossy on invalid UTF-8).
    pub fn decode(&self, ids: &[u32]) -> Result<String, TokenizerError> {
        let mut bytes = Vec::new();
        for &id in ids {
            // Special tokens are control markers → emit no text.
            if self.special_name(id).is_some() {
                continue;
            }
            let tok = self
                .id_to_token
                .get(id as usize)
                .ok_or(TokenizerError::UnknownId(id))?;
            bytes.extend_from_slice(tok);
        }
        Ok(String::from_utf8_lossy(&bytes).into_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn merges(pairs: &[(&str, &str)]) -> Vec<(Vec<u8>, Vec<u8>)> {
        pairs
            .iter()
            .map(|(a, b)| (a.as_bytes().to_vec(), b.as_bytes().to_vec()))
            .collect()
    }

    #[test]
    fn special_tokens_reserve_ids_above_bpe_vocab() {
        let t = Tokenizer::from_merges(merges(&[("a", "b")])).with_specials(["<bos>", "<eos>"]);
        let bpe = t.bpe_vocab_size(); // 256 + 1 merge = 257
        assert_eq!(bpe, 257);
        assert_eq!(t.vocab_size(), 259); // + 2 specials
        assert_eq!(t.special_id("<bos>"), Some(257));
        assert_eq!(t.special_id("<eos>"), Some(258));
        assert_eq!(t.special_id("<missing>"), None);
        assert_eq!(t.special_name(258), Some("<eos>"));
        assert_eq!(t.special_name(0), None); // a byte, not special
    }

    #[test]
    fn encode_never_emits_specials_and_decode_skips_them() {
        let t = Tokenizer::default().with_specials(["<eos>"]);
        let eos = t.special_id("<eos>").unwrap();
        let ids = t.encode("hi");
        assert!(
            ids.iter().all(|&id| id != eos),
            "encode must not emit <eos>"
        );
        // A sequence with the special interleaved decodes to just the text.
        let mut with_special = t.encode("hi");
        with_special.push(eos);
        with_special.extend(t.encode("!"));
        assert_eq!(t.decode(&with_special).unwrap(), "hi!");
    }

    #[test]
    fn specials_dedupe_and_ignore_empty() {
        let t = Tokenizer::default().with_specials(["<eos>", "<eos>", "", "<pad>"]);
        assert_eq!(t.vocab_size(), 256 + 2); // <eos>, <pad> only
        assert_eq!(t.special_id("<pad>"), Some(257));
    }

    #[test]
    fn specials_survive_serde_round_trip() {
        let t = Tokenizer::from_merges(merges(&[("a", "b")])).with_specials(["<bos>", "<eos>"]);
        let data: TokenizerData = t.clone().into();
        let back: Tokenizer = data.into();
        assert_eq!(back.vocab_size(), t.vocab_size());
        assert_eq!(back.special_id("<eos>"), t.special_id("<eos>"));
    }

    #[test]
    fn base_vocab_is_256() {
        let t = Tokenizer::default();
        assert_eq!(t.vocab_size(), 256);
    }

    #[test]
    fn no_merges_is_one_token_per_byte() {
        let t = Tokenizer::default();
        let ids = t.encode("abc");
        assert_eq!(ids, vec![b'a' as u32, b'b' as u32, b'c' as u32]);
    }

    #[test]
    fn round_trip_is_lossless_ascii() {
        let t = Tokenizer::from_merges(merges(&[("a", "b"), ("ab", "c")]));
        for text in ["", "a", "abc", "the quick brown fox", "aaa bbb ccc"] {
            assert_eq!(t.decode(&t.encode(text)).unwrap(), text, "text {text:?}");
        }
    }

    #[test]
    fn round_trip_is_lossless_utf8() {
        // multi-byte UTF-8 survives because encoding is byte-level
        let t = Tokenizer::default();
        let text = "héllo — 世界 🌍";
        assert_eq!(t.decode(&t.encode(text)).unwrap(), text);
    }

    #[test]
    fn a_merge_reduces_token_count() {
        let plain = Tokenizer::default();
        let merged = Tokenizer::from_merges(merges(&[("a", "b")]));
        let text = "abab";
        assert_eq!(plain.encode(text).len(), 4); // a b a b
        assert_eq!(merged.encode(text).len(), 2); // ab ab
    }

    #[test]
    fn merges_chain_into_longer_tokens() {
        // a+b → ab, then ab+c → abc. "abc" should become a single token.
        let t = Tokenizer::from_merges(merges(&[("a", "b"), ("ab", "c")]));
        let ids = t.encode("abc");
        assert_eq!(ids.len(), 1);
        assert_eq!(t.token_bytes(ids[0]).unwrap(), b"abc");
    }

    #[test]
    fn lower_rank_merge_wins_first() {
        // Two competing merges over "aa": with rule ("a","a") present, "aaa"
        // greedily merges the leftmost pair first → ["aa","a"] then, if
        // ("aa","a") exists, → ["aaa"]. Order/rank determines the outcome.
        let t = Tokenizer::from_merges(merges(&[("a", "a"), ("aa", "a")]));
        let ids = t.encode("aaa");
        assert_eq!(ids.len(), 1);
        assert_eq!(t.token_bytes(ids[0]).unwrap(), b"aaa");
    }

    #[test]
    fn rank_priority_is_respected() {
        // "xy" has rank 0, "yz" rank 1. In "xyz", the rank-0 pair (x,y) is
        // chosen before (y,z), yielding ["xy","z"] (2 tokens), not ["x","yz"].
        let t = Tokenizer::from_merges(merges(&[("x", "y"), ("y", "z")]));
        let ids = t.encode("xyz");
        assert_eq!(ids.len(), 2);
        assert_eq!(t.token_bytes(ids[0]).unwrap(), b"xy");
        assert_eq!(t.token_bytes(ids[1]).unwrap(), b"z");
    }

    #[test]
    fn encoding_is_deterministic() {
        let t = Tokenizer::from_merges(merges(&[("a", "b"), ("ab", "c")]));
        assert_eq!(t.encode("abcabc"), t.encode("abcabc"));
    }

    #[test]
    fn merged_tokens_extend_vocab() {
        let t = Tokenizer::from_merges(merges(&[("a", "b"), ("ab", "c")]));
        // 256 base + 2 merged = 258
        assert_eq!(t.vocab_size(), 258);
    }

    #[test]
    fn decode_rejects_unknown_id() {
        let t = Tokenizer::default(); // vocab 256
        assert_eq!(
            t.decode(&[300]).unwrap_err(),
            TokenizerError::UnknownId(300)
        );
    }

    #[test]
    fn serde_round_trip() {
        let t = Tokenizer::from_merges(merges(&[("a", "b")]));
        let j = serde_json::to_string(&t).unwrap();
        let back: Tokenizer = serde_json::from_str(&j).unwrap();
        assert_eq!(t.vocab_size(), back.vocab_size());
        assert_eq!(t.encode("abab"), back.encode("abab"));
    }
}
