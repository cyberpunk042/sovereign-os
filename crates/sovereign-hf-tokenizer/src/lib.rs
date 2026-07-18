//! `sovereign-hf-tokenizer` — a faithful loader for a HuggingFace
//! `tokenizer.json` (GPT-2 **byte-level BPE**: an explicit `piece → id` vocab, a
//! ranked merge list, and the GPT-2 byte↔unicode alphabet). It gives the
//! sovereign quant runtime `encode`/`decode` over a REAL model's vocabulary, so
//! `sovereign-serve --model DIR` can run a real trained Llama/SmolLM-family
//! checkpoint instead of only the 256-vocab byte tokenizer.
//!
//! Sovereignty-clean: pure Rust + `serde_json`. No external `tokenizers`,
//! `regex`, `sentencepiece`, or `protobuf` dependency — the GPT-2 pre-tokenizer
//! regex is hand-rolled with unicode char-class scanning, and the BPE merge loop
//! and byte-level alphabet are implemented here.
//!
//! ```text
//!   ids  = tok.encode("the quick brown fox")   // -> real vocab ids
//!   text = tok.decode(&ids)                     // byte-level inverse
//! ```
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::{HashMap, HashSet};

use serde::Deserialize;
use thiserror::Error;

/// Things that can go wrong loading a `tokenizer.json`.
#[derive(Debug, Error)]
pub enum HfTokenizerError {
    /// The JSON could not be parsed.
    #[error("tokenizer.json parse error: {0}")]
    Json(String),
    /// The `model.type` was not `BPE` (only byte-level BPE is supported here;
    /// SentencePiece/unigram `tokenizer.model` is a separate, later bridge).
    #[error("tokenizer.json is not a byte-level BPE model")]
    NotBpe,
}

// ── tokenizer.json partial schema (only what we need) ─────────────────────────

#[derive(Deserialize)]
struct RawTokenizer {
    model: RawModel,
    #[serde(default)]
    added_tokens: Vec<RawAdded>,
    /// The `pre_tokenizer` block — determines whether text is segmented the
    /// GPT-2 byte-level way (default) or the SentencePiece **Metaspace** way
    /// (`▁`-for-space, direct-unicode vocab). Parsed leniently as a Value so an
    /// unknown pre-tokenizer degrades to the GPT-2 default rather than failing.
    #[serde(default)]
    pre_tokenizer: Option<serde_json::Value>,
}

/// How a model segments raw text before BPE. GPT-2 byte-level (spaces → `Ġ`, the
/// hand-rolled contraction/letter/digit/punct scanner) vs SentencePiece
/// **Metaspace** (spaces → `▁`, direct-unicode vocab pieces + `<0xXX>` byte
/// fallback). Llama/Mistral/Gemma SentencePiece checkpoints need Metaspace; a
/// GPT-2-only tokenizer mis-segments them (F-2026-086).
#[derive(Debug, Clone, PartialEq)]
enum Pretok {
    /// GPT-2 byte-level BPE (the original, unchanged default path).
    Gpt2,
    /// SentencePiece Metaspace: `replacement` (usually `▁` U+2581) substitutes
    /// spaces; `prepend` adds one `replacement` at the very start (the
    /// `prepend_scheme: first|always` behavior).
    Metaspace { replacement: char, prepend: bool },
}

/// Parse the `pre_tokenizer` block into a [`Pretok`]. Handles a bare Metaspace,
/// a `Sequence` that contains one, and falls back to [`Pretok::Gpt2`] for
/// ByteLevel / absent / anything unrecognized (never fail the load on it).
fn parse_pretok(v: Option<&serde_json::Value>) -> Pretok {
    fn as_metaspace(node: &serde_json::Value) -> Option<Pretok> {
        if node.get("type").and_then(|t| t.as_str()) != Some("Metaspace") {
            return None;
        }
        let replacement = node
            .get("replacement")
            .and_then(|r| r.as_str())
            .and_then(|s| s.chars().next())
            .unwrap_or('\u{2581}');
        // prepend_scheme: "first" | "always" | "never" (older tokenizers used a
        // bare `add_prefix_space: bool`). first/always both prepend one leading
        // replacement for our single-sequence render; never/false does not.
        let prepend = match node.get("prepend_scheme").and_then(|p| p.as_str()) {
            Some("never") => false,
            Some(_) => true,
            None => node
                .get("add_prefix_space")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(true),
        };
        Some(Pretok::Metaspace {
            replacement,
            prepend,
        })
    }
    let Some(node) = v else { return Pretok::Gpt2 };
    if let Some(ms) = as_metaspace(node) {
        return ms;
    }
    // Sequence: scan its children for a Metaspace.
    if node.get("type").and_then(|t| t.as_str()) == Some("Sequence")
        && let Some(list) = node.get("pretokenizers").and_then(|p| p.as_array())
    {
        for child in list {
            if let Some(ms) = as_metaspace(child) {
                return ms;
            }
        }
    }
    Pretok::Gpt2
}

