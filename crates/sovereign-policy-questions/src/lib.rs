//! `sovereign-policy-questions` — M049 7-policy-question runtime surface.
//!
//! Per E0473 + F04155-F04156 + dump 14988-15000, the Policy Fabric
//! answers exactly **7 canonical questions** at every action boundary:
//!
//! 1. Can this model see this context?
//! 2. Can this agent use this tool?
//! 3. Can this workflow call cloud?
//! 4. Can this sandbox access network?
//! 5. Can this memory be written?
//! 6. Can this action mutate files?
//! 7. Can this result be committed?
//!
//! Doctrines preserved verbatim:
//!
//! > "Can subject do action on object for this intent under this profile?" (F04158 dump 15014)
//!
//! > "That is sovereignty" (E0474 dump 15040)
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Doctrine surface verbatim per F04158 dump 15014.
pub const DOCTRINE_AGENT_REQUIREMENT: &str =
    "Can subject do action on object for this intent under this profile?";

/// Doctrine surface verbatim per E0474 dump 15040.
pub const DOCTRINE_THAT_IS_SOVEREIGNTY: &str = "That is sovereignty";

/// The 7 canonical policy questions per F04155-F04156 dump 14988-15000.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PolicyQuestion {
    /// Q1 (dump 14988) — Can this model see this context?
    ModelSeesContext,
    /// Q2 (dump 14990) — Can this agent use this tool?
    AgentUsesTool,
    /// Q3 (dump 14992) — Can this workflow call cloud?
    WorkflowCallsCloud,
    /// Q4 (dump 14994) — Can this sandbox access network?
    SandboxAccessesNetwork,
    /// Q5 (dump 14996) — Can this memory be written?
    MemoryWriteAllowed,
    /// Q6 (dump 14998) — Can this action mutate files?
    ActionMutatesFiles,
    /// Q7 (dump 15000) — Can this result be committed?
    ResultCommitted,
}

impl PolicyQuestion {
    /// Canonical 1..7 question number.
    pub fn position(self) -> u8 {
        match self {
            PolicyQuestion::ModelSeesContext => 1,
            PolicyQuestion::AgentUsesTool => 2,
            PolicyQuestion::WorkflowCallsCloud => 3,
            PolicyQuestion::SandboxAccessesNetwork => 4,
            PolicyQuestion::MemoryWriteAllowed => 5,
            PolicyQuestion::ActionMutatesFiles => 6,
            PolicyQuestion::ResultCommitted => 7,
        }
    }

    /// Verbatim human-readable question text per dump 14988-15000.
    pub fn text(self) -> &'static str {
        match self {
            PolicyQuestion::ModelSeesContext => "Can this model see this context?",
            PolicyQuestion::AgentUsesTool => "Can this agent use this tool?",
            PolicyQuestion::WorkflowCallsCloud => "Can this workflow call cloud?",
            PolicyQuestion::SandboxAccessesNetwork => "Can this sandbox access network?",
            PolicyQuestion::MemoryWriteAllowed => "Can this memory be written?",
            PolicyQuestion::ActionMutatesFiles => "Can this action mutate files?",
            PolicyQuestion::ResultCommitted => "Can this result be committed?",
        }
    }

    /// Iterate all 7 questions in canonical order.
    pub fn all() -> [PolicyQuestion; 7] {
        [
            PolicyQuestion::ModelSeesContext, PolicyQuestion::AgentUsesTool,
            PolicyQuestion::WorkflowCallsCloud, PolicyQuestion::SandboxAccessesNetwork,
            PolicyQuestion::MemoryWriteAllowed, PolicyQuestion::ActionMutatesFiles,
            PolicyQuestion::ResultCommitted,
        ]
    }
}

/// Yes/no/ask outcome for each question.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AnswerOutcome {
    /// Yes — proceed.
    Yes,
    /// No — refuse.
    No,
    /// Ask operator (queued for D-06).
    Ask,
}

/// One question + answer + reason.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct QuestionAnswer {
    /// Question.
    pub question: PolicyQuestion,
    /// Answer outcome.
    pub answer: AnswerOutcome,
    /// Reason text (operator-readable).
    pub reason: String,
    /// M049 trace_id reference.
    pub trace_id: String,
}

