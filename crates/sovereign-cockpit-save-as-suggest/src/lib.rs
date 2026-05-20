//! `sovereign-cockpit-save-as-suggest` — collision-avoiding name.
//!
//! suggest(base, ext, existing) returns "<base>.<ext>" if not
//! taken, else "<base>-2.<ext>", "<base>-3.<ext>", ... until
//! finding an unused name. Existing is a set of taken names.
//! ext may be empty.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Versioned state placeholder.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SaveAsState {
    /// Schema version.
    pub schema_version: String,
    /// Last suggested name.
    pub last: Option<String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum SuggestError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("base empty")]
    EmptyBase,
}

/// Suggest a unique name based on (base, ext, existing).
pub fn suggest(base: &str, ext: &str, existing: &BTreeSet<String>) -> Result<String, SuggestError> {
    if base.is_empty() { return Err(SuggestError::EmptyBase); }
    let make = |suffix: &str| if ext.is_empty() { format!("{}{}", base, suffix) } else { format!("{}{}.{}", base, suffix, ext) };
    let primary = make("");
    if !existing.contains(&primary) {
        return Ok(primary);
    }
    let mut n: u32 = 2;
    loop {
        let cand = make(&format!("-{}", n));
        if !existing.contains(&cand) { return Ok(cand); }
        n = n.saturating_add(1);
        // Safety cap.
        if n > 100_000 { return Ok(cand); }
    }
}

impl SaveAsState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            last: None,
        }
    }

    /// Suggest + store.
    pub fn suggest_and_store(&mut self, base: &str, ext: &str, existing: &BTreeSet<String>) -> Result<String, SuggestError> {
        let name = suggest(base, ext, existing)?;
        self.last = Some(name.clone());
        Ok(name)
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), SuggestError> {
        if self.schema_version != SCHEMA_VERSION { return Err(SuggestError::SchemaMismatch); }
        Ok(())
    }
}

impl Default for SaveAsState {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn set(items: &[&str]) -> BTreeSet<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn primary_used_when_unique() {
        let n = suggest("report", "md", &set(&[])).unwrap();
        assert_eq!(n, "report.md");
    }

    #[test]
    fn collision_appends_2() {
        let n = suggest("report", "md", &set(&["report.md"])).unwrap();
        assert_eq!(n, "report-2.md");
    }

    #[test]
    fn cascading_collision_3() {
        let n = suggest("report", "md", &set(&["report.md", "report-2.md"])).unwrap();
        assert_eq!(n, "report-3.md");
    }

    #[test]
    fn no_extension() {
        let n = suggest("Makefile", "", &set(&["Makefile"])).unwrap();
        assert_eq!(n, "Makefile-2");
    }

    #[test]
    fn empty_base_rejected() {
        assert!(matches!(suggest("", "md", &set(&[])).unwrap_err(), SuggestError::EmptyBase));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = SaveAsState::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), SuggestError::SchemaMismatch));
    }

    #[test]
    fn state_serde_roundtrip() {
        let mut s = SaveAsState::new();
        s.suggest_and_store("x", "txt", &set(&[])).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: SaveAsState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
