//! `sovereign-observability-fabric` — M048 Module 9 9-source aggregator.
//!
//! Per M048 + E0465 + M00811 + R08149-R08150 + dump 14728-14744.
//!
//! 9 sources + 6 questions answered.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 9 observability sources per R08149 dump 14728-14736.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObservabilitySource {
    /// 1. OpenTelemetry traces.
    OtelTraces,
    /// 2. journald.
    Journald,
    /// 3. DCGM (NVIDIA GPU telemetry).
    Dcgm,
    /// 4. PSI (pressure stall information).
    Psi,
    /// 5. eBPF programs.
    Ebpf,
    /// 6. ZFS events (zfs.events / zpool).
    ZfsEvents,
    /// 7. Test output (CI + L1-L5 layers).
    TestOutput,
    /// 8. Gateway logs (Anthropic-first + provider-inversion ledger).
    GatewayLogs,
    /// 9. Cost ledger.
    CostLedger,
}

impl ObservabilitySource {
    /// Canonical 1..9.
    pub fn position(self) -> u8 {
        match self {
            ObservabilitySource::OtelTraces => 1,
            ObservabilitySource::Journald => 2,
            ObservabilitySource::Dcgm => 3,
            ObservabilitySource::Psi => 4,
            ObservabilitySource::Ebpf => 5,
            ObservabilitySource::ZfsEvents => 6,
            ObservabilitySource::TestOutput => 7,
            ObservabilitySource::GatewayLogs => 8,
            ObservabilitySource::CostLedger => 9,
        }
    }
}

/// 6 questions answered per R08150 dump 14740-14744.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ObservabilityQuestion {
    /// 1. What happened?
    WhatHappened,
    /// 2. What changed?
    WhatChanged,
    /// 3. Which model decided?
    ModelDecided,
    /// 4. Which policy allowed it?
    PolicyAllowed,
    /// 5. What did it cost?
    Cost,
    /// 6. What pressure did hardware experience?
    HardwarePressure,
}

impl ObservabilityQuestion {
    /// Canonical 1..6.
    pub fn position(self) -> u8 {
        match self {
            ObservabilityQuestion::WhatHappened => 1,
            ObservabilityQuestion::WhatChanged => 2,
            ObservabilityQuestion::ModelDecided => 3,
            ObservabilityQuestion::PolicyAllowed => 4,
            ObservabilityQuestion::Cost => 5,
            ObservabilityQuestion::HardwarePressure => 6,
        }
    }
    /// Verbatim text per R08150 dump 14740-14744.
    pub fn text(self) -> &'static str {
        match self {
            ObservabilityQuestion::WhatHappened => "what happened?",
            ObservabilityQuestion::WhatChanged => "what changed?",
            ObservabilityQuestion::ModelDecided => "which model decided?",
            ObservabilityQuestion::PolicyAllowed => "which policy allowed it?",
            ObservabilityQuestion::Cost => "what did it cost?",
            ObservabilityQuestion::HardwarePressure => "what pressure did hardware experience?",
        }
    }
}

/// Source connection state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SourceState {
    /// Connected + emitting.
    Connected,
    /// Connected but no recent events.
    Idle,
    /// Disconnected (transient).
    Disconnected,
    /// Permanently disabled by operator.
    Disabled,
}

/// One source connection record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SourceRecord {
    /// Source kind.
    pub source: ObservabilitySource,
    /// Current state.
    pub state: SourceState,
    /// Event-per-second rate (last sample).
    pub eps: u32,
    /// ISO-8601 UTC last heartbeat.
    pub last_heartbeat_at: String,
}

/// Top-level fabric envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ObservabilityFabric {
    /// Schema version.
    pub schema_version: String,
    /// 9 source records (MUST be exactly 9).
    pub sources: Vec<SourceRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FabricError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Source count != 9.
    #[error("source count {0} != 9 canonical observability sources")]
    SourceCountInvalid(usize),
    /// Required source missing.
    #[error("required source missing: {0:?}")]
    SourceMissing(ObservabilitySource),
    /// Duplicate source.
    #[error("duplicate source: {0:?}")]
    DuplicateSource(ObservabilitySource),
}

