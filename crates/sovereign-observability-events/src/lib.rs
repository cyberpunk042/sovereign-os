//! `sovereign-observability-events` — E0470 / M00818 + M00819: the runtime
//! observability event taxonomy + span schema.
//!
//! "Every module must leave traces that can feed adaptation … A task no longer
//! disappears when the answer is done. It becomes part of the system's
//! experience." OTel-aligned, vendor-neutral ("lock into trace semantics, not
//! UI"). This crate fixes the catalogued contract: the event kinds every
//! module emits, and the span fields each event carries. `branch_id`/`trace_id`
//! are the [`sovereign_trace_context`] types, so an event slots straight into a
//! reconstructable trace (E0112).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_trace_context::{BranchId, TraceId};

/// The runtime observability event taxonomy (M00818, features F04095–F04109).
///
/// The catalogue titles this the "16-event taxonomy" but enumerates fifteen
/// events (F04095–F04109); [`EventKind::ALL`] is the authoritative set.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventKind {
    /// A model (oracle/scout/cloud) inference call.
    ModelCall,
    /// A tool invocation.
    ToolCall,
    /// A memory read.
    MemoryRead,
    /// A memory write.
    MemoryWrite,
    /// A routing decision (which tier/model).
    RouteDecision,
    /// A policy decision (allow/deny).
    PolicyDecision,
    /// A sandbox started.
    SandboxStart,
    /// A sandbox stopped.
    SandboxStop,
    /// A test run.
    TestRun,
    /// An eval score recorded.
    EvalScore,
    /// A continuity checkpoint.
    Checkpoint,
    /// A rollback to a checkpoint.
    Rollback,
    /// A human approval gate.
    HumanGate,
    /// A cloud provider call.
    CloudCall,
    /// A cost event (spend recorded).
    CostEvent,
}

impl EventKind {
    /// All fifteen catalogued event kinds, in F04095–F04109 order.
    pub const ALL: [EventKind; 15] = [
        EventKind::ModelCall,
        EventKind::ToolCall,
        EventKind::MemoryRead,
        EventKind::MemoryWrite,
        EventKind::RouteDecision,
        EventKind::PolicyDecision,
        EventKind::SandboxStart,
        EventKind::SandboxStop,
        EventKind::TestRun,
        EventKind::EvalScore,
        EventKind::Checkpoint,
        EventKind::Rollback,
        EventKind::HumanGate,
        EventKind::CloudCall,
        EventKind::CostEvent,
    ];

    /// The snake_case wire name (e.g. `model_call`).
    #[must_use]
    pub fn wire(self) -> &'static str {
        match self {
            EventKind::ModelCall => "model_call",
            EventKind::ToolCall => "tool_call",
            EventKind::MemoryRead => "memory_read",
            EventKind::MemoryWrite => "memory_write",
            EventKind::RouteDecision => "route_decision",
            EventKind::PolicyDecision => "policy_decision",
            EventKind::SandboxStart => "sandbox_start",
            EventKind::SandboxStop => "sandbox_stop",
            EventKind::TestRun => "test_run",
            EventKind::EvalScore => "eval_score",
            EventKind::Checkpoint => "checkpoint",
            EventKind::Rollback => "rollback",
            EventKind::HumanGate => "human_gate",
            EventKind::CloudCall => "cloud_call",
            EventKind::CostEvent => "cost_event",
        }
    }
}

/// The 13-field observability span (M00819, features F04110-family).
///
/// One span per event. The five core attribution fields plus token/latency/
/// cost/risk measurement, the memory/tool references it touched, the policy
/// result that governed it, and the trace coordinates that place it in a
/// reconstructable trace (E0112). Optional fields are `None` when the event
/// kind doesn't carry them (e.g. a `checkpoint` has no `model`/`tokens`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ObservabilitySpan {
    /// Which event this span records.
    pub kind: EventKind,
    /// 1. profile in effect.
    pub profile: String,
    /// 2. model name (if a model was involved).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// 3. provider (anthropic/local/…).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    /// 4. hardware target the work ran on.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hardware: Option<String>,
    /// 5. tokens consumed.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tokens: Option<u64>,
    /// 6. latency in milliseconds.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<u64>,
    /// 7. cost (USD).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cost: Option<f64>,
    /// 8. risk label/score for the action.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub risk: Option<String>,
    /// 9. memory object ids this span touched.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub memory_refs: Vec<String>,
    /// 10. tool ids this span touched.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tool_refs: Vec<String>,
    /// 11. policy decision that governed the span (allow/deny/…).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub policy_result: Option<String>,
    /// 12. runtime branch this span belongs to (E0112).
    pub branch_id: BranchId,
    /// 13. user-request trace this span belongs to (E0112).
    pub trace_id: TraceId,
}

impl ObservabilitySpan {
    /// A minimal span: the kind, profile, and trace coordinates. Optional
    /// measurement/reference fields default empty and are filled per event.
    #[must_use]
    pub fn new(
        kind: EventKind,
        profile: impl Into<String>,
        trace_id: TraceId,
        branch_id: BranchId,
    ) -> Self {
        Self {
            kind,
            profile: profile.into(),
            model: None,
            provider: None,
            hardware: None,
            tokens: None,
            latency_ms: None,
            cost: None,
            risk: None,
            memory_refs: Vec::new(),
            tool_refs: Vec::new(),
            policy_result: None,
            branch_id,
            trace_id,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn taxonomy_has_fifteen_distinct_events() {
        assert_eq!(EventKind::ALL.len(), 15);
        // distinct
        use std::collections::HashSet;
        let set: HashSet<_> = EventKind::ALL.iter().collect();
        assert_eq!(set.len(), 15);
    }

    #[test]
    fn wire_names_match_catalogue_and_serde() {
        // wire() and the serde snake_case rename must agree, and match the
        // catalogued F04095–F04109 names.
        assert_eq!(EventKind::ModelCall.wire(), "model_call");
        assert_eq!(EventKind::CostEvent.wire(), "cost_event");
        assert_eq!(EventKind::HumanGate.wire(), "human_gate");
        for k in EventKind::ALL {
            let json = serde_json::to_string(&k).unwrap();
            assert_eq!(json, format!("\"{}\"", k.wire()), "{k:?}");
        }
    }

    #[test]
    fn span_carries_trace_coordinates_and_roundtrips() {
        let mut s = ObservabilitySpan::new(
            EventKind::ModelCall,
            "inference-ready",
            TraceId(0xabc),
            BranchId(7),
        );
        s.model = Some("oracle".into());
        s.provider = Some("local".into());
        s.tokens = Some(1234);
        s.cost = Some(0.0);
        s.policy_result = Some("allow".into());
        s.memory_refs = vec!["m1".into(), "m2".into()];

        let j = serde_json::to_string(&s).unwrap();
        let back: ObservabilitySpan = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
        // trace coordinates are the E0112 types.
        assert_eq!(back.trace_id, TraceId(0xabc));
        assert_eq!(back.branch_id, BranchId(7));
    }

    #[test]
    fn minimal_span_omits_empty_optionals_in_json() {
        let s = ObservabilitySpan::new(
            EventKind::Checkpoint,
            "training",
            TraceId(1),
            BranchId(1),
        );
        let v: serde_json::Value = serde_json::to_value(&s).unwrap();
        // a checkpoint carries no model/tokens — those keys are omitted.
        assert!(v.get("model").is_none());
        assert!(v.get("tokens").is_none());
        assert!(v.get("memory_refs").is_none());
        assert_eq!(v["kind"], "checkpoint");
        assert_eq!(v["profile"], "training");
    }
}
