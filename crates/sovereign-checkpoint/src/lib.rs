//! `sovereign-checkpoint` — versioned, integrity-checked model persistence.
//!
//! A model is only useful across restarts if it can be saved and restored, and
//! a *sovereign* runtime must also know when a restored model is corrupt. This
//! crate wraps an [`LlmConfig`] (tokenizer + model weights) in a small binary
//! container:
//!
//! ```text
//!   magic "SVCP" | version u16 | FNV-1a-64 checksum of payload | JSON payload
//! ```
//!
//! [`save`] produces those bytes; [`load`] validates the magic, the format
//! version, and the checksum before deserializing — so a truncated, tampered,
//! or foreign file is rejected with a precise error rather than silently
//! loading garbage. The checksum is FNV-1a (deterministic, dependency-free):
//! tamper-*evident*, not cryptographically tamper-*proof*.
//!
//! [`LlmConfig`]: sovereign_llm::LlmConfig
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_llm::LlmConfig;
use thiserror::Error;

/// Schema version of the checkpoint surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Magic bytes at the start of every checkpoint.
pub const MAGIC: [u8; 4] = *b"SVCP";

/// The container format version this build writes and accepts.
pub const FORMAT_VERSION: u16 = 1;

/// Fixed header length: magic(4) + version(2) + checksum(8).
const HEADER_LEN: usize = 14;

/// Things that can go wrong loading a checkpoint.
#[derive(Debug, Error, PartialEq)]
pub enum CheckpointError {
    /// The data was shorter than a valid header.
    #[error("truncated checkpoint: {len} bytes < {HEADER_LEN}-byte header")]
    Truncated {
        /// Observed length.
        len: usize,
    },
    /// The magic bytes did not match.
    #[error("bad magic: not a sovereign checkpoint")]
    BadMagic,
    /// The format version is not supported by this build.
    #[error("unsupported format version {found} (this build writes {expected})")]
    UnsupportedVersion {
        /// Version found in the file.
        found: u16,
        /// Version this build supports.
        expected: u16,
    },
    /// The payload checksum did not match — the file is corrupt or tampered.
    #[error("checksum mismatch: header {stored:#018x} != computed {computed:#018x}")]
    ChecksumMismatch {
        /// Checksum stored in the header.
        stored: u64,
        /// Checksum recomputed from the payload.
        computed: u64,
    },
    /// The payload failed to deserialize into an `LlmConfig`.
    #[error("deserialize: {0}")]
    Deserialize(String),
}

/// FNV-1a 64-bit hash.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// Serialize a model config into a checkpoint byte container.
pub fn save(config: &LlmConfig) -> Vec<u8> {
    // serde_json on LlmConfig cannot fail (no maps with non-string keys etc.);
    // fall back to an empty payload defensively rather than panicking.
    let payload = serde_json::to_vec(config).unwrap_or_default();
    let checksum = fnv1a(&payload);

    let mut out = Vec::with_capacity(HEADER_LEN + payload.len());
    out.extend_from_slice(&MAGIC);
    out.extend_from_slice(&FORMAT_VERSION.to_le_bytes());
    out.extend_from_slice(&checksum.to_le_bytes());
    out.extend_from_slice(&payload);
    out
}