impl ObservabilityFabric {
    /// Construct an empty canonical fabric.
    pub fn empty_canonical() -> Self {
        let now = "2026-05-19T00:00:00Z";
        let sources = [
            ObservabilitySource::OtelTraces,
            ObservabilitySource::Journald,
            ObservabilitySource::Dcgm,
            ObservabilitySource::Psi,
            ObservabilitySource::Ebpf,
            ObservabilitySource::ZfsEvents,
            ObservabilitySource::TestOutput,
            ObservabilitySource::GatewayLogs,
            ObservabilitySource::CostLedger,
        ]
        .into_iter()
        .map(|s| SourceRecord {
            source: s,
            state: SourceState::Disconnected,
            eps: 0,
            last_heartbeat_at: now.into(),
        })
        .collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            sources,
        }
    }

    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), FabricError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FabricError::SchemaMismatch);
        }
        if self.sources.len() != 9 {
            return Err(FabricError::SourceCountInvalid(self.sources.len()));
        }
        let required = [
            ObservabilitySource::OtelTraces,
            ObservabilitySource::Journald,
            ObservabilitySource::Dcgm,
            ObservabilitySource::Psi,
            ObservabilitySource::Ebpf,
            ObservabilitySource::ZfsEvents,
            ObservabilitySource::TestOutput,
            ObservabilitySource::GatewayLogs,
            ObservabilitySource::CostLedger,
        ];
        for s in required {
            if !self.sources.iter().any(|r| r.source == s) {
                return Err(FabricError::SourceMissing(s));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<ObservabilitySource> = HashSet::new();
        for r in &self.sources {
            if !seen.insert(r.source) {
                return Err(FabricError::DuplicateSource(r.source));
            }
        }
        Ok(())
    }

    /// Total EPS across connected sources.
    pub fn total_eps(&self) -> u64 {
        self.sources
            .iter()
            .filter(|r| r.state == SourceState::Connected)
            .map(|r| r.eps as u64)
            .sum()
    }

    /// Count of connected sources.
    pub fn connected_count(&self) -> usize {
        self.sources
            .iter()
            .filter(|r| r.state == SourceState::Connected)
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nine_sources_positioned_1_to_9() {
        for (s, p) in [
            (ObservabilitySource::OtelTraces, 1),
            (ObservabilitySource::Journald, 2),
            (ObservabilitySource::Dcgm, 3),
            (ObservabilitySource::Psi, 4),
            (ObservabilitySource::Ebpf, 5),
            (ObservabilitySource::ZfsEvents, 6),
            (ObservabilitySource::TestOutput, 7),
            (ObservabilitySource::GatewayLogs, 8),
            (ObservabilitySource::CostLedger, 9),
        ] {
            assert_eq!(s.position(), p);
        }
    }

    #[test]
    fn six_questions_positioned_1_to_6() {
        for (q, p) in [
            (ObservabilityQuestion::WhatHappened, 1),
            (ObservabilityQuestion::WhatChanged, 2),
            (ObservabilityQuestion::ModelDecided, 3),
            (ObservabilityQuestion::PolicyAllowed, 4),
            (ObservabilityQuestion::Cost, 5),
            (ObservabilityQuestion::HardwarePressure, 6),
        ] {
            assert_eq!(q.position(), p);
        }
    }

    #[test]
    fn six_questions_text_verbatim() {
        assert_eq!(ObservabilityQuestion::WhatHappened.text(), "what happened?");
        assert_eq!(ObservabilityQuestion::WhatChanged.text(), "what changed?");
        assert_eq!(
            ObservabilityQuestion::ModelDecided.text(),
            "which model decided?"
        );
        assert_eq!(
            ObservabilityQuestion::PolicyAllowed.text(),
            "which policy allowed it?"
        );
        assert_eq!(ObservabilityQuestion::Cost.text(), "what did it cost?");
        assert_eq!(
            ObservabilityQuestion::HardwarePressure.text(),
            "what pressure did hardware experience?"
        );
    }

    #[test]
    fn empty_canonical_validates() {
        ObservabilityFabric::empty_canonical().validate().unwrap();
    }

    #[test]
    fn source_count_invalid_rejected() {
        let mut f = ObservabilityFabric::empty_canonical();
        f.sources.pop();
        assert!(matches!(
            f.validate().unwrap_err(),
            FabricError::SourceCountInvalid(8)
        ));
    }

    #[test]
    fn missing_source_caught_when_replaced() {
        let mut f = ObservabilityFabric::empty_canonical();
        f.sources[0] = SourceRecord {
            source: ObservabilitySource::Journald, // duplicate
            state: SourceState::Disconnected,
            eps: 0,
            last_heartbeat_at: "ts".into(),
        };
        let err = f.validate().unwrap_err();
        assert!(matches!(
            err,
            FabricError::SourceMissing(ObservabilitySource::OtelTraces)
                | FabricError::DuplicateSource(ObservabilitySource::Journald)
        ));
    }

    #[test]
    fn total_eps_sums_connected_only() {
        let mut f = ObservabilityFabric::empty_canonical();
        f.sources[0].state = SourceState::Connected;
        f.sources[0].eps = 100;
        f.sources[1].state = SourceState::Connected;
        f.sources[1].eps = 50;
        f.sources[2].state = SourceState::Disconnected;
        f.sources[2].eps = 9999;
        assert_eq!(f.total_eps(), 150);
    }

    #[test]
    fn connected_count_filters() {
        let mut f = ObservabilityFabric::empty_canonical();
        f.sources[0].state = SourceState::Connected;
        f.sources[1].state = SourceState::Idle;
        f.sources[2].state = SourceState::Disabled;
        assert_eq!(f.connected_count(), 1);
    }

    #[test]
    fn source_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ObservabilitySource::OtelTraces).unwrap(),
            "\"otel-traces\""
        );
        assert_eq!(
            serde_json::to_string(&ObservabilitySource::ZfsEvents).unwrap(),
            "\"zfs-events\""
        );
        assert_eq!(
            serde_json::to_string(&ObservabilitySource::CostLedger).unwrap(),
            "\"cost-ledger\""
        );
    }

    #[test]
    fn question_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ObservabilityQuestion::WhatHappened).unwrap(),
            "\"what-happened\""
        );
        assert_eq!(
            serde_json::to_string(&ObservabilityQuestion::HardwarePressure).unwrap(),
            "\"hardware-pressure\""
        );
        assert_eq!(
            serde_json::to_string(&ObservabilityQuestion::PolicyAllowed).unwrap(),
            "\"policy-allowed\""
        );
    }

    #[test]
    fn fabric_serde_roundtrip() {
        let f = ObservabilityFabric::empty_canonical();
        let j = serde_json::to_string(&f).unwrap();
        let back: ObservabilityFabric = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
