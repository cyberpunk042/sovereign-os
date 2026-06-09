//! Runtime serving decision.
//!
//! `lib.rs` defines the 8 adapter slots, the 7-step promotion pipeline,
//! and the six [`RuntimeDecision`] *variants* — but not the logic that
//! *chooses* one at serving time. This module is that decision (E0442):
//! given which eval-passed adapters match the task and the runtime
//! constraints, pick how to serve.
//!
//! Rules (in priority order):
//! 1. **high-stakes** → [`RuntimeDecision::AskOracle`] — verification
//!    bypass; skip the adapter path for risky work.
//! 2. **no matching adapter** → [`RuntimeDecision::UseBase`] if the base is
//!    allowed, else [`RuntimeDecision::Refuse`].
//! 3. **exactly one** → [`RuntimeDecision::UseAdapter`].
//! 4. **two or more** → [`RuntimeDecision::StackMerge`] when stacking is
//!    supported, otherwise [`RuntimeDecision::RouteSpecialist`].

use crate::{AdapterSlot, RuntimeDecision};
use serde::{Deserialize, Serialize};

/// Inputs to the serving decision.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ServeRequest {
    /// Eval-passed, promoted adapters that match the task (may be empty).
    pub matching_adapters: Vec<AdapterSlot>,
    /// Whether the runtime supports stack-merging multiple adapters.
    pub stacking_supported: bool,
    /// Whether the task is high-stakes (routes to oracle verification).
    pub high_stakes: bool,
    /// Whether falling back to the base model (no adapter) is permitted.
    pub base_allowed: bool,
}

impl ServeRequest {
    /// A simple request: these matching adapters, base allowed, not
    /// high-stakes, no stacking.
    pub fn with_adapters(matching: Vec<AdapterSlot>) -> Self {
        Self {
            matching_adapters: matching,
            stacking_supported: false,
            high_stakes: false,
            base_allowed: true,
        }
    }
}

/// Choose how to serve the request (E0442 — the 6 runtime decisions).
pub fn decide_serving(req: &ServeRequest) -> RuntimeDecision {
    if req.high_stakes {
        return RuntimeDecision::AskOracle;
    }
    match req.matching_adapters.len() {
        0 => {
            if req.base_allowed {
                RuntimeDecision::UseBase
            } else {
                RuntimeDecision::Refuse
            }
        }
        1 => RuntimeDecision::UseAdapter,
        _ => {
            if req.stacking_supported {
                RuntimeDecision::StackMerge
            } else {
                RuntimeDecision::RouteSpecialist
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_adapter_uses_base() {
        let r = ServeRequest::with_adapters(vec![]);
        assert_eq!(decide_serving(&r), RuntimeDecision::UseBase);
    }

    #[test]
    fn no_adapter_no_base_refuses() {
        let mut r = ServeRequest::with_adapters(vec![]);
        r.base_allowed = false;
        assert_eq!(decide_serving(&r), RuntimeDecision::Refuse);
    }

    #[test]
    fn single_adapter_is_used() {
        let r = ServeRequest::with_adapters(vec![AdapterSlot::CodingStyle]);
        assert_eq!(decide_serving(&r), RuntimeDecision::UseAdapter);
    }

    #[test]
    fn two_adapters_stack_when_supported() {
        let mut r =
            ServeRequest::with_adapters(vec![AdapterSlot::CodingStyle, AdapterSlot::SpecDriven]);
        r.stacking_supported = true;
        assert_eq!(decide_serving(&r), RuntimeDecision::StackMerge);
    }

    #[test]
    fn two_adapters_route_specialist_when_no_stacking() {
        let r = ServeRequest::with_adapters(vec![AdapterSlot::CodingStyle, AdapterSlot::TddReview]);
        assert_eq!(decide_serving(&r), RuntimeDecision::RouteSpecialist);
    }

    #[test]
    fn high_stakes_always_asks_oracle() {
        // Even with a perfectly good single adapter, high-stakes → oracle.
        let mut r = ServeRequest::with_adapters(vec![AdapterSlot::SelfdefSecurity]);
        r.high_stakes = true;
        assert_eq!(decide_serving(&r), RuntimeDecision::AskOracle);
    }

    #[test]
    fn high_stakes_beats_even_stacking() {
        let mut r =
            ServeRequest::with_adapters(vec![AdapterSlot::CodingStyle, AdapterSlot::SpecDriven]);
        r.stacking_supported = true;
        r.high_stakes = true;
        assert_eq!(decide_serving(&r), RuntimeDecision::AskOracle);
    }

    #[test]
    fn serve_request_round_trips() {
        let r = ServeRequest::with_adapters(vec![AdapterSlot::UserPreference]);
        let j = serde_json::to_string(&r).unwrap();
        let back: ServeRequest = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