/// Load and validate a checkpoint back into an [`LlmConfig`].
pub fn load(bytes: &[u8]) -> Result<LlmConfig, CheckpointError> {
    if bytes.len() < HEADER_LEN {
        return Err(CheckpointError::Truncated { len: bytes.len() });
    }
    if bytes[0..4] != MAGIC {
        return Err(CheckpointError::BadMagic);
    }
    let version = u16::from_le_bytes([bytes[4], bytes[5]]);
    if version != FORMAT_VERSION {
        return Err(CheckpointError::UnsupportedVersion {
            found: version,
            expected: FORMAT_VERSION,
        });
    }
    let stored = u64::from_le_bytes([
        bytes[6], bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13],
    ]);
    let payload = &bytes[HEADER_LEN..];
    let computed = fnv1a(payload);
    if stored != computed {
        return Err(CheckpointError::ChecksumMismatch { stored, computed });
    }
    serde_json::from_slice(payload).map_err(|e| CheckpointError::Deserialize(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_llm::LlmConfig;
    use std::collections::BTreeMap;

    // Build a minimal valid LlmConfig via JSON (avoids pulling every block crate
    // as a dev-dep): a 1-layer f32 model over a 256-token base vocab.
    fn sample_config() -> LlmConfig {
        // Construct by deserializing a known-good JSON skeleton would be brittle;
        // instead build the smallest real config through the public types.
        // We round-trip through serde to obtain an owned LlmConfig.
        let json = sample_config_json();
        serde_json::from_str(&json).expect("valid sample config json")
    }

    // A compact but complete LlmConfig JSON: vocab 2, model_dim 2, 1 f32 block.
    fn sample_config_json() -> String {
        // helpers to keep the JSON readable
        let zeros = |n: usize| vec![0.0f32; n];
        let rmsnorm = |dim: usize| {
            let mut m = BTreeMap::new();
            m.insert("dim", serde_json::json!(dim));
            m.insert("eps", serde_json::json!(1e-6));
            m.insert("gain", serde_json::json!(vec![1.0f32; dim]));
            serde_json::to_value(m).unwrap()
        };
        let md = 2usize;
        let vocab = 2usize;
        let block = serde_json::json!({
            "model_dim": md,
            "head_dim": md,
            "attn_norm": rmsnorm(md),
            "ffn_norm": rmsnorm(md),
            "w_q": zeros(md*md), "w_k": zeros(md*md), "w_v": zeros(md*md), "w_o": zeros(md*md),
            "ffn": {
                "dim": md, "hidden": md,
                "w_gate": zeros(md*md), "w_up": zeros(md*md), "w_down": zeros(md*md)
            }
        });
        let model = serde_json::json!({
            "vocab": vocab,
            "model_dim": md,
            "embedding": zeros(vocab*md),
            "blocks": [block],
            "final_norm": rmsnorm(md),
            "head": zeros(vocab*md),
            "sampler": { "config": {
                "temperature": 1.0, "top_k": null, "top_p": null,
                "min_p": null, "repetition_penalty": 1.0
            }},
            "recent_window": 64
        });
        let cfg = serde_json::json!({
            "tokenizer": { "merges": [] },
            "model": model
        });
        serde_json::to_string(&cfg).unwrap()
    }

    #[test]
    fn save_then_load_round_trips() {
        let cfg = sample_config();
        let bytes = save(&cfg);
        let back = load(&bytes).unwrap();
        assert_eq!(cfg, back);
    }

    #[test]
    fn header_has_magic_and_version() {
        let bytes = save(&sample_config());
        assert_eq!(&bytes[0..4], b"SVCP");
        assert_eq!(u16::from_le_bytes([bytes[4], bytes[5]]), FORMAT_VERSION);
        assert!(bytes.len() > HEADER_LEN);
    }

    #[test]
    fn truncated_is_rejected() {
        assert_eq!(
            load(&[0u8; 5]).unwrap_err(),
            CheckpointError::Truncated { len: 5 }
        );
    }

    #[test]
    fn bad_magic_is_rejected() {
        let mut bytes = save(&sample_config());
        bytes[0] = b'X';
        assert_eq!(load(&bytes).unwrap_err(), CheckpointError::BadMagic);
    }

    #[test]
    fn wrong_version_is_rejected() {
        let mut bytes = save(&sample_config());
        bytes[4] = 99; // bump version LE low byte
        assert!(matches!(
            load(&bytes).unwrap_err(),
            CheckpointError::UnsupportedVersion {
                found: _,
                expected: _
            }
        ));
    }

    #[test]
    fn tampered_payload_fails_checksum() {
        let mut bytes = save(&sample_config());
        let last = bytes.len() - 1;
        bytes[last] ^= 0xFF; // flip a payload byte
        assert!(matches!(
            load(&bytes).unwrap_err(),
            CheckpointError::ChecksumMismatch { .. }
        ));
    }

    #[test]
    fn checksum_matches_payload_fnv() {
        let cfg = sample_config();
        let bytes = save(&cfg);
        let stored = u64::from_le_bytes([
            bytes[6], bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13],
        ]);
        assert_eq!(stored, fnv1a(&bytes[HEADER_LEN..]));
    }
}
