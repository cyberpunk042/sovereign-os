//! `sovereign-cockpit-image-load-state` — image load lifecycle.
//!
//! Image{url, placeholder, phase Idle/Loading/Loaded/Failed,
//! started_at_ms, loaded_at_ms}. begin(url, ts) Idle→Loading.
//! load(url, ts) Loading→Loaded. fail(url, err, ts) Loading→Failed.
//! Each image keyed by url.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Phase.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "phase", content = "error")]
pub enum Phase {
    /// Idle.
    Idle,
    /// Loading.
    Loading,
    /// Loaded.
    Loaded,
    /// Failed(reason).
    Failed(String),
}

/// Image record.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Image {
    /// Url (key).
    pub url: String,
    /// Optional low-fi placeholder (e.g. blurhash, dominant color).
    pub placeholder: String,
    /// Phase.
    pub phase: Phase,
    /// Started ms.
    pub started_at_ms: u64,
    /// Loaded/failed ms.
    pub ended_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ImageLoadState {
    /// Schema version.
    pub schema_version: String,
    /// url → image.
    pub images: BTreeMap<String, Image>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum LoadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("url empty")]
    EmptyUrl,
    /// Empty.
    #[error("error empty")]
    EmptyError,
    /// Unknown.
    #[error("unknown url: {0}")]
    Unknown(String),
    /// Invalid phase.
    #[error("invalid phase for operation")]
    InvalidPhase,
}

impl ImageLoadState {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            images: BTreeMap::new(),
        }
    }

    /// Register with placeholder.
    pub fn register(&mut self, url: &str, placeholder: &str) -> Result<(), LoadError> {
        if url.is_empty() {
            return Err(LoadError::EmptyUrl);
        }
        self.images.entry(url.into()).or_insert(Image {
            url: url.into(),
            placeholder: placeholder.into(),
            phase: Phase::Idle,
            started_at_ms: 0,
            ended_at_ms: 0,
        });
        Ok(())
    }

    /// Begin loading.
    pub fn begin(&mut self, url: &str, ts_ms: u64) -> Result<(), LoadError> {
        if url.is_empty() {
            return Err(LoadError::EmptyUrl);
        }
        let img = self.images.entry(url.into()).or_insert(Image {
            url: url.into(),
            placeholder: String::new(),
            phase: Phase::Idle,
            started_at_ms: 0,
            ended_at_ms: 0,
        });
        if !matches!(img.phase, Phase::Idle | Phase::Failed(_)) {
            return Err(LoadError::InvalidPhase);
        }
        img.phase = Phase::Loading;
        img.started_at_ms = ts_ms;
        Ok(())
    }

    /// Loaded.
    pub fn load(&mut self, url: &str, ts_ms: u64) -> Result<(), LoadError> {
        let img = self
            .images
            .get_mut(url)
            .ok_or_else(|| LoadError::Unknown(url.into()))?;
        if img.phase != Phase::Loading {
            return Err(LoadError::InvalidPhase);
        }
        img.phase = Phase::Loaded;
        img.ended_at_ms = ts_ms;
        Ok(())
    }

    /// Failed.
    pub fn fail(&mut self, url: &str, err: &str, ts_ms: u64) -> Result<(), LoadError> {
        if err.is_empty() {
            return Err(LoadError::EmptyError);
        }
        let img = self
            .images
            .get_mut(url)
            .ok_or_else(|| LoadError::Unknown(url.into()))?;
        if img.phase != Phase::Loading {
            return Err(LoadError::InvalidPhase);
        }
        img.phase = Phase::Failed(err.into());
        img.ended_at_ms = ts_ms;
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), LoadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(LoadError::SchemaMismatch);
        }
        for k in self.images.keys() {
            if k.is_empty() {
                return Err(LoadError::EmptyUrl);
            }
        }
        Ok(())
    }
}

impl Default for ImageLoadState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn begin_then_load() {
        let mut s = ImageLoadState::new();
        s.register("u1", "blur").unwrap();
        s.begin("u1", 100).unwrap();
        s.load("u1", 200).unwrap();
        assert_eq!(s.images.get("u1").unwrap().phase, Phase::Loaded);
    }

    #[test]
    fn begin_then_fail() {
        let mut s = ImageLoadState::new();
        s.begin("u1", 100).unwrap();
        s.fail("u1", "404", 200).unwrap();
        assert!(matches!(
            s.images.get("u1").unwrap().phase,
            Phase::Failed(_)
        ));
    }

    #[test]
    fn retry_after_failure() {
        let mut s = ImageLoadState::new();
        s.begin("u1", 100).unwrap();
        s.fail("u1", "500", 150).unwrap();
        s.begin("u1", 200).unwrap();
        assert_eq!(s.images.get("u1").unwrap().phase, Phase::Loading);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = ImageLoadState::new();
        assert!(matches!(s.begin("", 0).unwrap_err(), LoadError::EmptyUrl));
        s.begin("u1", 0).unwrap();
        assert!(matches!(
            s.fail("u1", "", 1).unwrap_err(),
            LoadError::EmptyError
        ));
    }

    #[test]
    fn invalid_transition_rejected() {
        let mut s = ImageLoadState::new();
        s.begin("u1", 100).unwrap();
        s.load("u1", 200).unwrap();
        // Cannot load again from Loaded.
        assert!(matches!(
            s.load("u1", 300).unwrap_err(),
            LoadError::InvalidPhase
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = ImageLoadState::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            LoadError::SchemaMismatch
        ));
    }

    #[test]
    fn image_serde_roundtrip() {
        let mut s = ImageLoadState::new();
        s.register("u1", "blur").unwrap();
        s.begin("u1", 100).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: ImageLoadState = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
