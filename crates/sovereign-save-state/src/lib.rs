//! `sovereign-save-state` — E0451: ZFS + CRIU together.
//!
//! ZFS snapshots hold filesystem truth; CRIU holds process state. Neither alone
//! is a true agent save-state — that needs five layers combined: the ZFS
//! snapshot, the CRIU checkpoint, the replay log (why the state exists), the
//! memory record (what was learned), and the profile state (what permissions
//! and budgets apply). "Cloud providers rarely give you this level of
//! continuity." This crate fixes the five layers and the completeness gate so a
//! save-state missing a layer is not mistaken for a true one.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

/// The 5 layers of a true agent save-state (E0451).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SaveLayer {
    /// ZFS snapshot — files + repo + caches + artifacts.
    ZfsSnapshot,
    /// CRIU checkpoint — running process / container state.
    CriuCheckpoint,
    /// Replay log — why the state exists.
    ReplayLog,
    /// Memory record — what was learned.
    MemoryRecord,
    /// Profile state — what permissions and budgets apply.
    ProfileState,
}

impl SaveLayer {
    /// All 5 layers.
    pub const ALL: [SaveLayer; 5] = [
        SaveLayer::ZfsSnapshot,
        SaveLayer::CriuCheckpoint,
        SaveLayer::ReplayLog,
        SaveLayer::MemoryRecord,
        SaveLayer::ProfileState,
    ];
}

/// A captured save-state — the set of layers that have been written.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SaveState {
    captured: BTreeSet<SaveLayer>,
}

impl SaveState {
    /// A new, empty save-state.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Record that a layer has been captured.
    pub fn capture(&mut self, layer: SaveLayer) {
        self.captured.insert(layer);
    }

    /// Whether a layer has been captured.
    #[must_use]
    pub fn has(&self, layer: SaveLayer) -> bool {
        self.captured.contains(&layer)
    }

    /// The layers still missing for a true save-state.
    #[must_use]
    pub fn missing_layers(&self) -> Vec<SaveLayer> {
        SaveLayer::ALL
            .into_iter()
            .filter(|l| !self.captured.contains(l))
            .collect()
    }

    /// A TRUE save-state requires all five layers. A partial capture (e.g. a
    /// ZFS snapshot without the CRIU checkpoint, or without the replay log that
    /// records *why*) is restorable but not a complete agent save-state.
    #[must_use]
    pub fn is_true_save_state(&self) -> bool {
        self.missing_layers().is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn five_layers() {
        assert_eq!(SaveLayer::ALL.len(), 5);
    }

    #[test]
    fn empty_state_is_not_true_and_misses_all() {
        let s = SaveState::new();
        assert!(!s.is_true_save_state());
        assert_eq!(s.missing_layers().len(), 5);
    }

    #[test]
    fn all_five_layers_make_a_true_save_state() {
        let mut s = SaveState::new();
        for l in SaveLayer::ALL {
            s.capture(l);
        }
        assert!(s.is_true_save_state());
        assert!(s.missing_layers().is_empty());
        assert!(s.has(SaveLayer::ReplayLog));
    }

    #[test]
    fn zfs_plus_criu_alone_is_not_a_true_save_state() {
        // The classic partial: files + process, but no replay/memory/profile.
        let mut s = SaveState::new();
        s.capture(SaveLayer::ZfsSnapshot);
        s.capture(SaveLayer::CriuCheckpoint);
        assert!(!s.is_true_save_state());
        let missing = s.missing_layers();
        assert!(missing.contains(&SaveLayer::ReplayLog));
        assert!(missing.contains(&SaveLayer::MemoryRecord));
        assert!(missing.contains(&SaveLayer::ProfileState));
    }

    #[test]
    fn serde_roundtrip_and_kebab() {
        let mut s = SaveState::new();
        s.capture(SaveLayer::ProfileState);
        let j = serde_json::to_string(&s).unwrap();
        let back: SaveState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        assert_eq!(
            serde_json::to_string(&SaveLayer::CriuCheckpoint).unwrap(),
            "\"criu-checkpoint\""
        );
    }
}