#[derive(Deserialize)]
struct RawModel {
    #[serde(rename = "type")]
    typ: Option<String>,
    vocab: HashMap<String, u32>,
    #[serde(default)]
    merges: Vec<serde_json::Value>,
}

#[derive(Deserialize)]
struct RawAdded {
    id: u32,
    content: String,
    #[serde(default)]
    #[allow(dead_code)]
    special: bool,
}

/// The GPT-2 byte→unicode alphabet: a reversible mapping of every byte `0..=255`
/// to a printable unicode codepoint, so BPE can operate over a "clean" alphabet
/// (spaces become `Ġ`, newlines `Ċ`, etc.) with no unprintable/whitespace pieces.
fn bytes_to_unicode() -> ([char; 256], HashMap<char, u8>) {
    let mut bs: Vec<u32> = Vec::new();
    bs.extend((b'!' as u32)..=(b'~' as u32));
    bs.extend(0xA1u32..=0xAC);
    bs.extend(0xAEu32..=0xFF);
    let mut cs = bs.clone();
    let mut n = 0u32;
    for b in 0u32..256 {
        if !bs.contains(&b) {
            bs.push(b);
            cs.push(256 + n);
            n += 1;
        }
    }
    let mut enc = ['\0'; 256];
    let mut dec = HashMap::new();
    for (b, c) in bs.iter().zip(cs.iter()) {
        let ch = char::from_u32(*c).expect("valid codepoint");
        enc[*b as usize] = ch;
        dec.insert(ch, *b as u8);
    }
    (enc, dec)
}

/// The raw bytes a Metaspace vocab piece decodes to. A `<0xXX>` byte-fallback
/// token yields that single byte; any other piece has its `replacement` chars
/// turned back into spaces and its remaining UTF-8 emitted verbatim.
fn metaspace_piece_bytes(piece: &str, replacement: char) -> Vec<u8> {
    if let Some(hex) = piece.strip_prefix("<0x").and_then(|s| s.strip_suffix('>'))
        && hex.len() == 2
        && let Ok(b) = u8::from_str_radix(hex, 16)
    {
        return vec![b];
    }
    let mut out = Vec::with_capacity(piece.len());
    for ch in piece.chars() {
        if ch == replacement {
            out.push(b' ');
        } else {
            let mut buf = [0u8; 4];
            out.extend_from_slice(ch.encode_utf8(&mut buf).as_bytes());
        }
    }
    out
}

/// A model's `tokenizer_config.json` — the sibling of `tokenizer.json` that
/// carries the **chat template** (the Jinja string the gateway must apply to
/// render a real prompt instead of a newline-join) plus the bos/eos special
/// tokens. Parsed leniently: every field is optional so a model dir without a
/// `tokenizer_config.json` (or an older one) still loads (F-2026-086).
#[derive(Debug, Clone, Default, Deserialize)]
pub struct TokenizerConfig {
    /// The Jinja `chat_template` string, if the model ships one.
    #[serde(default)]
    pub chat_template: Option<String>,
    /// The beginning-of-sequence token text (e.g. `<|begin_of_text|>`).
    #[serde(default)]
    pub bos_token: Option<StringOrMap>,
    /// The end-of-sequence token text (e.g. `<|eot_id|>`).
    #[serde(default)]
    pub eos_token: Option<StringOrMap>,
}

