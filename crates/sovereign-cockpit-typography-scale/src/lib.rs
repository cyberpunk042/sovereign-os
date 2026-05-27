//! `sovereign-cockpit-typography-scale` — per-element type sizes.
//!
//! Operator picks one of 3 scales (Tight / Default / Generous); the
//! cockpit looks up per-element pt sizes for h1..h6 / body / caption.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 3 scales.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Scale {
    /// Tight (dense).
    Tight,
    /// Default.
    Default,
    /// Generous (large hero typography).
    Generous,
}

/// 8 type elements.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TypeElement {
    /// h1.
    H1,
    /// h2.
    H2,
    /// h3.
    H3,
    /// h4.
    H4,
    /// h5.
    H5,
    /// h6.
    H6,
    /// body.
    Body,
    /// caption.
    Caption,
}

/// State envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TypographyState {
    /// Schema version.
    pub schema_version: String,
    /// Current scale.
    pub scale: Scale,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TypographyError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
}

impl Scale {
    /// pt size for an element under this scale.
    pub fn pt_for(self, element: TypeElement) -> u16 {
        let base = match self {
            Scale::Tight => [22, 18, 16, 14, 12, 11, 11, 9],
            Scale::Default => [28, 22, 18, 16, 14, 12, 13, 10],
            Scale::Generous => [36, 28, 22, 18, 16, 14, 15, 11],
        };
        let idx = match element {
            TypeElement::H1 => 0,
            TypeElement::H2 => 1,
            TypeElement::H3 => 2,
            TypeElement::H4 => 3,
            TypeElement::H5 => 4,
            TypeElement::H6 => 5,
            TypeElement::Body => 6,
            TypeElement::Caption => 7,
        };
        base[idx]
    }
}

impl TypographyState {
    /// Default state — Default scale.
    pub fn default_state() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            scale: Scale::Default,
        }
    }

    /// Switch scale.
    pub fn switch(&mut self, s: Scale) {
        self.scale = s;
    }

    /// pt for element.
    pub fn pt(&self, e: TypeElement) -> u16 {
        self.scale.pt_for(e)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TypographyError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TypographyError::SchemaMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        TypographyState::default_state().validate().unwrap();
    }

    #[test]
    fn h1_largest_for_each_scale() {
        for s in [Scale::Tight, Scale::Default, Scale::Generous] {
            assert!(s.pt_for(TypeElement::H1) > s.pt_for(TypeElement::H2));
        }
    }

    #[test]
    fn caption_smallest_for_each_scale() {
        for s in [Scale::Tight, Scale::Default, Scale::Generous] {
            assert!(s.pt_for(TypeElement::Caption) <= s.pt_for(TypeElement::Body));
            assert!(s.pt_for(TypeElement::Caption) < s.pt_for(TypeElement::H6));
        }
    }

    #[test]
    fn scale_progression_monotonic() {
        for el in [TypeElement::H1, TypeElement::Body, TypeElement::Caption] {
            assert!(Scale::Tight.pt_for(el) <= Scale::Default.pt_for(el));
            assert!(Scale::Default.pt_for(el) <= Scale::Generous.pt_for(el));
        }
    }

    #[test]
    fn switch_updates() {
        let mut s = TypographyState::default_state();
        s.switch(Scale::Generous);
        assert_eq!(s.scale, Scale::Generous);
        assert_eq!(s.pt(TypeElement::H1), 36);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = TypographyState::default_state();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            TypographyError::SchemaMismatch
        ));
    }

    #[test]
    fn scale_serde_kebab() {
        assert_eq!(serde_json::to_string(&Scale::Tight).unwrap(), "\"tight\"");
        assert_eq!(
            serde_json::to_string(&Scale::Generous).unwrap(),
            "\"generous\""
        );
    }

    #[test]
    fn element_serde_kebab() {
        assert_eq!(serde_json::to_string(&TypeElement::H1).unwrap(), "\"h1\"");
        assert_eq!(
            serde_json::to_string(&TypeElement::Body).unwrap(),
            "\"body\""
        );
        assert_eq!(
            serde_json::to_string(&TypeElement::Caption).unwrap(),
            "\"caption\""
        );
    }

    #[test]
    fn state_serde_roundtrip() {
        let s = TypographyState::default_state();
        let j = serde_json::to_string(&s).unwrap();
        let back: TypographyState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
