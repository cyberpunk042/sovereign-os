//! `sovereign-huffman` — optimal prefix-free coding over token symbols.
//!
//! Given how often each symbol occurs, Huffman coding assigns every symbol a
//! variable-length bit string such that no code is a prefix of another (so a
//! stream decodes unambiguously) and the *expected* code length is minimal among
//! all prefix-free codes. Frequent symbols get short codes, rare ones long codes;
//! the result is within one bit of the distribution's Shannon entropy, which is
//! why it both compresses token streams and gives a concrete read on their
//! information content.
//!
//! Construction is the classic greedy merge: put each symbol in a min-heap keyed
//! by frequency, repeatedly pop the two lowest and replace them with an internal
//! node whose frequency is their sum, until one tree remains. The path from the
//! root to a leaf — left = 0, right = 1 — is that symbol's code. Ties are broken
//! deterministically (by an insertion sequence) so the same frequencies always
//! yield the same code, which matters for a code that has to be shared between an
//! encoder and a decoder. A single-symbol alphabet is given a one-bit code so it
//! is still representable.
//!
//! [`HuffmanCode::encode`] packs a symbol sequence into a [`BitBuffer`] (bytes
//! plus an exact bit length); [`HuffmanCode::decode`] walks the tree to recover
//! the original sequence exactly.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BinaryHeap, HashMap};
use thiserror::Error;

/// Schema version of the Huffman surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors building or using a code.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum HuffmanError {
    /// No symbols (or all zero frequency) were supplied.
    #[error("need at least one symbol with positive frequency")]
    Empty,
    /// A symbol was encountered during encoding that has no code.
    #[error("symbol {0} is not in the code's alphabet")]
    UnknownSymbol(u32),
    /// The bit stream did not decode into whole symbols (corrupt or truncated).
    #[error("bit stream did not decode cleanly into symbols")]
    InvalidStream,
}

/// A packed sequence of bits.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct BitBuffer {
    bytes: Vec<u8>,
    /// Number of valid bits (the last byte may be partially used).
    bit_len: usize,
}

impl BitBuffer {
    /// The number of bits.
    pub fn bit_len(&self) -> usize {
        self.bit_len
    }

    /// Whether there are no bits.
    pub fn is_empty(&self) -> bool {
        self.bit_len == 0
    }

    /// The packed bytes.
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    fn push(&mut self, bit: bool) {
        let byte = self.bit_len / 8;
        if byte >= self.bytes.len() {
            self.bytes.push(0);
        }
        if bit {
            self.bytes[byte] |= 1 << (7 - (self.bit_len % 8));
        }
        self.bit_len += 1;
    }

    fn get(&self, i: usize) -> bool {
        (self.bytes[i / 8] >> (7 - (i % 8))) & 1 == 1
    }
}

/// An internal tree node used only during construction/decoding.
#[derive(Debug, Clone, Serialize, Deserialize)]
enum Node {
    Leaf(u32),
    Internal(Box<Node>, Box<Node>),
}

/// A built Huffman code.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HuffmanCode {
    /// symbol → its bit code (true = 1).
    codes: HashMap<u32, Vec<bool>>,
    tree: Node,
}

/// Heap entry: ordered by descending frequency then descending tie-break so the
/// `BinaryHeap` (a max-heap) pops the *smallest* frequency first.
struct HeapItem {
    freq: u64,
    seq: u64,
    node: Node,
}
impl PartialEq for HeapItem {
    fn eq(&self, other: &Self) -> bool {
        self.freq == other.freq && self.seq == other.seq
    }
}
impl Eq for HeapItem {}
impl Ord for HeapItem {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        // reverse so the min frequency is "greatest" in the max-heap; break ties
        // by smaller seq first (also reversed).
        other.freq.cmp(&self.freq).then(other.seq.cmp(&self.seq))
    }
}
impl PartialOrd for HeapItem {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl HuffmanCode {
    /// Build a code from a `symbol → frequency` map. Zero-frequency symbols are
    /// ignored. The frequencies can be raw counts.
    pub fn from_frequencies(freqs: &HashMap<u32, u64>) -> Result<Self, HuffmanError> {
        let mut items: Vec<(u32, u64)> = freqs
            .iter()
            .filter(|&(_, &f)| f > 0)
            .map(|(&s, &f)| (s, f))
            .collect();
        if items.is_empty() {
            return Err(HuffmanError::Empty);
        }
        // deterministic order regardless of HashMap iteration
        items.sort_by_key(|&(s, _)| s);

        // Single-symbol alphabet: one-bit code.
        if items.len() == 1 {
            let s = items[0].0;
            let mut codes = HashMap::new();
            codes.insert(s, vec![false]);
            return Ok(Self {
                codes,
                tree: Node::Internal(Box::new(Node::Leaf(s)), Box::new(Node::Leaf(s))),
            });
        }

        let mut heap = BinaryHeap::new();
        let mut seq = 0u64;
        for (s, f) in items {
            heap.push(HeapItem {
                freq: f,
                seq,
                node: Node::Leaf(s),
            });
            seq += 1;
        }
        while heap.len() > 1 {
            let a = heap.pop().unwrap();
            let b = heap.pop().unwrap();
            heap.push(HeapItem {
                freq: a.freq + b.freq,
                seq,
                node: Node::Internal(Box::new(a.node), Box::new(b.node)),
            });
            seq += 1;
        }
        let tree = heap.pop().unwrap().node;

        let mut codes = HashMap::new();
        let mut path = Vec::new();
        build_codes(&tree, &mut path, &mut codes);
        Ok(Self { codes, tree })
    }

