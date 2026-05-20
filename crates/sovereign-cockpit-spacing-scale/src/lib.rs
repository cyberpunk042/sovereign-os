//! `sovereign-cockpit-spacing-scale` — token-based spacing.
//!
//! Token{None/Xxs/Xs/Sm/Md/Lg/Xl/Xxl/Xxxl}. Default px values
//! 0/2/4/8/12/16/24/32/48; px(token) returns the px for the
//! token. Custom values must be non-decreasing. multiply(scalar)
//! scales every token by scalar (clamped against u32 overflow).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Spacing token.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Token {
    /// None (0).
    None,
    /// Extra-extra small.
    Xxs,
    /// Extra small.
    Xs,
    /// Small.
    Sm,
    /// Medium.
    Md,
    /// Large.
    Lg,
    /// Extra large.
    Xl,
    /// Extra extra large.
    Xxl,
    /// Extra extra extra large.
    Xxxl,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SpacingScale {
    /// Schema version.
    pub schema_version: String,
    /// None px.
    pub none_px: u32,
    /// Xxs.
    pub xxs_px: u32,
    /// Xs.
    pub xs_px: u32,
    /// Sm.
    pub sm_px: u32,
    /// Md.
    pub md_px: u32,
    /// Lg.
    pub lg_px: u32,
    /// Xl.
    pub xl_px: u32,
    /// Xxl.
    pub xxl_px: u32,
    /// Xxxl.
    pub xxxl_px: u32,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ScaleError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Not non-decreasing.
    #[error("values must be non-decreasing")]
    NotMonotone,
}

impl SpacingScale {
    /// New with defaults (0/2/4/8/12/16/24/32/48).
    pub fn defaults() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            none_px: 0,
            xxs_px: 2,
            xs_px: 4,
            sm_px: 8,
            md_px: 12,
            lg_px: 16,
            xl_px: 24,
            xxl_px: 32,
            xxxl_px: 48,
        }
    }

    /// Px value of a token.
    pub fn px(&self, t: Token) -> u32 {
        match t {
            Token::None => self.none_px,
            Token::Xxs => self.xxs_px,
            Token::Xs => self.xs_px,
            Token::Sm => self.sm_px,
            Token::Md => self.md_px,
            Token::Lg => self.lg_px,
            Token::Xl => self.xl_px,
            Token::Xxl => self.xxl_px,
            Token::Xxxl => self.xxxl_px,
        }
    }

    /// Multiply every value by scalar.
    pub fn multiply(&mut self, scalar: u32) {
        let mul = |v: u32| v.saturating_mul(scalar);
        self.none_px = mul(self.none_px);
        self.xxs_px = mul(self.xxs_px);
        self.xs_px = mul(self.xs_px);
        self.sm_px = mul(self.sm_px);
        self.md_px = mul(self.md_px);
        self.lg_px = mul(self.lg_px);
        self.xl_px = mul(self.xl_px);
        self.xxl_px = mul(self.xxl_px);
        self.xxxl_px = mul(self.xxxl_px);
    }

    /// Validate (non-decreasing).
    pub fn validate(&self) -> Result<(), ScaleError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ScaleError::SchemaMismatch); }
        let seq = [
            self.none_px, self.xxs_px, self.xs_px, self.sm_px, self.md_px,
            self.lg_px, self.xl_px, self.xxl_px, self.xxxl_px,
        ];
        for w in seq.windows(2) {
            if w[1] < w[0] { return Err(ScaleError::NotMonotone); }
        }
        Ok(())
    }
}

impl Default for SpacingScale {
    fn default() -> Self { Self::defaults() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_correct() {
        let s = SpacingScale::defaults();
        assert_eq!(s.px(Token::None), 0);
        assert_eq!(s.px(Token::Xs), 4);
        assert_eq!(s.px(Token::Md), 12);
        assert_eq!(s.px(Token::Xxxl), 48);
    }

    #[test]
    fn multiply_scales() {
        let mut s = SpacingScale::defaults();
        s.multiply(2);
        assert_eq!(s.px(Token::Md), 24);
        assert_eq!(s.px(Token::Xxxl), 96);
    }

    #[test]
    fn validate_defaults() {
        let s = SpacingScale::defaults();
        assert!(s.validate().is_ok());
    }

    #[test]
    fn non_monotone_rejected() {
        let mut s = SpacingScale::defaults();
        s.md_px = 100;
        s.lg_px = 50;
        assert!(matches!(s.validate().unwrap_err(), ScaleError::NotMonotone));
    }

    #[test]
    fn multiply_overflow_saturates() {
        let mut s = SpacingScale::defaults();
        s.multiply(u32::MAX);
        assert_eq!(s.px(Token::None), 0);
        assert_eq!(s.px(Token::Xxxl), u32::MAX);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SpacingScale::defaults();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), ScaleError::SchemaMismatch));
    }

    #[test]
    fn scale_serde_roundtrip() {
        let s = SpacingScale::defaults();
        let j = serde_json::to_string(&s).unwrap();
        let back: SpacingScale = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
