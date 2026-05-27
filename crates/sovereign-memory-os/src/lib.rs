//! `sovereign-memory-os` — M028 8-memory-type registry + admission lifecycle.
//!
//! Per M028 + M00459-M00465 + E0260 + E0264 + E0265 + dump 8121-8474:
//!
//! ## 8 memory types
//!
//! 1. **Working** (M00459) — current task / active branches / local facts
//! 2. **Episodic** (M00460) — full traces / conversations / failures
//! 3. **Semantic** (M00461) — distilled facts / concepts / project knowledge
//! 4. **Procedural** (M00462) — skills / workflows / command recipes
//! 5. **TemporalGraph** (M00463) — entities / relationships / timestamps
//! 6. **Value** (M00464) — what worked / what failed / which model succeeded
//! 7. **KV** (M00465) — cached prefixes / reusable prompt blocks
//! 8. **Reward** (E0265 verbatim) — local experience base; reward signals
//!
//! ## 11-stage admission lifecycle (E0264 + M00471)
//!
//! observe → classify → quarantine → link → score → store-raw →
//! extract-facts → verify → promote → decay → archive
//!
//! Doctrine surface preserved verbatim per E0267 dump 8423-8474:
//!
//! > "Intelligence improves when memory stops being recall and becomes adaptive state"
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface preserved verbatim per E0267 dump 8423-8474.
pub const DOCTRINE_MEMORY_ADAPTIVE_STATE: &str =
    "Intelligence improves when memory stops being recall and becomes adaptive state";

/// 8 memory types per M00459-M00465 + E0265.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum MemoryType {
    /// Working memory (M00459) — current task scratch.
    Working,
    /// Episodic memory (M00460) — full traces.
    Episodic,
    /// Semantic memory (M00461) — distilled facts.
    Semantic,
    /// Procedural memory (M00462) — skills & workflows.
    Procedural,
    /// Temporal-graph memory (M00463) — entities + timestamps.
    TemporalGraph,
    /// Value memory (M00464) — what worked / what failed.
    Value,
    /// KV memory (M00465) — cached prefixes / prompt blocks.
    Kv,
    /// Reward memory (E0265) — local experience base.
    Reward,
}

impl MemoryType {
    /// Canonical ordering 1..8.
    pub fn index(self) -> u8 {
        match self {
            MemoryType::Working => 1,
            MemoryType::Episodic => 2,
            MemoryType::Semantic => 3,
            MemoryType::Procedural => 4,
            MemoryType::TemporalGraph => 5,
            MemoryType::Value => 6,
            MemoryType::Kv => 7,
            MemoryType::Reward => 8,
        }
    }
}

/// 11-stage admission lifecycle per E0264 + M00471 + dump 8295-8308.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum LifecycleStage {
    /// 1. Observe — incoming data noticed.
    Observe,
    /// 2. Classify — memory type assigned.
    Classify,
    /// 3. Quarantine — pending integrity check.
    Quarantine,
    /// 4. Link — wired into existing graph.
    Link,
    /// 5. Score — value-plane scoring applied.
    Score,
    /// 6. StoreRaw — raw episode persisted.
    StoreRaw,
    /// 7. ExtractFacts — facts distilled.
    ExtractFacts,
    /// 8. Verify — facts checked against sources.
    Verify,
    /// 9. Promote — promoted to long-term store.
    Promote,
    /// 10. Decay — TTL-driven decay applied.
    Decay,
    /// 11. Archive — moved to cold storage.
    Archive,
}

impl LifecycleStage {
    /// Canonical position 1..11.
    pub fn position(self) -> u8 {
        match self {
            LifecycleStage::Observe => 1,
            LifecycleStage::Classify => 2,
            LifecycleStage::Quarantine => 3,
            LifecycleStage::Link => 4,
            LifecycleStage::Score => 5,
            LifecycleStage::StoreRaw => 6,
            LifecycleStage::ExtractFacts => 7,
            LifecycleStage::Verify => 8,
            LifecycleStage::Promote => 9,
            LifecycleStage::Decay => 10,
            LifecycleStage::Archive => 11,
        }
    }