    /// Build a code from a training sequence by counting symbol frequencies.
    pub fn from_sequence(symbols: &[u32]) -> Result<Self, HuffmanError> {
        let mut freqs = HashMap::new();
        for &s in symbols {
            *freqs.entry(s).or_insert(0) += 1;
        }
        Self::from_frequencies(&freqs)
    }

    /// The number of distinct symbols in the alphabet.
    pub fn alphabet_size(&self) -> usize {
        self.codes.len()
    }

    /// The bit-length of `symbol`'s code, if it is in the alphabet.
    pub fn code_length(&self, symbol: u32) -> Option<usize> {
        self.codes.get(&symbol).map(|c| c.len())
    }

    /// Encode a symbol sequence into a packed [`BitBuffer`].
    pub fn encode(&self, symbols: &[u32]) -> Result<BitBuffer, HuffmanError> {
        let mut buf = BitBuffer::default();
        for &s in symbols {
            let code = self.codes.get(&s).ok_or(HuffmanError::UnknownSymbol(s))?;
            for &bit in code {
                buf.push(bit);
            }
        }
        Ok(buf)
    }

    /// Decode a [`BitBuffer`] back into the original symbol sequence.
    pub fn decode(&self, buf: &BitBuffer) -> Result<Vec<u32>, HuffmanError> {
        let mut out = Vec::new();
        let mut node = &self.tree;
        let mut consumed_since_symbol = 0usize;
        for i in 0..buf.bit_len() {
            let bit = buf.get(i);
            consumed_since_symbol += 1;
            node = match node {
                Node::Internal(l, r) => {
                    if bit {
                        r
                    } else {
                        l
                    }
                }
                Node::Leaf(_) => unreachable!("walk always resets at a leaf"),
            };
            if let Node::Leaf(s) = node {
                out.push(*s);
                node = &self.tree;
                consumed_since_symbol = 0;
            }
        }
        if consumed_since_symbol != 0 {
            return Err(HuffmanError::InvalidStream);
        }
        Ok(out)
    }

