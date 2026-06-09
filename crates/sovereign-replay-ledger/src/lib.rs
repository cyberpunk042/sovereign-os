//! `sovereign-replay-ledger` — M012 storage & replay plane (the log).
//!
//! The dump's replay plane needs a durable, tamper-evident record of what
//! happened. This crate is that log: an **append-only, hash-chained**
//! ledger where every entry's hash folds in the previous entry's hash, so
//! altering any past entry breaks the chain from that point on and
//! [`ReplayLedger::verify`] pinpoints it. The replay cursor / bookmark
//! crates navigate over a ledger like this; this is the ledger itself.
//!
//! The hash is FNV-1a (deterministic, dependency-free) — tamper-*evident*,
//! not cryptographically tamper-*proof*; that's the reference contract.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the replay-ledger surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One chained log entry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Entry {
    /// Sequence number (0-based, contiguous).
    pub seq: u64,
    /// Opaque payload (event data).
    pub payload: String,
    /// Hash of the previous entry (`0` for the genesis entry).
    pub prev_hash: u64,
    /// This entry's hash = `fnv1a(seq ‖ prev_hash ‖ payload)`.
    pub hash: u64,
}

/// Ledger integrity errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum LedgerError {
    /// An entry's recomputed hash or prev-link did not match — tampering.
    #[error("ledger tampered at seq {seq}")]
    Tampered {
        /// The first entry whose integrity failed.
        seq: u64,
    },
    /// Sequence numbers were not contiguous from 0.
    #[error("non-contiguous sequence at index {index}: expected seq {expected}, got {got}")]
    NonContiguous {
        /// Position in the entry vector.
        index: usize,
        /// Expected seq.
        expected: u64,
        /// Observed seq.
        got: u64,
    },
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

/// Compute an entry's hash from its fields.
fn entry_hash(seq: u64, prev_hash: u64, payload: &str) -> u64 {
    let mut buf = Vec::with_capacity(16 + payload.len());
    buf.extend_from_slice(&seq.to_le_bytes());
    buf.extend_from_slice(&prev_hash.to_le_bytes());
    buf.extend_from_slice(payload.as_bytes());
    fnv1a(&buf)
}

/// An append-only, hash-chained replay ledger.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ReplayLedger {
    entries: Vec<Entry>,
}

impl ReplayLedger {
    /// An empty ledger.
    pub fn new() -> Self {
        Self::default()
    }

    /// Append a payload; returns the new entry's sequence number.
    pub fn append(&mut self, payload: impl Into<String>) -> u64 {
        let payload = payload.into();
        let seq = self.entries.len() as u64;
        let prev_hash = self.entries.last().map(|e| e.hash).unwrap_or(0);
        let hash = entry_hash(seq, prev_hash, &payload);
        self.entries.push(Entry {
            seq,
            payload,
            prev_hash,
            hash,
        });
        seq
    }

    /// Number of entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the ledger is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// The head hash (chain tip), `0` for an empty ledger.
    pub fn head_hash(&self) -> u64 {
        self.entries.last().map(|e| e.hash).unwrap_or(0)
    }

    /// Read an entry by sequence number.
    pub fn get(&self, seq: u64) -> Option<&Entry> {
        self.entries.get(seq as usize)
    }

    /// All entries from `seq` onward (replay window).
    pub fn replay_from(&self, seq: u64) -> &[Entry] {
        let start = (seq as usize).min(self.entries.len());
        &self.entries[start..]
    }

    /// Reconstruct a ledger from stored entries (e.g. loaded from disk).
    pub fn from_entries(entries: Vec<Entry>) -> Self {
        Self { entries }
    }

    /// Borrow the raw entries.
    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }

    /// Verify the chain: contiguous seqs, correct prev-links, and each hash
    /// recomputes. Returns the first failing seq on tampering.
    pub fn verify(&self) -> Result<(), LedgerError> {
        let mut expected_prev = 0u64;
        for (i, e) in self.entries.iter().enumerate() {
            if e.seq != i as u64 {
                return Err(LedgerError::NonContiguous {
                    index: i,
                    expected: i as u64,
                    got: e.seq,
                });
            }
            if e.prev_hash != expected_prev || e.hash != entry_hash(e.seq, e.prev_hash, &e.payload)
            {
                return Err(LedgerError::Tampered { seq: e.seq });
            }
            expected_prev = e.hash;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn filled() -> ReplayLedger {
        let mut l = ReplayLedger::new();
        l.append("boot");
        l.append("route task-1");
        l.append("commit task-1");
        l
    }

    #[test]
    fn append_assigns_contiguous_seqs() {
        let l = filled();
        assert_eq!(l.len(), 3);
        assert_eq!(l.get(0).unwrap().payload, "boot");
        assert_eq!(l.get(2).unwrap().seq, 2);
        assert_eq!(l.get(0).unwrap().prev_hash, 0); // genesis
    }

    #[test]
    fn chain_links_each_entry() {
        let l = filled();
        // entry i's prev_hash equals entry i-1's hash
        assert_eq!(l.get(1).unwrap().prev_hash, l.get(0).unwrap().hash);
        assert_eq!(l.get(2).unwrap().prev_hash, l.get(1).unwrap().hash);
        assert_eq!(l.head_hash(), l.get(2).unwrap().hash);
    }

    #[test]
    fn clean_ledger_verifies() {
        assert!(filled().verify().is_ok());
    }

    #[test]
    fn tampered_payload_is_detected() {
        let mut entries = filled().entries().to_vec();
        entries[1].payload = "route task-EVIL".to_string(); // mutate without rehashing
        let tampered = ReplayLedger::from_entries(entries);
        assert_eq!(
            tampered.verify().unwrap_err(),
            LedgerError::Tampered { seq: 1 }
        );
    }

    #[test]
    fn rehashed_tamper_still_breaks_the_chain() {
        // A sophisticated tamper: rehash entry 1 so it self-verifies, but the
        // chain to entry 2 (whose prev_hash still points at the old hash) breaks.
        let mut entries = filled().entries().to_vec();
        entries[1].payload = "route task-EVIL".to_string();
        entries[1].hash = entry_hash(entries[1].seq, entries[1].prev_hash, &entries[1].payload);
        let tampered = ReplayLedger::from_entries(entries);
        // entry 1 self-checks, but entry 2's prev_hash no longer matches → seq 2
        assert_eq!(
            tampered.verify().unwrap_err(),
            LedgerError::Tampered { seq: 2 }
        );
    }

    #[test]
    fn non_contiguous_seq_rejected() {
        let entries = vec![Entry {
            seq: 5,
            payload: "x".into(),
            prev_hash: 0,
            hash: entry_hash(5, 0, "x"),
        }];
        let l = ReplayLedger::from_entries(entries);
        assert!(matches!(
            l.verify().unwrap_err(),
            LedgerError::NonContiguous { .. }
        ));
    }

    #[test]
    fn replay_from_window() {
        let l = filled();
        assert_eq!(l.replay_from(1).len(), 2);
        assert_eq!(l.replay_from(1)[0].payload, "route task-1");
        assert_eq!(l.replay_from(99).len(), 0);
    }

    #[test]
    fn serde_round_trip_and_verify() {
        let l = filled();
        let j = serde_json::to_string(&l).unwrap();
        let back: ReplayLedger = serde_json::from_str(&j).unwrap();
        assert!(back.verify().is_ok());
        assert_eq!(back.head_hash(), l.head_hash());
    }
}