/// Full 7-answer envelope for one action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PolicyAnswerSet {
    /// Wire-stable schema version.
    pub schema_version: String,
    /// All 7 answers in canonical order. MUST be exactly 7.
    pub answers: Vec<QuestionAnswer>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PolicyQuestionError {
    /// Schema drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected.
        expected: String,
        /// Observed.
        actual: String,
    },
    /// Answer count != 7.
    #[error("answer count {0} != 7 canonical questions")]
    AnswerCountInvalid(usize),
    /// One of the 7 questions missing.
    #[error("required question missing: {0:?}")]
    QuestionMissing(PolicyQuestion),
    /// Duplicate question.
    #[error("duplicate question: {0:?}")]
    DuplicateQuestion(PolicyQuestion),
    /// Doctrine surface tampered.
    #[error("doctrine tampered: expected verbatim {expected:?}")]
    DoctrineTampered {
        /// Expected.
        expected: String,
    },
}

impl PolicyAnswerSet {
    /// Validate canonical invariants.
    pub fn validate(&self) -> Result<(), PolicyQuestionError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PolicyQuestionError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.answers.len() != 7 {
            return Err(PolicyQuestionError::AnswerCountInvalid(self.answers.len()));
        }
        for q in PolicyQuestion::all() {
            if !self.answers.iter().any(|a| a.question == q) {
                return Err(PolicyQuestionError::QuestionMissing(q));
            }
        }
        use std::collections::HashSet;
        let mut seen: HashSet<PolicyQuestion> = HashSet::new();
        for a in &self.answers {
            if !seen.insert(a.question) {
                return Err(PolicyQuestionError::DuplicateQuestion(a.question));
            }
        }
        Ok(())
    }

    /// True iff every answer is Yes.
    pub fn all_yes(&self) -> bool {
        self.answers.iter().all(|a| a.answer == AnswerOutcome::Yes)
    }

    /// True iff any answer is No.
    pub fn any_no(&self) -> bool {
        self.answers.iter().any(|a| a.answer == AnswerOutcome::No)
    }

    /// True iff any answer is Ask (queues operator approval).
    pub fn any_ask(&self) -> bool {
        self.answers.iter().any(|a| a.answer == AnswerOutcome::Ask)
    }

    /// List the questions that returned No (or all if any_no=false returns empty).
    pub fn refused_questions(&self) -> Vec<PolicyQuestion> {
        self.answers.iter()
            .filter(|a| a.answer == AnswerOutcome::No)
            .map(|a| a.question)
            .collect()
    }
}

