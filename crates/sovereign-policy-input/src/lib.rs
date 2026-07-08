//! `sovereign-policy-input` — E0473 / E0474 / E0475: the Policy Fabric decision
//! contract.
//!
//! "Sovereign choice needs a policy engine." Classic authorization asks "Can
//! subject do action on object?"; agents require "Can subject do action on
//! object **for this intent under this profile**?" — "That is sovereignty."
//! This crate fixes the decision *contract* (the questions, the input fields,
//! the sensitivity vocabulary) that a policy engine (OPA/Cedar/OpenFGA) decides
//! over; it does not embed the policy itself.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// The 7 policy decisions the fabric answers (E0473 / M00823).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PolicyQuestion {
    /// Can this model see this context?
    ModelSeesContext,
    /// Can this agent use this tool?
    AgentUsesTool,
    /// Can this workflow call cloud?
    WorkflowCallsCloud,
    /// Can this sandbox access network?
    SandboxAccessesNetwork,
    /// Can this memory be written?
    MemoryWrite,
    /// Can this action mutate files?
    FileMutation,
    /// Can this result be committed?
    ResultCommit,
}

impl PolicyQuestion {
    /// All 7 questions.
    pub const ALL: [PolicyQuestion; 7] = [
        PolicyQuestion::ModelSeesContext,
        PolicyQuestion::AgentUsesTool,
        PolicyQuestion::WorkflowCallsCloud,
        PolicyQuestion::SandboxAccessesNetwork,
        PolicyQuestion::MemoryWrite,
        PolicyQuestion::FileMutation,
        PolicyQuestion::ResultCommit,
    ];
}

/// The 9 memory sensitivity classes (E0475). "Memory is not neutral."
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SensitivityClass {
    /// private
    Private,
    /// project-local
    ProjectLocal,
    /// cloud-forbidden
    CloudForbidden,
    /// time-limited
    TimeLimited,
    /// user-only
    UserOnly,
    /// quarantined
    Quarantined,
    /// verified
    Verified,
    /// derived
    Derived,
    /// raw
    Raw,
}

impl SensitivityClass {
    /// All 9 sensitivity classes.
    pub const ALL: [SensitivityClass; 9] = [
        SensitivityClass::Private,
        SensitivityClass::ProjectLocal,
        SensitivityClass::CloudForbidden,
        SensitivityClass::TimeLimited,
        SensitivityClass::UserOnly,
        SensitivityClass::Quarantined,
        SensitivityClass::Verified,
        SensitivityClass::Derived,
        SensitivityClass::Raw,
    ];
}

/// Risk level for the action.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RiskLevel {
    /// Low risk.
    Low,
    /// Medium risk.
    Medium,
    /// High risk.
    High,
    /// Critical risk.
    Critical,
}

/// The side-effect class of an action (its blast radius if it goes wrong).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SideEffectClass {
    /// No side effects (pure read/compute).
    None,
    /// Reads only.
    ReadOnly,
    /// Writes files.
    FileWrite,
    /// Makes a network call.
    NetworkCall,
    /// Irreversible / destructive.
    Destructive,
}

/// User approval state for the action (E0474 field 10).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ApprovalState {
    /// No approval requested (default).
    NotRequested,
    /// Approval requested, awaiting the human gate.
    Pending,
    /// Granted by the user.
    Granted,
    /// Denied by the user.
    Denied,
}

/// The 10-field intent-based policy input (E0474 / M00824).
///
/// "Policy input MUST include 10 fields." Unlike classic authorization, the
/// input carries `intent`, `profile`, and `user_approval` — the same
/// (subject, action, resource) can be denied for one intent and allowed for
/// another.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyInput {
    /// 1. subject (who/what acts).
    pub subject: String,
    /// 2. action.
    pub action: String,
    /// 3. resource (the object).
    pub resource: String,
    /// 4. intent (why — the agent-specific dimension).
    pub intent: String,
    /// 5. profile in effect.
    pub profile: String,
    /// 6. risk level.
    pub risk: RiskLevel,
    /// 7. model / provider doing the work.
    pub model_provider: String,
    /// 8. context sensitivity of the resource.
    pub context_sensitivity: SensitivityClass,
    /// 9. side-effect class of the action.
    pub side_effect_class: SideEffectClass,
    /// 10. user approval state.
    pub user_approval: ApprovalState,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ssh_config_read(intent: &str, approval: ApprovalState) -> PolicyInput {
        PolicyInput {
            subject: "agent:scout".into(),
            action: "read".into(),
            resource: "~/.ssh/config".into(),
            intent: intent.into(),
            profile: "inference-ready".into(),
            risk: RiskLevel::High,
            model_provider: "local:oracle".into(),
            context_sensitivity: SensitivityClass::Private,
            side_effect_class: SideEffectClass::ReadOnly,
            user_approval: approval,
        }
    }

    #[test]
    fn seven_questions_and_nine_sensitivity_classes() {
        use std::collections::HashSet;
        assert_eq!(PolicyQuestion::ALL.len(), 7);
        assert_eq!(PolicyQuestion::ALL.iter().collect::<HashSet<_>>().len(), 7);
        assert_eq!(SensitivityClass::ALL.len(), 9);
        assert_eq!(
            SensitivityClass::ALL.iter().collect::<HashSet<_>>().len(),
            9
        );
    }

    #[test]
    fn input_carries_intent_so_same_triple_differs() {
        // The E0474 example: reading ~/.ssh/config is denied for generic
        // summarization but maybe allowed for debugging SSH — the (subject,
        // action, resource) triple is identical; only `intent` differs.
        let a = ssh_config_read("summarize my files", ApprovalState::NotRequested);
        let b = ssh_config_read("debug ssh connection failure", ApprovalState::Granted);
        assert_eq!(
            (&a.subject, &a.action, &a.resource),
            (&b.subject, &b.action, &b.resource)
        );
        assert_ne!(a.intent, b.intent);
        assert_ne!(a.user_approval, b.user_approval);
    }

    #[test]
    fn input_roundtrips_with_kebab_enums() {
        let p = ssh_config_read("debug", ApprovalState::Pending);
        let v: serde_json::Value = serde_json::to_value(&p).unwrap();
        assert_eq!(v["risk"], "high");
        assert_eq!(v["context_sensitivity"], "private");
        assert_eq!(v["side_effect_class"], "read-only");
        assert_eq!(v["user_approval"], "pending");
        let back: PolicyInput = serde_json::from_value(v).unwrap();
        assert_eq!(p, back);
    }

    #[test]
    fn question_serializes_kebab() {
        assert_eq!(
            serde_json::to_string(&PolicyQuestion::WorkflowCallsCloud).unwrap(),
            "\"workflow-calls-cloud\""
        );
        assert_eq!(
            serde_json::to_string(&SensitivityClass::CloudForbidden).unwrap(),
            "\"cloud-forbidden\""
        );
    }
}
