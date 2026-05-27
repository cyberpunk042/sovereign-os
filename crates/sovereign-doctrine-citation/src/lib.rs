//! `sovereign-doctrine-citation` — runtime doctrine citation envelope.
//!
//! Each cockpit-emitted action carries a citation set of `DoctrineTag`s
//! from `sovereign-doctrinal-preservation`. This crate computes default
//! citations for canonical action shapes and validates citation
//! envelopes against the registry.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_doctrinal_preservation::{DoctrineRegistry, DoctrineTag};
use sovereign_execution_mode_registry::ExecutionMode;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Action shape for citation lookup.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ActionShape {
    /// Model dispatch.
    ModelDispatch,
    /// Mode transition.
    ModeTransition,
    /// Replay session opened/closed.
    ReplaySession,
    /// LoRA adapter swap.
    LoraSwap,
    /// Memory state read/write.
    MemoryAccess,
    /// Tool invocation.
    ToolInvocation,
    /// Provider switch (local↔cloud).
    ProviderSwitch,
    /// Cognitive compiler step.
    CompilerStep,
}

/// Citation envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CitationSet {
    /// Schema version.
    pub schema_version: String,
    /// trace_id linking to originating dispatch.
    pub trace_id: String,
    /// Action shape that produced this citation.
    pub shape: ActionShape,
    /// Mode at action time.
    pub mode: ExecutionMode,
    /// Cited tags (non-empty).
    pub tags: Vec<DoctrineTag>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CitationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty citation.
    #[error("empty citation for trace {0}")]
    Empty(String),
    /// Tag not in registry.
    #[error("cited unknown tag {0:?}")]
    Unknown(DoctrineTag),
    /// Empty trace_id.
    #[error("trace_id missing")]
    MissingTraceId,
}

/// Compute the canonical citation set for an action shape + mode.
pub fn cite(trace_id: &str, shape: ActionShape, mode: ExecutionMode) -> CitationSet {
    let mut tags = vec![
        DoctrineTag::AgentRequirement,
        DoctrineTag::ThatIsSovereignty,
    ];

    match shape {
        ActionShape::ModelDispatch => {
            tags.push(DoctrineTag::NotEveryPrompt);
            tags.push(DoctrineTag::PrmProposes);
            tags.push(DoctrineTag::ProviderInversion);
        }
        ActionShape::ModeTransition => {
            tags.push(DoctrineTag::WorkflowVersioned);
        }
        ActionShape::ReplaySession => {
            tags.push(DoctrineTag::ThoughtsDeserveMoreLife);
        }
        ActionShape::LoraSwap => {
            tags.push(DoctrineTag::RuntimeFirst);
            tags.push(DoctrineTag::KeyLine);
        }
        ActionShape::MemoryAccess => {
            tags.push(DoctrineTag::MemoryAdaptiveState);
        }
        ActionShape::ToolInvocation => {
            tags.push(DoctrineTag::BuildMapFirst);
        }
        ActionShape::ProviderSwitch => {
            tags.push(DoctrineTag::ProviderInversion);
            tags.push(DoctrineTag::SrpToHardware);
        }
        ActionShape::CompilerStep => {
            tags.push(DoctrineTag::CompilerPipeline);
            tags.push(DoctrineTag::TrinityGenesis);
        }
    }

    // Replay mode adds "thoughts-deserve-more-life".
    if mode == ExecutionMode::Replay {
        tags.push(DoctrineTag::ThoughtsDeserveMoreLife);
    }
    if mode == ExecutionMode::Sandbox {
        tags.push(DoctrineTag::NonSurjective);
    }
    if mode == ExecutionMode::Execute {
        tags.push(DoctrineTag::PressureAsSensation);
    }

    // Dedup while preserving order.
    let mut seen = std::collections::HashSet::new();
    tags.retain(|t| seen.insert(*t));

    CitationSet {
        schema_version: SCHEMA_VERSION.into(),
        trace_id: trace_id.into(),
        shape,
        mode,
        tags,
    }
}