/// `bos_token`/`eos_token` may be a bare string OR an `AddedToken` object with a
/// `content` field — accept either.
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum StringOrMap {
    /// A bare `"<|eot_id|>"` string.
    Str(String),
    /// An `{"content": "<|eot_id|>", ...}` object.
    Obj {
        /// The token text.
        content: String,
    },
}

impl StringOrMap {
    /// The token text, whichever shape it arrived in.
    pub fn text(&self) -> &str {
        match self {
            StringOrMap::Str(s) => s,
            StringOrMap::Obj { content } => content,
        }
    }
}

impl TokenizerConfig {
    /// Parse from the raw bytes of a `tokenizer_config.json`. Unknown fields are
    /// ignored; a parse failure is surfaced (the caller may choose to proceed
    /// without a template on error).
    pub fn from_json(bytes: &[u8]) -> Result<Self, HfTokenizerError> {
        serde_json::from_slice(bytes).map_err(|e| HfTokenizerError::Json(e.to_string()))
    }

    /// The chat template string, if present and non-empty.
    pub fn chat_template(&self) -> Option<&str> {
        self.chat_template
            .as_deref()
            .filter(|s| !s.trim().is_empty())
    }
}

fn parse_merge(v: &serde_json::Value) -> Result<(String, String), HfTokenizerError> {
    match v {
        // Older tokenizer.json: a single "a b" string.
        serde_json::Value::String(s) => {
            let mut it = s.splitn(2, ' ');
            let a = it.next().ok_or(HfTokenizerError::NotBpe)?.to_string();
            let b = it.next().ok_or(HfTokenizerError::NotBpe)?.to_string();
            Ok((a, b))
        }
        // Newer tokenizer.json: a ["a", "b"] pair.
        serde_json::Value::Array(arr) if arr.len() == 2 => Ok((
            arr[0].as_str().unwrap_or_default().to_string(),
            arr[1].as_str().unwrap_or_default().to_string(),
        )),
        _ => Err(HfTokenizerError::NotBpe),
    }
}

/// A loaded HuggingFace byte-level BPE tokenizer.
#[derive(Debug)]
pub struct HfBpeTokenizer {
    /// piece → id (includes special/added tokens).
    vocab: HashMap<String, u32>,
    /// id → piece (added tokens overlay the base vocab).
    decoder: HashMap<u32, String>,
    /// (left, right) merge → rank (lower rank merges first).
    merge_ranks: HashMap<(String, String), usize>,
    byte_encoder: [char; 256],
    byte_decoder: HashMap<char, u8>,
    special_ids: HashSet<u32>,
    vocab_size: usize,
    bos_id: Option<u32>,
    /// Segmentation strategy (GPT-2 byte-level vs SentencePiece Metaspace).
    pretok: Pretok,
}

impl HfBpeTokenizer {
    /// Load from the raw bytes of a `tokenizer.json`.
    pub fn from_tokenizer_json(bytes: &[u8]) -> Result<Self, HfTokenizerError> {
        let raw: RawTokenizer =
            serde_json::from_slice(bytes).map_err(|e| HfTokenizerError::Json(e.to_string()))?;
        if raw.model.typ.as_deref() != Some("BPE") {
            return Err(HfTokenizerError::NotBpe);
        }
        let (byte_encoder, byte_decoder) = bytes_to_unicode();

        let mut merge_ranks = HashMap::with_capacity(raw.model.merges.len());
        for (rank, m) in raw.model.merges.iter().enumerate() {
            merge_ranks.insert(parse_merge(m)?, rank);
        }

        let mut decoder: HashMap<u32, String> = HashMap::with_capacity(raw.model.vocab.len());
        for (piece, &id) in &raw.model.vocab {
            decoder.insert(id, piece.clone());
        }
        let mut vocab = raw.model.vocab;

        let mut special_ids = HashSet::new();
        let mut bos_id = None;
        for a in &raw.added_tokens {
            vocab.insert(a.content.clone(), a.id);
            decoder.insert(a.id, a.content.clone());
            special_ids.insert(a.id);
            if a.content == "<|endoftext|>" {
                bos_id = Some(a.id);
            }
        }

        let vocab_size = decoder.keys().copied().max().map_or(0, |m| m as usize + 1);
        let pretok = parse_pretok(raw.pre_tokenizer.as_ref());
        Ok(Self {
            vocab,
            decoder,
            merge_ranks,
            byte_encoder,
            byte_decoder,
            special_ids,
            vocab_size,
            bos_id,
            pretok,
        })
    }