    /// The average code length under the given frequencies (expected bits per
    /// symbol). Useful for comparing against the distribution's entropy.
    pub fn average_code_length(&self, freqs: &HashMap<u32, u64>) -> f64 {
        let total: u64 = freqs.values().sum();
        if total == 0 {
            return 0.0;
        }
        let mut bits = 0.0;
        for (&s, &f) in freqs {
            if let Some(len) = self.code_length(s) {
                bits += len as f64 * f as f64;
            }
        }
        bits / total as f64
    }
}

fn build_codes(node: &Node, path: &mut Vec<bool>, out: &mut HashMap<u32, Vec<bool>>) {
    match node {
        Node::Leaf(s) => {
            // root-is-leaf can't happen (we special-case single symbol), but guard
            let code = if path.is_empty() {
                vec![false]
            } else {
                path.clone()
            };
            out.insert(*s, code);
        }
        Node::Internal(l, r) => {
            path.push(false);
            build_codes(l, path, out);
            path.pop();
            path.push(true);
            build_codes(r, path, out);
            path.pop();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn freqs(pairs: &[(u32, u64)]) -> HashMap<u32, u64> {
        pairs.iter().copied().collect()
    }

    #[test]
    fn round_trips_a_sequence() {
        let seq = [1u32, 2, 3, 1, 1, 2, 4, 1, 3, 1];
        let code = HuffmanCode::from_sequence(&seq).unwrap();
        let enc = code.encode(&seq).unwrap();
        let dec = code.decode(&enc).unwrap();
        assert_eq!(dec, seq);
    }

    #[test]
    fn frequent_symbols_get_shorter_codes() {
        // 1 is very frequent, 4 is rare → len(1) <= len(4)
        let f = freqs(&[(1, 100), (2, 10), (3, 5), (4, 1)]);
        let code = HuffmanCode::from_frequencies(&f).unwrap();
        let l1 = code.code_length(1).unwrap();
        let l4 = code.code_length(4).unwrap();
        assert!(l1 <= l4, "len(1)={l1} len(4)={l4}");
        assert_eq!(l1, 1, "dominant symbol should get a 1-bit code");
    }

    #[test]
    fn is_prefix_free() {
        let f = freqs(&[(1, 7), (2, 5), (3, 3), (4, 2), (5, 1)]);
        let code = HuffmanCode::from_frequencies(&f).unwrap();
        let codes: Vec<Vec<bool>> = [1, 2, 3, 4, 5]
            .iter()
            .map(|s| code.codes.get(s).unwrap().clone())
            .collect();
        // no code is a prefix of another
        for i in 0..codes.len() {
            for j in 0..codes.len() {
                if i != j {
                    let a = &codes[i];
                    let b = &codes[j];
                    let is_prefix = a.len() <= b.len() && b[..a.len()] == a[..];
                    assert!(!is_prefix, "code {i} is a prefix of {j}");
                }
            }
        }
    }

    #[test]
    fn average_length_is_near_entropy() {
        // distribution with entropy ~1.75 bits (1/2, 1/4, 1/8, 1/8)
        let f = freqs(&[(0, 4), (1, 2), (2, 1), (3, 1)]); // total 8
        let code = HuffmanCode::from_frequencies(&f).unwrap();
        let avg = code.average_code_length(&f);
        // optimal Huffman achieves exactly the entropy here: 1.75 bits
        assert!((avg - 1.75).abs() < 1e-9, "avg {avg}");
    }

    #[test]
    fn single_symbol_alphabet() {
        let seq = [9u32, 9, 9, 9];
        let code = HuffmanCode::from_sequence(&seq).unwrap();
        assert_eq!(code.code_length(9), Some(1));
        let enc = code.encode(&seq).unwrap();
        assert_eq!(enc.bit_len(), 4); // one bit each
        assert_eq!(code.decode(&enc).unwrap(), seq);
    }

    #[test]
    fn empty_frequencies_error() {
        assert_eq!(
            HuffmanCode::from_frequencies(&HashMap::new()).unwrap_err(),
            HuffmanError::Empty
        );
        assert_eq!(
            HuffmanCode::from_frequencies(&freqs(&[(1, 0)])).unwrap_err(),
            HuffmanError::Empty
        );
    }

    #[test]
    fn unknown_symbol_on_encode_errors() {
        let code = HuffmanCode::from_sequence(&[1, 2, 3]).unwrap();
        assert_eq!(code.encode(&[1, 9]), Err(HuffmanError::UnknownSymbol(9)));
    }

    #[test]
    fn deterministic_for_same_frequencies() {
        let f = freqs(&[(1, 5), (2, 5), (3, 5), (4, 5)]);
        let a = HuffmanCode::from_frequencies(&f).unwrap();
        let b = HuffmanCode::from_frequencies(&f).unwrap();
        for s in [1, 2, 3, 4] {
            assert_eq!(a.codes.get(&s), b.codes.get(&s), "symbol {s}");
        }
    }

    #[test]
    fn compression_beats_fixed_width_on_skewed_data() {
        // skewed stream: mostly symbol 0
        let mut seq = vec![0u32; 1000];
        seq.extend([1, 2, 3, 4, 5]);
        let code = HuffmanCode::from_sequence(&seq).unwrap();
        let enc = code.encode(&seq).unwrap();
        // fixed-width over 6 symbols would need 3 bits each = 3015 bits;
        // Huffman should be far smaller.
        assert!(
            enc.bit_len() < 3 * seq.len(),
            "encoded {} bits",
            enc.bit_len()
        );
        assert!(enc.bit_len() < 1100, "encoded {} bits", enc.bit_len());
    }

    #[test]
    fn serde_round_trip() {
        let code = HuffmanCode::from_sequence(&[1, 1, 2, 3, 3, 3]).unwrap();
        let j = serde_json::to_string(&code).unwrap();
        let back: HuffmanCode = serde_json::from_str(&j).unwrap();
        let seq = [3u32, 1, 2, 3];
        let enc = back.encode(&seq).unwrap();
        assert_eq!(back.decode(&enc).unwrap(), seq);
    }
}