impl CitationSet {
    /// Validate against the doctrine registry.
    pub fn validate(&self, registry: &DoctrineRegistry) -> Result<(), CitationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CitationError::SchemaMismatch);
        }
        if self.trace_id.is_empty() {
            return Err(CitationError::MissingTraceId);
        }
        if self.tags.is_empty() {
            return Err(CitationError::Empty(self.trace_id.clone()));
        }
        for t in &self.tags {
            if !registry.records.iter().any(|r| r.tag == *t) {
                return Err(CitationError::Unknown(*t));
            }
        }
        Ok(())
    }

    /// True if a specific tag is cited.
    pub fn cites(&self, tag: DoctrineTag) -> bool {
        self.tags.contains(&tag)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reg() -> DoctrineRegistry {
        DoctrineRegistry::canonical()
    }

    #[test]
    fn model_dispatch_cites_core_tags() {
        let c = cite("tr-1", ActionShape::ModelDispatch, ExecutionMode::Execute);
        assert!(c.cites(DoctrineTag::AgentRequirement));
        assert!(c.cites(DoctrineTag::ThatIsSovereignty));
        assert!(c.cites(DoctrineTag::NotEveryPrompt));
        assert!(c.cites(DoctrineTag::PrmProposes));
        assert!(c.cites(DoctrineTag::ProviderInversion));
        c.validate(&reg()).unwrap();
    }

    #[test]
    fn replay_session_cites_thoughts_doctrine() {
        let c = cite("tr-1", ActionShape::ReplaySession, ExecutionMode::Replay);
        assert!(c.cites(DoctrineTag::ThoughtsDeserveMoreLife));
    }

    #[test]
    fn lora_swap_cites_runtime_first_and_keyline() {
        let c = cite("tr-1", ActionShape::LoraSwap, ExecutionMode::Execute);
        assert!(c.cites(DoctrineTag::RuntimeFirst));
        assert!(c.cites(DoctrineTag::KeyLine));
    }

    #[test]
    fn memory_access_cites_memory_doctrine() {
        let c = cite("tr-1", ActionShape::MemoryAccess, ExecutionMode::Execute);
        assert!(c.cites(DoctrineTag::MemoryAdaptiveState));
    }

    #[test]
    fn execute_mode_adds_pressure_doctrine() {
        let c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Execute);
        assert!(c.cites(DoctrineTag::PressureAsSensation));
    }

    #[test]
    fn sandbox_mode_adds_non_surjective() {
        let c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Sandbox);
        assert!(c.cites(DoctrineTag::NonSurjective));
    }

    #[test]
    fn replay_mode_adds_thoughts() {
        let c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Replay);
        assert!(c.cites(DoctrineTag::ThoughtsDeserveMoreLife));
    }

    #[test]
    fn dedup_preserves_invariant() {
        let c = cite("tr-1", ActionShape::ReplaySession, ExecutionMode::Replay);
        // ThoughtsDeserveMoreLife is added twice (action shape + mode); dedup → 1
        let n = c
            .tags
            .iter()
            .filter(|t| **t == DoctrineTag::ThoughtsDeserveMoreLife)
            .count();
        assert_eq!(n, 1);
    }

    #[test]
    fn provider_switch_cites_provider_inversion() {
        let c = cite("tr-1", ActionShape::ProviderSwitch, ExecutionMode::Execute);
        assert!(c.cites(DoctrineTag::ProviderInversion));
        assert!(c.cites(DoctrineTag::SrpToHardware));
    }

    #[test]
    fn compiler_step_cites_pipeline_and_trinity() {
        let c = cite("tr-1", ActionShape::CompilerStep, ExecutionMode::Plan);
        assert!(c.cites(DoctrineTag::CompilerPipeline));
        assert!(c.cites(DoctrineTag::TrinityGenesis));
    }

    #[test]
    fn empty_citation_rejected() {
        let mut c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Plan);
        c.tags.clear();
        assert!(matches!(
            c.validate(&reg()).unwrap_err(),
            CitationError::Empty(_)
        ));
    }

    #[test]
    fn missing_trace_id_rejected() {
        let mut c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Plan);
        c.trace_id = String::new();
        assert!(matches!(
            c.validate(&reg()).unwrap_err(),
            CitationError::MissingTraceId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = cite("tr-1", ActionShape::ToolInvocation, ExecutionMode::Plan);
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate(&reg()).unwrap_err(),
            CitationError::SchemaMismatch
        ));
    }

    #[test]
    fn shape_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ActionShape::ModelDispatch).unwrap(),
            "\"model-dispatch\""
        );
        assert_eq!(
            serde_json::to_string(&ActionShape::ReplaySession).unwrap(),
            "\"replay-session\""
        );
        assert_eq!(
            serde_json::to_string(&ActionShape::ProviderSwitch).unwrap(),
            "\"provider-switch\""
        );
    }

    #[test]
    fn citation_serde_roundtrip() {
        let c = cite("tr-1", ActionShape::ModelDispatch, ExecutionMode::Execute);
        let j = serde_json::to_string(&c).unwrap();
        let back: CitationSet = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
