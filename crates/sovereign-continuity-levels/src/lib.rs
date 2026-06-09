//! `sovereign-continuity-levels` — E0456: the 8-level continuity ladder.
//!
//! "Continuity turns inference into practice." Continuity has depth: from a
//! stateless API call up to user-sovereign life continuity. The sovereign
//! advantage is that a cloud provider typically gives you only the shallow
//! levels (0–2), while the station owns the deep ones (3–7) — warm filesystem
//! snapshots, process checkpoints, warm KV context, learned policy, and a
//! continuous life of work. This crate fixes the ladder and that ownership
//! boundary.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 8 continuity levels (E0456), shallow → deep.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ContinuityLevel {
    /// 0. Stateless API call.
    StatelessApiCall,
    /// 1. Conversation memory.
    ConversationMemory,
    /// 2. Workflow checkpoint.
    WorkflowCheckpoint,
    /// 3. Filesystem snapshot.
    FilesystemSnapshot,
    /// 4. Process / container checkpoint.
    ProcessContainerCheckpoint,
    /// 5. Warm model / KV context.
    WarmModelKvContext,
    /// 6. Learned skill / profile / policy.
    LearnedSkillProfilePolicy,
    /// 7. User-sovereign life continuity.
    UserSovereignLifeContinuity,
}

impl ContinuityLevel {
    /// All 8 levels, shallow first.
    pub const ALL: [ContinuityLevel; 8] = [
        ContinuityLevel::StatelessApiCall,
        ContinuityLevel::ConversationMemory,
        ContinuityLevel::WorkflowCheckpoint,
        ContinuityLevel::FilesystemSnapshot,
        ContinuityLevel::ProcessContainerCheckpoint,
        ContinuityLevel::WarmModelKvContext,
        ContinuityLevel::LearnedSkillProfilePolicy,
        ContinuityLevel::UserSovereignLifeContinuity,
    ];

    /// Depth 0..=7.
    #[must_use]
    pub fn depth(self) -> u8 {
        Self::ALL.iter().position(|l| *l == self).unwrap() as u8
    }

    /// Whether a typical cloud provider reaches this level (only 0–2).
    #[must_use]
    pub fn is_cloud_typical(self) -> bool {
        self.depth() <= 2
    }

    /// Whether the sovereign station owns this level (3–7) — the levels a cloud
    /// rarely provides.
    #[must_use]
    pub fn is_station_owned(self) -> bool {
        self.depth() >= 3
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eight_levels_ordered_by_depth() {
        assert_eq!(ContinuityLevel::ALL.len(), 8);
        assert_eq!(ContinuityLevel::StatelessApiCall.depth(), 0);
        assert_eq!(ContinuityLevel::UserSovereignLifeContinuity.depth(), 7);
        // ordering matches depth.
        for w in ContinuityLevel::ALL.windows(2) {
            assert!(w[0].depth() < w[1].depth());
        }
    }

    #[test]
    fn cloud_owns_shallow_station_owns_deep() {
        // The E0456 boundary: cloud 0-2, station 3-7, partition is total.
        let cloud = ContinuityLevel::ALL.iter().filter(|l| l.is_cloud_typical()).count();
        let station = ContinuityLevel::ALL.iter().filter(|l| l.is_station_owned()).count();
        assert_eq!(cloud, 3);
        assert_eq!(station, 5);
        for l in ContinuityLevel::ALL {
            assert_ne!(l.is_cloud_typical(), l.is_station_owned(), "{l:?}");
        }
    }

    #[test]
    fn the_advantage_levels_are_station_owned() {
        for l in [
            ContinuityLevel::FilesystemSnapshot,
            ContinuityLevel::ProcessContainerCheckpoint,
            ContinuityLevel::WarmModelKvContext,
            ContinuityLevel::LearnedSkillProfilePolicy,
            ContinuityLevel::UserSovereignLifeContinuity,
        ] {
            assert!(l.is_station_owned(), "{l:?}");
            assert!(!l.is_cloud_typical(), "{l:?}");
        }
    }

    #[test]
    fn serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ContinuityLevel::WarmModelKvContext).unwrap(),
            "\"warm-model-kv-context\""
        );
    }
}
