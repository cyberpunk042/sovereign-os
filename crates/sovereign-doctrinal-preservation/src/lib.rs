//! `sovereign-doctrinal-preservation` — composite verbatim doctrine registry.
//!
//! Counterpart to selfdef-doctrinal-preservation. Aggregates every
//! doctrine string from the sovereign-os runtime/cockpit crates into
//! one tamper-checkable snapshot.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_cognitive_compiler::DOCTRINE_PIPELINE;
use sovereign_environment_maps::DOCTRINE_BUILD_MAP_FIRST;
use sovereign_gateway::DOCTRINE_PROVIDER_INVERSION;
use sovereign_inheritance_contracts::DOCTRINE_WORKFLOW_VERSIONED;
use sovereign_intervention_class_mirror::DOCTRINE_NON_SURJECTIVE;
use sovereign_lora_foundry::DOCTRINE_RUNTIME_FIRST;
use sovereign_memory_os::DOCTRINE_MEMORY_ADAPTIVE_STATE;
use sovereign_module_catalog::KEY_LINE;
use sovereign_policy_questions::{DOCTRINE_AGENT_REQUIREMENT, DOCTRINE_THAT_IS_SOVEREIGNTY};
use sovereign_pressure_sensors::DOCTRINE_PRESSURE_AS_SENSATION;
use sovereign_router_7axis::DOCTRINE_NOT_EVERY_PROMPT;
use sovereign_srp_scheduler::DOCTRINE_SRP_TO_HARDWARE;
use sovereign_trinity::TRINITY_GENESIS;
use sovereign_value_plane::{DOCTRINE_PRM_PROPOSES, DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Tagged enum of every sovereign-os doctrine string.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DoctrineTag {
    /// M042 7-axis NadirClaw.
    NotEveryPrompt,
    /// M042 MAP doctrine.
    BuildMapFirst,
    /// M042 Symphony.
    WorkflowVersioned,
    /// M048 KEY LINE.
    KeyLine,
    /// M046 LoRA.
    RuntimeFirst,
    /// M045 Pressure-As-Sensation.
    PressureAsSensation,
    /// M027 PRM doctrine.
    PrmProposes,
    /// M027 closing rule.
    ThoughtsDeserveMoreLife,
    /// M028 Memory OS adaptive state.
    MemoryAdaptiveState,
    /// M066 Trinity genesis.
    TrinityGenesis,
    /// M075 SRP-to-hardware.
    SrpToHardware,
    /// M049 agent-requirement.
    AgentRequirement,
    /// M049 closing.
    ThatIsSovereignty,
    /// M048 Module 4 gateway.
    ProviderInversion,
    /// M025 cognitive-compiler pipeline.
    CompilerPipeline,
    /// M079 intervention class.
    NonSurjective,
}

impl DoctrineTag {
    /// Verbatim text.
    pub fn verbatim(self) -> &'static str {
        match self {
            DoctrineTag::NotEveryPrompt => DOCTRINE_NOT_EVERY_PROMPT,
            DoctrineTag::BuildMapFirst => DOCTRINE_BUILD_MAP_FIRST,
            DoctrineTag::WorkflowVersioned => DOCTRINE_WORKFLOW_VERSIONED,
            DoctrineTag::KeyLine => KEY_LINE,
            DoctrineTag::RuntimeFirst => DOCTRINE_RUNTIME_FIRST,
            DoctrineTag::PressureAsSensation => DOCTRINE_PRESSURE_AS_SENSATION,
            DoctrineTag::PrmProposes => DOCTRINE_PRM_PROPOSES,
            DoctrineTag::ThoughtsDeserveMoreLife => DOCTRINE_THOUGHTS_DESERVE_MORE_LIFE,
            DoctrineTag::MemoryAdaptiveState => DOCTRINE_MEMORY_ADAPTIVE_STATE,
            DoctrineTag::TrinityGenesis => TRINITY_GENESIS,
            DoctrineTag::SrpToHardware => DOCTRINE_SRP_TO_HARDWARE,
            DoctrineTag::AgentRequirement => DOCTRINE_AGENT_REQUIREMENT,
            DoctrineTag::ThatIsSovereignty => DOCTRINE_THAT_IS_SOVEREIGNTY,
            DoctrineTag::ProviderInversion => DOCTRINE_PROVIDER_INVERSION,
            DoctrineTag::CompilerPipeline => DOCTRINE_PIPELINE,
            DoctrineTag::NonSurjective => DOCTRINE_NON_SURJECTIVE,
        }
    }
    /// Provenance.
    pub fn provenance(self) -> &'static str {
        match self {
            DoctrineTag::NotEveryPrompt => "M042 NadirClaw dump 12219",
            DoctrineTag::BuildMapFirst => "M042 R07012 dump 12175",
            DoctrineTag::WorkflowVersioned => "M042 F03509 dump 12194",
            DoctrineTag::KeyLine => "M048 E0467 dump 14810",
            DoctrineTag::RuntimeFirst => "M046 E0438",
            DoctrineTag::PressureAsSensation => "M045 F03773 dump 13636-13660",
            DoctrineTag::PrmProposes => "M027 E0252 dump 7849",
            DoctrineTag::ThoughtsDeserveMoreLife => "M027 E0257 dump 8120",
            DoctrineTag::MemoryAdaptiveState => "M028 E0267 dump 8423-8474",
            DoctrineTag::TrinityGenesis => "M066 dump 953-978",
            DoctrineTag::SrpToHardware => "M075 dump 813",
            DoctrineTag::AgentRequirement => "M049 F04158 dump 15014",
            DoctrineTag::ThatIsSovereignty => "M049 E0474 dump 15040",
            DoctrineTag::ProviderInversion => "M048 E0462 dump 14592",
            DoctrineTag::CompilerPipeline => "M025 E0230 dump 7026-7030",
            DoctrineTag::NonSurjective => "M079 arXiv 2604.09839 §4",
        }
    }
    /// All 16 tags.
    pub fn all() -> [DoctrineTag; 16] {
        [
            DoctrineTag::NotEveryPrompt, DoctrineTag::BuildMapFirst,
            DoctrineTag::WorkflowVersioned, DoctrineTag::KeyLine,
            DoctrineTag::RuntimeFirst, DoctrineTag::PressureAsSensation,
            DoctrineTag::PrmProposes, DoctrineTag::ThoughtsDeserveMoreLife,
            DoctrineTag::MemoryAdaptiveState, DoctrineTag::TrinityGenesis,
            DoctrineTag::SrpToHardware, DoctrineTag::AgentRequirement,
            DoctrineTag::ThatIsSovereignty, DoctrineTag::ProviderInversion,
            DoctrineTag::CompilerPipeline, DoctrineTag::NonSurjective,
        ]
    }
}