    /// Build directly from a GGUF checkpoint's embedded byte-level BPE tokenizer
    /// (`tokenizer.ggml.model = "gpt2"`/`"bpe"`). `tokens[i]` is the piece for id
    /// `i` (already in the GPT-2 byte-level alphabet, exactly as `tokenizer.json`
    /// stores it); `merges` are `"left right"` rank-ordered rules; `special_ids`
    /// are the control/user-defined tokens to keep atomic. This lets a bare
    /// `*.gguf` tokenize standalone — no sidecar `tokenizer.json` needed.
    ///
    /// # Errors
    /// Returns [`HfTokenizerError::NotBpe`] if `tokens` is empty or a merge rule
    /// is malformed (not a `"left right"` pair).
    pub fn from_gguf_bpe(
        tokens: &[String],
        merges: &[String],
        special_ids: &[u32],
        bos_id: Option<u32>,
    ) -> Result<Self, HfTokenizerError> {
        if tokens.is_empty() {
            return Err(HfTokenizerError::NotBpe);
        }
        let (byte_encoder, byte_decoder) = bytes_to_unicode();

        let mut vocab: HashMap<String, u32> = HashMap::with_capacity(tokens.len());
        let mut decoder: HashMap<u32, String> = HashMap::with_capacity(tokens.len());
        for (id, piece) in tokens.iter().enumerate() {
            let id = id as u32;
            vocab.insert(piece.clone(), id);
            decoder.insert(id, piece.clone());
        }

        let mut merge_ranks = HashMap::with_capacity(merges.len());
        for (rank, m) in merges.iter().enumerate() {
            let mut it = m.splitn(2, ' ');
            let a = it.next().ok_or(HfTokenizerError::NotBpe)?.to_string();
            let b = it.next().ok_or(HfTokenizerError::NotBpe)?.to_string();
            merge_ranks.insert((a, b), rank);
        }

        let special_ids: HashSet<u32> = special_ids.iter().copied().collect();
        let vocab_size = decoder.keys().copied().max().map_or(0, |m| m as usize + 1);
        Ok(Self {
            vocab,
            decoder,
            merge_ranks,
            byte_encoder,
            byte_decoder,
            special_ids,
            vocab_size,
            bos_id,
            // GGUF gpt2/bpe tokenizers use the byte-level alphabet (not Metaspace).
            pretok: Pretok::Gpt2,
        })
    }

    /// True when this tokenizer uses SentencePiece Metaspace segmentation
    /// (`▁`-for-space) rather than the GPT-2 byte-level alphabet.
    pub fn is_metaspace(&self) -> bool {
        matches!(self.pretok, Pretok::Metaspace { .. })
    }

    /// The vocabulary size (max id + 1) — must equal the model's `vocab()`.
    pub fn vocab_size(&self) -> usize {
        self.vocab_size
    }

    /// The beginning-of-sequence id (`<|endoftext|>`), if present.
    pub fn bos_id(&self) -> Option<u32> {
        self.bos_id
    }

    /// Encode text to token ids. GPT-2 path: pre-tokenize → byte-map → BPE →
    /// vocab. Metaspace path: `▁`-normalize → per-word BPE over direct-unicode
    /// pieces → vocab, with `<0xXX>` byte fallback (F-2026-086).
    pub fn encode(&self, text: &str) -> Vec<u32> {
        match self.pretok {
            Pretok::Gpt2 => self.encode_gpt2(text),
            Pretok::Metaspace {
                replacement,
                prepend,
            } => self.encode_metaspace(text, replacement, prepend),
        }
    }

    fn encode_gpt2(&self, text: &str) -> Vec<u32> {
        let mut ids = Vec::new();
        for pre in self.pretokenize(text) {
            // Map the pre-token's UTF-8 bytes through the byte-level alphabet.
            let mapped: String = pre.bytes().map(|b| self.byte_encoder[b as usize]).collect();
            for sym in self.bpe(&mapped) {
                if let Some(&id) = self.vocab.get(&sym) {
                    ids.push(id);
                } else {
                    // Unmerged fallback: every single byte-char is in the vocab.
                    for ch in sym.chars() {
                        if let Some(&id) = self.vocab.get(&ch.to_string()) {
                            ids.push(id);
                        }
                    }
                }
            }
        }
        ids
    }

