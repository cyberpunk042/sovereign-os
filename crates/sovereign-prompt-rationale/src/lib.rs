//! `sovereign-prompt-rationale` — per-dispatch explanation envelope.
//!
//! Each model dispatch the cockpit issues carries a `Rationale`
//! recording which provider, template, bundle, mode, and doctrine drove
//! the decision. The cockpit surfaces the rationale chip next to the
//! model output.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_profile_bundles::BundleName;
use sovereign_provider_catalog::ProviderId;
use sovereign_doctrinal_preservation::DoctrineTag;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One rationale entry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Rationale {
    /// Schema version.
    pub schema_version: String,
    /// M049 trace_id.
    pub trace_id: String,
    /// Provider routed to.
    pub provider: ProviderId,
    /// Template name used (empty when ad-hoc prompt).
    pub template_name: String,
    /// Bundle at dispatch.
    pub bundle: BundleName,
    /// Mode at dispatch.
    pub mode: ExecutionMode,
    /// Driving doctrine.
    pub primary_doctrine: DoctrineTag,
    /// Short operator-readable reason ("user typed-cmd", "from-template smoke", etc.).
    pub reason: String,
    /// ISO-8601 UTC.
    pub at: String,
}

/// Errors.
#[derive(Debug, Error)]
pub enum RationaleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty trace_id.
    #[error("trace_id missing")]
    MissingTraceId,
    /// Empty reason.
    #[error("reason missing")]
    MissingReason,
    /// Empty timestamp.
    #[error("at missing")]
    MissingTimestamp,
}

impl Rationale {
    /// Build a rationale.
    #[allow(clippy::too_many_arguments)]
    pub fn build(
        trace_id: &str,
        provider: ProviderId,
        template_name: &str,
        bundle: BundleName,
        mode: ExecutionMode,
        primary_doctrine: DoctrineTag,
        reason: &str,
        at: &str,
    ) -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            trace_id: trace_id.into(),
            provider, template_name: template_name.into(), bundle, mode,
            primary_doctrine,
            reason: reason.into(),
            at: at.into(),
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), RationaleError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RationaleError::SchemaMismatch);
        }
        if self.trace_id.is_empty() { return Err(RationaleError::MissingTraceId); }
        if self.reason.is_empty() { return Err(RationaleError::MissingReason); }
        if self.at.is_empty() { return Err(RationaleError::MissingTimestamp); }
        Ok(())
    }

    /// True if this rationale used a template (vs ad-hoc prompt).
    pub fn used_template(&self) -> bool {
        !self.template_name.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r() -> Rationale {
        Rationale::build(
            "tr-1",
            ProviderId::LocalOllama,
            "greet",
            BundleName::Careful,
            ExecutionMode::Execute,
            DoctrineTag::NotEveryPrompt,
            "operator typed at command palette",
            "2026-05-19T03:00:00Z",
        )
    }

    #[test]
    fn ok_rationale_validates() {
        r().validate().unwrap();
    }

    #[test]
    fn missing_trace_id_caught() {
        let mut x = r();
        x.trace_id = String::new();
        assert!(matches!(x.validate().unwrap_err(), RationaleError::MissingTraceId));
    }

    #[test]
    fn missing_reason_caught() {
        let mut x = r();
        x.reason = String::new();
        assert!(matches!(x.validate().unwrap_err(), RationaleError::MissingReason));
    }

    #[test]
    fn missing_timestamp_caught() {
        let mut x = r();
        x.at = String::new();
        assert!(matches!(x.validate().unwrap_err(), RationaleError::MissingTimestamp));
    }

    #[test]
    fn used_template_flag() {
        let r1 = r();
        assert!(r1.used_template());
        let r2 = Rationale::build("tr-2", ProviderId::Mock, "", BundleName::Private,
            ExecutionMode::Plan, DoctrineTag::AgentRequirement, "ad-hoc", "t");
        assert!(!r2.used_template());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut x = r();
        x.schema_version = "9.9.9".into();
        assert!(matches!(x.validate().unwrap_err(), RationaleError::SchemaMismatch));
    }

    #[test]
    fn rationale_serde_roundtrip() {
        let x = r();
        let j = serde_json::to_string(&x).unwrap();
        let back: Rationale = serde_json::from_str(&j).unwrap();
        assert_eq!(x, back);
    }
}
