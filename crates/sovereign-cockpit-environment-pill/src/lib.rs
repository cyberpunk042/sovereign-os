//! `sovereign-cockpit-environment-pill` — env risk label.
//!
//! Env{Dev/Staging/Prod/Custom}. Risk{Low/Medium/High}. Each
//! env maps to a default risk: Dev=Low, Staging=Medium, Prod=
//! High. Custom carries its own risk + label. requires_confirm
//! returns true for risk >= confirm_threshold.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Risk.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "kebab-case")]
pub enum Risk {
    /// Low.
    Low,
    /// Medium.
    Medium,
    /// High.
    High,
}

/// Environment kind.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "value")]
pub enum Env {
    /// Dev.
    Dev,
    /// Staging.
    Staging,
    /// Prod.
    Prod,
    /// Custom{label, risk}.
    Custom {
        /// Display label.
        label: String,
        /// Custom risk.
        risk: Risk,
    },
}

impl Env {
    /// Default risk.
    pub fn risk(&self) -> Risk {
        match self {
            Env::Dev => Risk::Low,
            Env::Staging => Risk::Medium,
            Env::Prod => Risk::High,
            Env::Custom { risk, .. } => *risk,
        }
    }

    /// Display label.
    pub fn label(&self) -> &str {
        match self {
            Env::Dev => "Dev",
            Env::Staging => "Staging",
            Env::Prod => "Prod",
            Env::Custom { label, .. } => label,
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EnvironmentPill {
    /// Schema version.
    pub schema_version: String,
    /// Environment.
    pub env: Env,
    /// Risk above which actions need confirmation.
    pub confirm_threshold: Risk,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PillError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("custom env label empty")]
    EmptyLabel,
}

impl EnvironmentPill {
    /// New.
    pub fn new(env: Env, confirm_threshold: Risk) -> Result<Self, PillError> {
        if let Env::Custom { label, .. } = &env {
            if label.is_empty() {
                return Err(PillError::EmptyLabel);
            }
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            env,
            confirm_threshold,
        })
    }

    /// Requires confirmation?
    pub fn requires_confirm(&self) -> bool {
        self.env.risk() >= self.confirm_threshold
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PillError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PillError::SchemaMismatch);
        }
        if let Env::Custom { label, .. } = &self.env {
            if label.is_empty() {
                return Err(PillError::EmptyLabel);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_risks() {
        assert_eq!(Env::Dev.risk(), Risk::Low);
        assert_eq!(Env::Staging.risk(), Risk::Medium);
        assert_eq!(Env::Prod.risk(), Risk::High);
    }

    #[test]
    fn labels() {
        assert_eq!(Env::Dev.label(), "Dev");
        assert_eq!(Env::Prod.label(), "Prod");
        let c = Env::Custom {
            label: "Sandbox".into(),
            risk: Risk::Low,
        };
        assert_eq!(c.label(), "Sandbox");
    }

    #[test]
    fn requires_confirm_at_or_above_threshold() {
        let p = EnvironmentPill::new(Env::Prod, Risk::High).unwrap();
        assert!(p.requires_confirm());
        let p = EnvironmentPill::new(Env::Staging, Risk::High).unwrap();
        assert!(!p.requires_confirm());
        let p = EnvironmentPill::new(Env::Staging, Risk::Medium).unwrap();
        assert!(p.requires_confirm());
    }

    #[test]
    fn custom_env_risk_used() {
        let p = EnvironmentPill::new(
            Env::Custom {
                label: "Canary".into(),
                risk: Risk::Medium,
            },
            Risk::Medium,
        )
        .unwrap();
        assert!(p.requires_confirm());
    }

    #[test]
    fn empty_custom_label_rejected() {
        let r = EnvironmentPill::new(
            Env::Custom {
                label: "".into(),
                risk: Risk::Low,
            },
            Risk::Medium,
        );
        assert!(matches!(r.unwrap_err(), PillError::EmptyLabel));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = EnvironmentPill::new(Env::Prod, Risk::High).unwrap();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PillError::SchemaMismatch
        ));
    }

    #[test]
    fn pill_serde_roundtrip() {
        let p = EnvironmentPill::new(
            Env::Custom {
                label: "X".into(),
                risk: Risk::High,
            },
            Risk::Medium,
        )
        .unwrap();
        let j = serde_json::to_string(&p).unwrap();
        let back: EnvironmentPill = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