    /// Split `▁`-normalized text into SentencePiece words, each keeping its
    /// leading `▁`: "▁hi▁there" → ["▁hi", "▁there"].
    fn metaspace_words(&self, text: &str, replacement: char, prepend: bool) -> Vec<String> {
        let mut s: String = text
            .chars()
            .map(|c| if c == ' ' { replacement } else { c })
            .collect();
        if prepend && !s.starts_with(replacement) {
            s.insert(0, replacement);
        }
        let mut words: Vec<String> = Vec::new();
        let mut cur = String::new();
        for ch in s.chars() {
            if ch == replacement && !cur.is_empty() {
                words.push(std::mem::take(&mut cur));
            }
            cur.push(ch);
        }
        if !cur.is_empty() {
            words.push(cur);
        }
        words
    }

    fn encode_metaspace(&self, text: &str, replacement: char, prepend: bool) -> Vec<u32> {
        let mut ids = Vec::new();
        for word in self.metaspace_words(text, replacement, prepend) {
            for sym in self.bpe(&word) {
                if let Some(&id) = self.vocab.get(&sym) {
                    ids.push(id);
                    continue;
                }
                // Piece not in vocab: try each char directly, then fall back to
                // the `<0xXX>` byte tokens SentencePiece models ship for coverage.
                for ch in sym.chars() {
                    if let Some(&id) = self.vocab.get(&ch.to_string()) {
                        ids.push(id);
                    } else {
                        let mut buf = [0u8; 4];
                        for &b in ch.encode_utf8(&mut buf).as_bytes() {
                            if let Some(&id) = self.vocab.get(&format!("<0x{b:02X}>")) {
                                ids.push(id);
                            }
                        }
                    }
                }
            }
        }
        ids
    }

    /// The raw bytes a single token decodes to (empty for special/unknown
    /// tokens) — the primitive for incremental streaming decode, where a
    /// [`sovereign_stream_decode::Utf8Stream`]-style buffer accumulates bytes
    /// and emits valid-UTF-8 chunks as tokens arrive.
    pub fn token_bytes(&self, id: u32) -> Vec<u8> {
        if self.special_ids.contains(&id) {
            return Vec::new();
        }
        match self.decoder.get(&id) {
            Some(piece) => match self.pretok {
                Pretok::Gpt2 => piece
                    .chars()
                    .filter_map(|c| self.byte_decoder.get(&c).copied())
                    .collect(),
                Pretok::Metaspace { replacement, .. } => metaspace_piece_bytes(piece, replacement),
            },
            None => Vec::new(),
        }
    }

    /// Decode token ids back to text (skips special/added tokens).
    pub fn decode(&self, ids: &[u32]) -> String {
        let mut bytes: Vec<u8> = Vec::new();
        for &id in ids {
            if self.special_ids.contains(&id) {
                continue;
            }
            if let Some(piece) = self.decoder.get(&id) {
                match self.pretok {
                    Pretok::Gpt2 => {
                        for ch in piece.chars() {
                            if let Some(&b) = self.byte_decoder.get(&ch) {
                                bytes.push(b);
                            }
                        }
                    }
                    Pretok::Metaspace { replacement, .. } => {
                        bytes.extend(metaspace_piece_bytes(piece, replacement));
                    }
                }
            }
        }
        let mut text = String::from_utf8_lossy(&bytes).into_owned();
        // Metaspace prepends one leading `▁`→space; SentencePiece decode strips
        // that single leading space so "▁Hi" round-trips to "Hi", not " Hi".
        if let Pretok::Metaspace { prepend: true, .. } = self.pretok
            && text.starts_with(' ')
        {
            text.remove(0);
        }
        text
    }