/// One record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DoctrineRecord {
    /// Tag.
    pub tag: DoctrineTag,
    /// Verbatim text.
    pub text: String,
    /// Provenance.
    pub provenance: String,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DoctrineRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Captured at.
    pub captured_at: String,
    /// 16 records.
    pub records: Vec<DoctrineRecord>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum DoctrineError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Count != 16.
    #[error("record count {0} != 16")]
    CountInvalid(usize),
    /// Tag missing.
    #[error("required tag missing: {0:?}")]
    TagMissing(DoctrineTag),
    /// Text tampered.
    #[error("verbatim text tampered for {tag:?}")]
    TextTampered {
        /// Tag.
        tag: DoctrineTag,
    },
}

impl DoctrineRegistry {
    /// Build canonical registry.
    pub fn canonical() -> Self {
        let records = DoctrineTag::all().into_iter().map(|t| DoctrineRecord {
            tag: t,
            text: t.verbatim().into(),
            provenance: t.provenance().into(),
        }).collect();
        Self {
            schema_version: SCHEMA_VERSION.into(),
            captured_at: "2026-05-19T00:00:00Z".into(),
            records,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), DoctrineError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(DoctrineError::SchemaMismatch);
        }
        if self.records.len() != 16 {
            return Err(DoctrineError::CountInvalid(self.records.len()));
        }
        for tag in DoctrineTag::all() {
            let rec = self.records.iter().find(|r| r.tag == tag)
                .ok_or(DoctrineError::TagMissing(tag))?;
            if rec.text != tag.verbatim() {
                return Err(DoctrineError::TextTampered { tag });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sixteen_doctrines() {
        assert_eq!(DoctrineTag::all().len(), 16);
    }

    #[test]
    fn canonical_validates() {
        DoctrineRegistry::canonical().validate().unwrap();
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = DoctrineRegistry::canonical();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), DoctrineError::SchemaMismatch));
    }

    #[test]
    fn count_invalid_rejected() {
        let mut r = DoctrineRegistry::canonical();
        r.records.pop();
        assert!(matches!(r.validate().unwrap_err(), DoctrineError::CountInvalid(15)));
    }

    #[test]
    fn text_tamper_caught() {
        let mut r = DoctrineRegistry::canonical();
        r.records[0].text = "tampered".into();
        assert!(matches!(r.validate().unwrap_err(), DoctrineError::TextTampered { .. }));
    }

    #[test]
    fn all_provenance_strings_non_empty() {
        for t in DoctrineTag::all() {
            assert!(!t.provenance().is_empty());
        }
    }

    #[test]
    fn all_verbatim_strings_non_empty() {
        for t in DoctrineTag::all() {
            assert!(!t.verbatim().is_empty());
        }
    }

    #[test]
    fn registry_serde_roundtrip() {
        let r = DoctrineRegistry::canonical();
        let j = serde_json::to_string(&r).unwrap();
        let back: DoctrineRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