    /// Next stage per the canonical pipeline. Archive returns None (terminal).
    pub fn next(self) -> Option<Self> {
        match self {
            LifecycleStage::Observe => Some(LifecycleStage::Classify),
            LifecycleStage::Classify => Some(LifecycleStage::Quarantine),
            LifecycleStage::Quarantine => Some(LifecycleStage::Link),
            LifecycleStage::Link => Some(LifecycleStage::Score),
            LifecycleStage::Score => Some(LifecycleStage::StoreRaw),
            LifecycleStage::StoreRaw => Some(LifecycleStage::ExtractFacts),
            LifecycleStage::ExtractFacts => Some(LifecycleStage::Verify),
            LifecycleStage::Verify => Some(LifecycleStage::Promote),
            LifecycleStage::Promote => Some(LifecycleStage::Decay),
            LifecycleStage::Decay => Some(LifecycleStage::Archive),
            LifecycleStage::Archive => None,
        }
    }
}

/// One memory item record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MemoryItem {
    /// ULID identifier.
    pub id: String,
    /// Memory type discriminator.
    pub memory_type: MemoryType,
    /// Current lifecycle stage.
    pub stage: LifecycleStage,
    /// ISO-8601 UTC observation timestamp.
    pub observed_at: String,
    /// ISO-8601 UTC last-update timestamp.
    pub updated_at: String,
    /// Trust score 0..1000 from Value Plane.
    pub trust_score: u16,
    /// Free-form payload (publisher fills schema per type).
    pub payload: String,
    /// MS003 signature over canonical-JSON encoding (hex).
    pub signature: String,
}

/// Per-type aggregate count.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TypeSummary {
    /// Memory type.
    pub memory_type: MemoryType,
    /// Total items in this type.
    pub total: u32,
    /// Items currently at each stage.
    pub stage_counts: [u32; 11],
}

/// Top-level Memory OS snapshot.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MemoryOsSnapshot {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// Doctrine surface — MUST equal [`DOCTRINE_MEMORY_ADAPTIVE_STATE`].
    pub doctrine: String,
    /// ISO-8601 UTC capture timestamp.
    pub captured_at: String,
    /// Per-type aggregate counts.
    pub summaries: Vec<TypeSummary>,
    /// Sample of recent items (bounded tail).
    pub items: Vec<MemoryItem>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum MemoryError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Doctrine surface tampered (E0267 verbatim).
    #[error("doctrine surface tampered: expected verbatim \"{expected}\"")]
    DoctrineTampered {
        /// Expected.
        expected: String,
    },
    /// Trust score outside 0..=1000 range.
    #[error("trust_score {0} outside 0..=1000")]
    TrustScoreOutOfRange(u16),
    /// Lifecycle attempted to skip stages.
    #[error("lifecycle transition from {from:?} to {to:?} skips stages (not allowed)")]
    LifecycleSkip {
        /// Current stage.
        from: LifecycleStage,
        /// Requested next stage.
        to: LifecycleStage,
    },
    /// Lifecycle attempted to move past terminal Archive.
    #[error("lifecycle attempted to advance past terminal Archive stage")]
    LifecycleTerminal,
}

impl MemoryOsSnapshot {
    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), MemoryError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(MemoryError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.doctrine != DOCTRINE_MEMORY_ADAPTIVE_STATE {
            return Err(MemoryError::DoctrineTampered {
                expected: DOCTRINE_MEMORY_ADAPTIVE_STATE.into(),
            });
        }
        for item in &self.items {
            if item.trust_score > 1000 {
                return Err(MemoryError::TrustScoreOutOfRange(item.trust_score));
            }
        }
        Ok(())
    }

    /// Aggregate item list into per-type summaries (cross-check helper).
    pub fn recompute_summaries(&self) -> Vec<TypeSummary> {
        use std::collections::HashMap;
        let mut by_type: HashMap<MemoryType, TypeSummary> = HashMap::new();
        for item in &self.items {
            let entry = by_type.entry(item.memory_type).or_insert(TypeSummary {
                memory_type: item.memory_type,
                total: 0,
                stage_counts: [0; 11],
            });
            entry.total += 1;
            let idx = (item.stage.position() as usize).saturating_sub(1);
            if idx < 11 {
                entry.stage_counts[idx] += 1;
            }
        }
        let mut out: Vec<TypeSummary> = by_type.into_values().collect();
        out.sort_by_key(|s| s.memory_type.index());
        out
    }
}