    /// Byte-pair-merge a byte-mapped word into its final pieces.
    fn bpe(&self, word: &str) -> Vec<String> {
        let mut symbols: Vec<String> = word.chars().map(|c| c.to_string()).collect();
        if symbols.len() < 2 {
            return symbols;
        }
        loop {
            // The adjacent pair with the lowest merge rank fires first.
            let mut best: Option<(usize, usize)> = None;
            for i in 0..symbols.len() - 1 {
                if let Some(&rank) = self
                    .merge_ranks
                    .get(&(symbols[i].clone(), symbols[i + 1].clone()))
                {
                    if best.is_none_or(|(br, _)| rank < br) {
                        best = Some((rank, i));
                    }
                }
            }
            let Some((_, i)) = best else { break };
            let merged = format!("{}{}", symbols[i], symbols[i + 1]);
            symbols.splice(i..=i + 1, std::iter::once(merged));
            if symbols.len() < 2 {
                break;
            }
        }
        symbols
    }

    /// GPT-2 pre-tokenization, hand-rolled (no `regex` dep) with individual
    /// digits (SmolLM's `Digits{individual_digits:true}` + `ByteLevel`):
    /// contractions, ` ?letters`, ` ?digit`, ` ?punct+`, and whitespace runs —
    /// a leading single space attaches to the following class run.
    fn pretokenize(&self, text: &str) -> Vec<String> {
        let chars: Vec<char> = text.chars().collect();
        let n = chars.len();
        let mut out: Vec<String> = Vec::new();
        let mut i = 0;
        let take = |a: usize, b: usize| chars[a..b].iter().collect::<String>();
        while i < n {
            let c = chars[i];

            // Contractions: 's 't 'm 'd  and  're 've 'll
            if c == '\'' && i + 1 < n {
                if i + 2 < n {
                    let p = [
                        chars[i + 1].to_ascii_lowercase(),
                        chars[i + 2].to_ascii_lowercase(),
                    ];
                    if matches!(p, ['r', 'e'] | ['v', 'e'] | ['l', 'l']) {
                        out.push(take(i, i + 3));
                        i += 3;
                        continue;
                    }
                }
                if matches!(chars[i + 1].to_ascii_lowercase(), 's' | 't' | 'm' | 'd') {
                    out.push(take(i, i + 2));
                    i += 2;
                    continue;
                }
            }

            if c == ' ' {
                if i + 1 < n && !chars[i + 1].is_whitespace() {
                    // ` ?X`: attach this single space to the following class run.
                    let nxt = chars[i + 1];
                    let j = if nxt.is_alphabetic() {
                        let mut j = i + 1;
                        while j < n && chars[j].is_alphabetic() {
                            j += 1;
                        }
                        j
                    } else if nxt.is_numeric() {
                        i + 2 // individual digit
                    } else {
                        let mut j = i + 1;
                        while j < n && is_other(chars[j]) {
                            j += 1;
                        }
                        j
                    };
                    out.push(take(i, j));
                    i = j;
                    continue;
                }
                // A run of spaces: if a non-space follows, leave the last space
                // for the following ` ?X` token; else consume the whole run.
                let mut j = i;
                while j < n && chars[j] == ' ' {
                    j += 1;
                }
                if j < n && !chars[j].is_whitespace() {
                    if j - 1 > i {
                        out.push(take(i, j - 1));
                    }
                    i = j - 1;
                } else {
                    out.push(take(i, j));
                    i = j;
                }
                continue;
            }

            if c.is_whitespace() {
                // Non-space whitespace (\n, \t, …): consume the run.
                let mut j = i;
                while j < n && chars[j].is_whitespace() && chars[j] != ' ' {
                    j += 1;
                }
                out.push(take(i, j));
                i = j;
                continue;
            }

            if c.is_alphabetic() {
                let mut j = i;
                while j < n && chars[j].is_alphabetic() {
                    j += 1;
                }
                out.push(take(i, j));
                i = j;
                continue;
            }

            if c.is_numeric() {
                out.push(take(i, i + 1)); // individual digit
                i += 1;
                continue;
            }

            // Punctuation / symbol run (non-space, non-letter, non-digit).
            let mut j = i;
            while j < n && is_other(chars[j]) {
                j += 1;
            }
            out.push(take(i, j));
            i = j;
        }
        out
    }
}

/// A "other" char for GPT-2 splitting: not whitespace, letter, or number.
fn is_other(c: char) -> bool {
    !c.is_whitespace() && !c.is_alphabetic() && !c.is_numeric()
}

#[cfg(test)]
mod tests {
    use super::*;