/// Validate the two doctrine constants.
pub fn assert_doctrines_intact(agent_req: &str, sovereignty: &str) -> Result<(), PolicyQuestionError> {
    if agent_req != DOCTRINE_AGENT_REQUIREMENT {
        return Err(PolicyQuestionError::DoctrineTampered { expected: DOCTRINE_AGENT_REQUIREMENT.into() });
    }
    if sovereignty != DOCTRINE_THAT_IS_SOVEREIGNTY {
        return Err(PolicyQuestionError::DoctrineTampered { expected: DOCTRINE_THAT_IS_SOVEREIGNTY.into() });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn answer(q: PolicyQuestion, a: AnswerOutcome) -> QuestionAnswer {
        QuestionAnswer {
            question: q,
            answer: a,
            reason: format!("test reason for {q:?}"),
            trace_id: format!("trace-{}", q.position()),
        }
    }
    fn all_yes_set() -> PolicyAnswerSet {
        PolicyAnswerSet {
            schema_version: SCHEMA_VERSION.into(),
            answers: PolicyQuestion::all().into_iter().map(|q| answer(q, AnswerOutcome::Yes)).collect(),
        }
    }

    // --- 7 questions ---

    #[test]
    fn seven_questions_positioned_1_to_7() {
        for (q, p) in [
            (PolicyQuestion::ModelSeesContext, 1), (PolicyQuestion::AgentUsesTool, 2),
            (PolicyQuestion::WorkflowCallsCloud, 3), (PolicyQuestion::SandboxAccessesNetwork, 4),
            (PolicyQuestion::MemoryWriteAllowed, 5), (PolicyQuestion::ActionMutatesFiles, 6),
            (PolicyQuestion::ResultCommitted, 7),
        ] {
            assert_eq!(q.position(), p);
        }
    }

    #[test]
    fn seven_questions_text_verbatim() {
        assert_eq!(PolicyQuestion::ModelSeesContext.text(), "Can this model see this context?");
        assert_eq!(PolicyQuestion::AgentUsesTool.text(), "Can this agent use this tool?");
        assert_eq!(PolicyQuestion::WorkflowCallsCloud.text(), "Can this workflow call cloud?");
        assert_eq!(PolicyQuestion::SandboxAccessesNetwork.text(), "Can this sandbox access network?");
        assert_eq!(PolicyQuestion::MemoryWriteAllowed.text(), "Can this memory be written?");
        assert_eq!(PolicyQuestion::ActionMutatesFiles.text(), "Can this action mutate files?");
        assert_eq!(PolicyQuestion::ResultCommitted.text(), "Can this result be committed?");
    }

    #[test]
    fn all_returns_7_in_canonical_order() {
        let a = PolicyQuestion::all();
        assert_eq!(a.len(), 7);
        for (i, q) in a.iter().enumerate() {
            assert_eq!(q.position(), (i + 1) as u8);
        }
    }

    // --- AnswerSet validation ---

    #[test]
    fn all_yes_set_validates() {
        all_yes_set().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = all_yes_set();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), PolicyQuestionError::SchemaMismatch { .. }));
    }

    #[test]
    fn answer_count_invalid_rejected() {
        let mut s = all_yes_set();
        s.answers.pop();
        assert!(matches!(s.validate().unwrap_err(), PolicyQuestionError::AnswerCountInvalid(6)));
    }

    #[test]
    fn missing_question_caught_when_replaced() {
        let mut s = all_yes_set();
        s.answers[0] = answer(PolicyQuestion::AgentUsesTool, AnswerOutcome::Yes);  // replace Q1 with Q2 dup
        let err = s.validate().unwrap_err();
        assert!(matches!(err,
            PolicyQuestionError::QuestionMissing(PolicyQuestion::ModelSeesContext)
            | PolicyQuestionError::DuplicateQuestion(PolicyQuestion::AgentUsesTool)
        ));
    }

    // --- Outcome aggregation ---

    #[test]
    fn all_yes_returns_true_when_all_yes() {
        let s = all_yes_set();
        assert!(s.all_yes());
        assert!(!s.any_no());
        assert!(!s.any_ask());
    }

    #[test]
    fn any_no_detects_one_no() {
        let mut s = all_yes_set();
        s.answers[2].answer = AnswerOutcome::No;
        assert!(!s.all_yes());
        assert!(s.any_no());
        let refused = s.refused_questions();
        assert_eq!(refused, vec![PolicyQuestion::WorkflowCallsCloud]);
    }

    #[test]
    fn any_ask_detects_one_ask() {
        let mut s = all_yes_set();
        s.answers[5].answer = AnswerOutcome::Ask;
        assert!(!s.all_yes());
        assert!(s.any_ask());
        assert!(!s.any_no());
    }

    // --- Doctrines ---

    #[test]
    fn doctrines_verbatim() {
        assert_eq!(DOCTRINE_AGENT_REQUIREMENT, "Can subject do action on object for this intent under this profile?");
        assert_eq!(DOCTRINE_THAT_IS_SOVEREIGNTY, "That is sovereignty");
        assert_doctrines_intact(DOCTRINE_AGENT_REQUIREMENT, DOCTRINE_THAT_IS_SOVEREIGNTY).unwrap();
    }

    #[test]
    fn doctrine_tamper_caught() {
        let err = assert_doctrines_intact("WRONG", DOCTRINE_THAT_IS_SOVEREIGNTY).unwrap_err();
        assert!(matches!(err, PolicyQuestionError::DoctrineTampered { .. }));
        let err2 = assert_doctrines_intact(DOCTRINE_AGENT_REQUIREMENT, "WRONG").unwrap_err();
        assert!(matches!(err2, PolicyQuestionError::DoctrineTampered { .. }));
    }

    // --- Serde ---

    #[test]
    fn policy_question_serde_kebab() {
        assert_eq!(serde_json::to_string(&PolicyQuestion::WorkflowCallsCloud).unwrap(), "\"workflow-calls-cloud\"");
        assert_eq!(serde_json::to_string(&PolicyQuestion::SandboxAccessesNetwork).unwrap(), "\"sandbox-accesses-network\"");
        assert_eq!(serde_json::to_string(&PolicyQuestion::ResultCommitted).unwrap(), "\"result-committed\"");
    }

    #[test]
    fn answer_outcome_serde_kebab() {
        assert_eq!(serde_json::to_string(&AnswerOutcome::Ask).unwrap(), "\"ask\"");
        assert_eq!(serde_json::to_string(&AnswerOutcome::Yes).unwrap(), "\"yes\"");
        assert_eq!(serde_json::to_string(&AnswerOutcome::No).unwrap(), "\"no\"");
    }

    #[test]
    fn answer_set_serde_roundtrip() {
        let s = all_yes_set();
        let j = serde_json::to_string(&s).unwrap();
        let back: PolicyAnswerSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