/// Advance one item to its next lifecycle stage. Refuses to skip ahead.
pub fn advance_stage(item: &mut MemoryItem, target: LifecycleStage) -> Result<(), MemoryError> {
    let next = item.stage.next().ok_or(MemoryError::LifecycleTerminal)?;
    if next != target {
        return Err(MemoryError::LifecycleSkip {
            from: item.stage,
            to: target,
        });
    }
    item.stage = target;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_item(mt: MemoryType, stage: LifecycleStage, trust: u16) -> MemoryItem {
        MemoryItem {
            id: format!("mem-{}-{}", mt.index(), stage.position()),
            memory_type: mt,
            stage,
            observed_at: "2026-05-19T00:00:00Z".into(),
            updated_at: "2026-05-19T03:00:00Z".into(),
            trust_score: trust,
            payload: "ok".into(),
            signature: "sig".into(),
        }
    }
    fn mk_snap(items: Vec<MemoryItem>) -> MemoryOsSnapshot {
        MemoryOsSnapshot {
            schema_version: SCHEMA_VERSION.into(),
            doctrine: DOCTRINE_MEMORY_ADAPTIVE_STATE.into(),
            captured_at: "2026-05-19T03:30:00Z".into(),
            summaries: vec![],
            items,
        }
    }

    // --- 8 memory types ---

    #[test]
    fn eight_memory_types_indexed_1_through_8() {
        let order = [
            (MemoryType::Working, 1),
            (MemoryType::Episodic, 2),
            (MemoryType::Semantic, 3),
            (MemoryType::Procedural, 4),
            (MemoryType::TemporalGraph, 5),
            (MemoryType::Value, 6),
            (MemoryType::Kv, 7),
            (MemoryType::Reward, 8),
        ];
        for (t, i) in order {
            assert_eq!(t.index(), i, "type {t:?}");
        }
    }

    #[test]
    fn memory_type_serde_kebab_case() {
        assert_eq!(
            serde_json::to_string(&MemoryType::TemporalGraph).unwrap(),
            "\"temporal-graph\""
        );
        assert_eq!(
            serde_json::to_string(&MemoryType::Reward).unwrap(),
            "\"reward\""
        );
        assert_eq!(serde_json::to_string(&MemoryType::Kv).unwrap(), "\"kv\"");
    }

    // --- 11-stage lifecycle ---

    #[test]
    fn eleven_stages_positioned_1_through_11() {
        let order = [
            (LifecycleStage::Observe, 1),
            (LifecycleStage::Classify, 2),
            (LifecycleStage::Quarantine, 3),
            (LifecycleStage::Link, 4),
            (LifecycleStage::Score, 5),
            (LifecycleStage::StoreRaw, 6),
            (LifecycleStage::ExtractFacts, 7),
            (LifecycleStage::Verify, 8),
            (LifecycleStage::Promote, 9),
            (LifecycleStage::Decay, 10),
            (LifecycleStage::Archive, 11),
        ];
        for (s, p) in order {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn next_chain_walks_through_all_11() {
        let mut s = LifecycleStage::Observe;
        let mut visited = vec![s];
        while let Some(n) = s.next() {
            visited.push(n);
            s = n;
        }
        assert_eq!(visited.len(), 11);
        assert_eq!(visited[0], LifecycleStage::Observe);
        assert_eq!(visited[10], LifecycleStage::Archive);
    }

    #[test]
    fn archive_terminal() {
        assert_eq!(LifecycleStage::Archive.next(), None);
    }

    #[test]
    fn lifecycle_stage_serde_kebab_case() {
        assert_eq!(
            serde_json::to_string(&LifecycleStage::StoreRaw).unwrap(),
            "\"store-raw\""
        );
        assert_eq!(
            serde_json::to_string(&LifecycleStage::ExtractFacts).unwrap(),
            "\"extract-facts\""
        );
    }

    // --- Snapshot validation ---

    #[test]
    fn canonical_snapshot_validates() {
        mk_snap(vec![]).validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = mk_snap(vec![]);
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            MemoryError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn doctrine_tamper_caught() {
        let mut s = mk_snap(vec![]);
        s.doctrine = "memory is just recall".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            MemoryError::DoctrineTampered { .. }
        ));
    }

    #[test]
    fn trust_score_over_1000_rejected() {
        let snap = mk_snap(vec![mk_item(
            MemoryType::Semantic,
            LifecycleStage::Promote,
            1500,
        )]);
        assert!(matches!(
            snap.validate().unwrap_err(),
            MemoryError::TrustScoreOutOfRange(1500)
        ));
    }

    // --- recompute_summaries ---

    #[test]
    fn summaries_group_by_type_and_stage() {
        let snap = mk_snap(vec![
            mk_item(MemoryType::Semantic, LifecycleStage::Promote, 800),
            mk_item(MemoryType::Semantic, LifecycleStage::Promote, 850),
            mk_item(MemoryType::Semantic, LifecycleStage::Decay, 200),
            mk_item(MemoryType::Working, LifecycleStage::Observe, 500),
            mk_item(MemoryType::Reward, LifecycleStage::Verify, 700),
        ]);
        let s = snap.recompute_summaries();
        assert_eq!(s.len(), 3);
        let sem = s
            .iter()
            .find(|x| x.memory_type == MemoryType::Semantic)
            .unwrap();
        assert_eq!(sem.total, 3);
        assert_eq!(sem.stage_counts[8], 2); // Promote = position 9 → index 8
        assert_eq!(sem.stage_counts[9], 1); // Decay = position 10 → index 9
        let working = s
            .iter()
            .find(|x| x.memory_type == MemoryType::Working)
            .unwrap();
        assert_eq!(working.stage_counts[0], 1); // Observe = position 1 → index 0
    }

    // --- advance_stage ---

    #[test]
    fn advance_to_next_stage_succeeds() {
        let mut item = mk_item(MemoryType::Working, LifecycleStage::Observe, 500);
        advance_stage(&mut item, LifecycleStage::Classify).unwrap();
        assert_eq!(item.stage, LifecycleStage::Classify);
    }

    #[test]
    fn advance_skipping_stages_refused() {
        let mut item = mk_item(MemoryType::Working, LifecycleStage::Observe, 500);
        let err = advance_stage(&mut item, LifecycleStage::Promote).unwrap_err();
        assert!(matches!(err, MemoryError::LifecycleSkip { .. }));
        // State unchanged
        assert_eq!(item.stage, LifecycleStage::Observe);
    }

    #[test]
    fn advance_past_archive_refused() {
        let mut item = mk_item(MemoryType::Episodic, LifecycleStage::Archive, 100);
        assert!(matches!(
            advance_stage(&mut item, LifecycleStage::Observe).unwrap_err(),
            MemoryError::LifecycleTerminal
        ));
    }

    // --- Doctrine ---

    #[test]
    fn doctrine_verbatim() {
        assert_eq!(
            DOCTRINE_MEMORY_ADAPTIVE_STATE,
            "Intelligence improves when memory stops being recall and becomes adaptive state"
        );
    }

    // --- Serde ---

    #[test]
    fn snapshot_serde_roundtrip() {
        let snap = mk_snap(vec![
            mk_item(MemoryType::Procedural, LifecycleStage::Score, 750),
            mk_item(MemoryType::TemporalGraph, LifecycleStage::Link, 600),
        ]);
        let j = serde_json::to_string(&snap).unwrap();
        let back: MemoryOsSnapshot = serde_json::from_str(&j).unwrap();
        assert_eq!(snap, back);
    }

    #[test]
    fn type_summary_stage_counts_array_size_11() {
        let s = TypeSummary {
            memory_type: MemoryType::Kv,
            total: 0,
            stage_counts: [0; 11],
        };
        assert_eq!(s.stage_counts.len(), 11);
    }
}
