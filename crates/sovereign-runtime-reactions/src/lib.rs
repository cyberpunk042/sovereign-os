//! `sovereign-runtime-reactions` — E0472 / M00821: Telemetry As Control.
//!
//! "Most observability tools show you what happened after the fact. Your system
//! should use telemetry in real time … This is the difference between logging
//! and intelligence." Where [`sovereign-pressure-reactions`](E0431) maps OS
//! pressure to scheduler actions, this maps *runtime* telemetry (cost,
//! tool-failures, hallucination, memory quality, GPU pressure, human-gate rate)
//! to the operator-named real-time reactions. Deterministic signal→action; the
//! runtime supplies the signals and does the acting.
//!
//! The six rules, verbatim from E0472:
//! 1. cost spike → downgrade profile or ask user
//! 2. tool failure repeats → stop branch + re-map
//! 3. model hallucination pattern detected → require oracle/test verifier
//! 4. memory retrieval low quality → widen map + rerank + ask user
//! 5. GPU pressure high → reduce branch width
//! 6. human gates too frequent → improve policy defaults + batch approvals

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The six operator-named real-time control triggers (E0472).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ControlTrigger {
    /// Spend rose sharply.
    CostSpike,
    /// A tool kept failing.
    ToolFailureRepeats,
    /// A hallucination pattern was detected.
    HallucinationPattern,
    /// Memory retrieval quality dropped.
    LowMemoryQuality,
    /// GPU pressure is high.
    GpuPressureHigh,
    /// Human approval gates are firing too often.
    HumanGatesTooFrequent,
}

impl ControlTrigger {
    /// The verbatim E0472 actions for this trigger.
    #[must_use]
    pub fn actions(self) -> &'static [&'static str] {
        match self {
            ControlTrigger::CostSpike => &["downgrade profile", "ask user"],
            ControlTrigger::ToolFailureRepeats => &["stop branch", "re-map"],
            ControlTrigger::HallucinationPattern => &["require oracle/test verifier"],
            ControlTrigger::LowMemoryQuality => &["widen map", "rerank", "ask user"],
            ControlTrigger::GpuPressureHigh => &["reduce branch width"],
            ControlTrigger::HumanGatesTooFrequent => {
                &["improve policy defaults", "batch approvals"]
            }
        }
    }
}

/// Live runtime telemetry signals the runtime feeds in each tick.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct RuntimeSignals {
    /// Cost rose sharply this window.
    pub cost_spike: bool,
    /// Consecutive failures of the same tool.
    pub tool_failure_streak: u32,
    /// A hallucination pattern was detected.
    pub hallucination_pattern: bool,
    /// Memory retrieval quality is below the acceptable bar.
    pub memory_retrieval_low_quality: bool,
    /// GPU pressure is high (e.g. from the PSI/DCGM-fed pressure snapshot).
    pub gpu_pressure_high: bool,
    /// Human approval gates are firing more often than the rate bar.
    pub human_gate_rate_high: bool,
}

/// Thresholds for the streak-based signals.
#[derive(Debug, Clone, Copy)]
pub struct ControlThresholds {
    /// A tool-failure streak at or above this fires `ToolFailureRepeats`.
    /// Default 3 ("repeats").
    pub tool_failure_streak_limit: u32,
}

impl Default for ControlThresholds {
    fn default() -> Self {
        Self {
            tool_failure_streak_limit: 3,
        }
    }
}

/// One fired control reaction.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ControlReaction {
    /// Which rule fired.
    pub trigger: ControlTrigger,
    /// Verbatim E0472 actions.
    pub actions: Vec<String>,
}

impl ControlReaction {
    fn of(trigger: ControlTrigger) -> Self {
        Self {
            trigger,
            actions: trigger.actions().iter().map(|s| (*s).to_string()).collect(),
        }
    }
}

/// Derive the real-time control reactions (E0472's six rules) from live runtime
/// signals, in canonical rule order.
#[must_use]
pub fn derive_controls(s: &RuntimeSignals, th: ControlThresholds) -> Vec<ControlReaction> {
    let mut out = Vec::new();
    if s.cost_spike {
        out.push(ControlReaction::of(ControlTrigger::CostSpike));
    }
    if s.tool_failure_streak >= th.tool_failure_streak_limit {
        out.push(ControlReaction::of(ControlTrigger::ToolFailureRepeats));
    }
    if s.hallucination_pattern {
        out.push(ControlReaction::of(ControlTrigger::HallucinationPattern));
    }
    if s.memory_retrieval_low_quality {
        out.push(ControlReaction::of(ControlTrigger::LowMemoryQuality));
    }
    if s.gpu_pressure_high {
        out.push(ControlReaction::of(ControlTrigger::GpuPressureHigh));
    }
    if s.human_gate_rate_high {
        out.push(ControlReaction::of(ControlTrigger::HumanGatesTooFrequent));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trigger_actions_are_verbatim_e0472() {
        assert_eq!(
            ControlTrigger::ToolFailureRepeats.actions(),
            ["stop branch", "re-map"]
        );
        assert_eq!(
            ControlTrigger::LowMemoryQuality.actions(),
            ["widen map", "rerank", "ask user"]
        );
        assert_eq!(
            ControlTrigger::HumanGatesTooFrequent.actions(),
            ["improve policy defaults", "batch approvals"]
        );
    }

    #[test]
    fn no_signals_no_reactions() {
        let r = derive_controls(&RuntimeSignals::default(), ControlThresholds::default());
        assert!(r.is_empty());
    }

    #[test]
    fn tool_failure_streak_respects_threshold() {
        let mut s = RuntimeSignals {
            tool_failure_streak: 2,
            ..Default::default()
        };
        // 2 < default 3 → no reaction.
        assert!(derive_controls(&s, ControlThresholds::default()).is_empty());
        s.tool_failure_streak = 3;
        let r = derive_controls(&s, ControlThresholds::default());
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].trigger, ControlTrigger::ToolFailureRepeats);
    }

    #[test]
    fn all_six_fire_in_canonical_order() {
        let s = RuntimeSignals {
            cost_spike: true,
            tool_failure_streak: 5,
            hallucination_pattern: true,
            memory_retrieval_low_quality: true,
            gpu_pressure_high: true,
            human_gate_rate_high: true,
        };
        let triggers: Vec<_> = derive_controls(&s, ControlThresholds::default())
            .into_iter()
            .map(|r| r.trigger)
            .collect();
        assert_eq!(
            triggers,
            [
                ControlTrigger::CostSpike,
                ControlTrigger::ToolFailureRepeats,
                ControlTrigger::HallucinationPattern,
                ControlTrigger::LowMemoryQuality,
                ControlTrigger::GpuPressureHigh,
                ControlTrigger::HumanGatesTooFrequent,
            ]
        );
    }

    #[test]
    fn trigger_serializes_kebab() {
        let r = ControlReaction::of(ControlTrigger::CostSpike);
        let j = serde_json::to_value(&r).unwrap();
        assert_eq!(j["trigger"], "cost-spike");
        assert_eq!(j["actions"][0], "downgrade profile");
    }
}