    // A minimal byte-level BPE tokenizer.json exercising byte-mapping (space→Ġ),
    // merges, and specials. `Ġ` is U+0120 (byte 0x20 in the GPT-2 alphabet).
    const MINI: &str = r#"{
      "added_tokens": [{"id": 100, "content": "<|endoftext|>", "special": true}],
      "model": {
        "type": "BPE",
        "vocab": {"a": 1, "b": 2, "c": 3, "Ġ": 4, "ab": 5, "Ġa": 6, "abc": 7},
        "merges": ["a b", "Ġ a", "ab c"]
      }
    }"#;

    fn mini() -> HfBpeTokenizer {
        HfBpeTokenizer::from_tokenizer_json(MINI.as_bytes()).unwrap()
    }

    #[test]
    fn byte_alphabet_maps_space_to_g_dot() {
        let (enc, dec) = bytes_to_unicode();
        assert_eq!(enc[b' ' as usize], '\u{0120}'); // GPT-2: space → Ġ
        assert_eq!(dec[&'\u{0120}'], b' ');
        // printable ascii is identity
        assert_eq!(enc[b'a' as usize], 'a');
        // the alphabet is a bijection over 256 codepoints
        assert_eq!(dec.len(), 256);
    }

    #[test]
    fn merges_apply_by_rank() {
        let t = mini();
        // "ab" merges a+b (rank 0) → piece "ab" (id 5)
        assert_eq!(t.encode("ab"), vec![5]);
        // "abc" merges a+b then ab+c → "abc" (id 7)
        assert_eq!(t.encode("abc"), vec![7]);
    }

    #[test]
    fn leading_space_becomes_g_dot_and_merges() {
        let t = mini();
        // " a" → byte-map "Ġa" → merge Ġ+a (rank 1) → id 6
        assert_eq!(t.encode(" a"), vec![6]);
    }

    #[test]
    fn decode_inverts_byte_level() {
        let t = mini();
        assert_eq!(t.decode(&[5]), "ab");
        assert_eq!(t.decode(&[6]), " a"); // Ġa → space + a
        // round-trip
        assert_eq!(t.decode(&t.encode("abc")), "abc");
    }

    #[test]
    fn specials_are_skipped_on_decode_and_reported() {
        let t = mini();
        assert_eq!(t.bos_id(), Some(100));
        assert_eq!(t.vocab_size(), 101); // max id 100 + 1
        assert_eq!(t.decode(&[100, 5]), "ab"); // special skipped
    }

    #[test]
    fn from_gguf_bpe_matches_json_path() {
        // The same byte-level BPE tokenizer as MINI, but expressed as GGUF parts:
        // a dense id→piece array + "left right" merges. Behavior must match the
        // tokenizer.json path exactly.
        let tokens: Vec<String> = ["<unk>", "a", "b", "c", "Ġ", "ab", "Ġa", "abc"]
            .iter()
            .map(|s| (*s).to_string())
            .collect();
        let merges: Vec<String> = ["a b", "Ġ a", "ab c"]
            .iter()
            .map(|s| (*s).to_string())
            .collect();
        let t = HfBpeTokenizer::from_gguf_bpe(&tokens, &merges, &[0], Some(0)).unwrap();
        assert_eq!(t.vocab_size(), 8);
        assert_eq!(t.bos_id(), Some(0));
        assert!(!t.is_metaspace());
        // merge ranks apply identically to the json path
        assert_eq!(t.encode("ab"), vec![5]);
        assert_eq!(t.encode("abc"), vec![7]);
        assert_eq!(t.encode(" a"), vec![6]); // space → Ġ, then Ġ+a
        // decode inverts the byte-level alphabet; special id 0 is dropped
        assert_eq!(t.decode(&[5]), "ab");
        assert_eq!(t.decode(&[0, 7]), "abc");
        assert_eq!(t.decode(&t.encode("abc")), "abc");
    }

    #[test]
    fn from_gguf_bpe_rejects_empty_and_malformed() {
        // empty vocab → NotBpe
        assert!(HfBpeTokenizer::from_gguf_bpe(&[], &[], &[], None).is_err());
        // a merge without a space separator is malformed → NotBpe
        let toks = vec!["a".to_string(), "b".to_string()];
        let bad = vec!["ab".to_string()];
        assert!(HfBpeTokenizer::from_gguf_bpe(&toks, &bad, &[], None).is_err());
    }

    #[test]
    fn multi_space_run_splits_like_gpt2() {
        let t = mini();
        // "a  b" → ["a", " ", " b"]-ish: two spaces, last attaches to b.
        // Here it should encode a, then a lone space (Ġ id 4), then Ġb→(Ġ,b).
        let ids = t.encode("a  b");
        // first id is 'a' (1); the run keeps generation stable (no panic, ids valid)
        assert_eq!(ids.first(), Some(&1));
        assert!(ids.iter().all(|&x| x <= 100));
    }

    #[test]
    fn gpt2_is_the_default_pretokenizer() {
        // MINI has no pre_tokenizer block → GPT-2 path, unchanged behavior.
        assert!(!mini().is_metaspace());
    }

    // ── Metaspace (SentencePiece) path (F-2026-086) ──────────────────────────
    // A tiny Metaspace tokenizer: `▁`-for-space, direct-unicode vocab, `<0xXX>`
    // byte fallback. Merges build "▁hi" and "▁ab" from their chars.
    const MINI_METASPACE: &str = r#"{
      "pre_tokenizer": {"type": "Metaspace", "replacement": "▁", "prepend_scheme": "first"},
      "model": {
        "type": "BPE",
        "vocab": {"▁": 1, "h": 2, "i": 3, "a": 4, "b": 5,
                  "▁h": 6, "▁hi": 7, "▁a": 8, "▁ab": 9,
                  "<0x5A>": 10},
        "merges": ["▁ h", "▁h i", "▁ a", "▁a b"]
      }
    }"#;

    fn mini_ms() -> HfBpeTokenizer {
        HfBpeTokenizer::from_tokenizer_json(MINI_METASPACE.as_bytes()).unwrap()
    }

    #[test]
    fn metaspace_detected_from_pre_tokenizer() {
        assert!(mini_ms().is_metaspace());
    }

    #[test]
    fn metaspace_encodes_via_underscore_words() {
        let t = mini_ms();
        // "hi ab" → "▁hi▁ab" → words ["▁hi","▁ab"] → ids [7, 9]
        assert_eq!(t.encode("hi ab"), vec![7, 9]);
    }

    #[test]
    fn metaspace_byte_fallback_for_unknown_char() {
        let t = mini_ms();
        // "Z" is not a vocab piece; its byte 0x5A falls back to the <0x5A> token.
        // Prepend adds a leading ▁ (id 1) first.
        assert_eq!(t.encode("Z"), vec![1, 10]);
    }

    #[test]
    fn metaspace_decode_round_trips_and_strips_prepend() {
        let t = mini_ms();
        // ▁→space on decode; the single prepended leading space is stripped.
        assert_eq!(t.decode(&[7, 9]), "hi ab");
        assert_eq!(t.decode(&t.encode("hi ab")), "hi ab");
        // byte-fallback token decodes back to its raw byte
        assert_eq!(t.decode(&[10]), "Z");
    }

    // ── tokenizer_config.json (chat template) ────────────────────────────────

    #[test]
    fn tokenizer_config_parses_chat_template_and_tokens() {
        let json = r#"{
          "chat_template": "{% for m in messages %}<|im_start|>{{ m.role }}{% endfor %}",
          "bos_token": "<|begin_of_text|>",
          "eos_token": {"content": "<|eot_id|>", "lstrip": false}
        }"#;
        let cfg = TokenizerConfig::from_json(json.as_bytes()).unwrap();
        assert!(cfg.chat_template().unwrap().contains("<|im_start|>"));
        assert_eq!(cfg.bos_token.unwrap().text(), "<|begin_of_text|>");
        assert_eq!(cfg.eos_token.unwrap().text(), "<|eot_id|>");
    }

    #[test]
    fn tokenizer_config_absent_fields_are_none() {
        let cfg = TokenizerConfig::from_json(b"{}").unwrap();
        assert!(cfg.chat_template().is_none());
        // an empty/whitespace template counts as absent
        let cfg2 = TokenizerConfig::from_json(br#"{"chat_template": "  "}"#).unwrap();
        assert!(cfg2.chat_template().is_none());
    }
}
