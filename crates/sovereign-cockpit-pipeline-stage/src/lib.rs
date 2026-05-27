//! `sovereign-cockpit-pipeline-stage` — staged pipeline state.
//!
//! Stage{id, depends_on, status, label}. add_stage registers
//! with deps. mark transitions status. ready_to_run returns
//! stages whose all-deps Status::Success and own status =
//! Pending. failed_chain returns stages affected (downstream
//! of any Failed dep).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Status {
    /// Pending.
    Pending,
    /// Running.
    Running,
    /// Success.
    Success,
    /// Failed.
    Failed,
    /// Skipped.
    Skipped,
}

/// Stage.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Stage {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// Dependencies (ids).
    pub depends_on: BTreeSet<String>,
    /// Status.
    pub status: Status,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Pipeline {
    /// Schema version.
    pub schema_version: String,
    /// id → stage.
    pub stages: BTreeMap<String, Stage>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PipeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate stage: {0}")]
    DuplicateStage(String),
    /// Unknown.
    #[error("unknown stage: {0}")]
    UnknownStage(String),
    /// Unknown dep.
    #[error("unknown dep {dep} for stage {stage}")]
    UnknownDep {
        /// Stage id.
        stage: String,
        /// Dep id.
        dep: String,
    },
}

impl Pipeline {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            stages: BTreeMap::new(),
        }
    }

    /// Add a stage.
    pub fn add_stage(&mut self, id: &str, label: &str, deps: Vec<String>) -> Result<(), PipeError> {
        if id.is_empty() {
            return Err(PipeError::EmptyId);
        }
        if label.is_empty() {
            return Err(PipeError::EmptyLabel);
        }
        if self.stages.contains_key(id) {
            return Err(PipeError::DuplicateStage(id.into()));
        }
        for d in &deps {
            if !self.stages.contains_key(d) {
                return Err(PipeError::UnknownDep {
                    stage: id.into(),
                    dep: d.clone(),
                });
            }
        }
        self.stages.insert(
            id.into(),
            Stage {
                id: id.into(),
                label: label.into(),
                depends_on: deps.into_iter().collect(),
                status: Status::Pending,
            },
        );
        Ok(())
    }

    /// Mark stage status.
    pub fn mark(&mut self, id: &str, status: Status) -> Result<(), PipeError> {
        let s = self
            .stages
            .get_mut(id)
            .ok_or_else(|| PipeError::UnknownStage(id.into()))?;
        s.status = status;
        Ok(())
    }

    /// Stages ready to run: Pending + all deps Success.
    pub fn ready_to_run(&self) -> Vec<&str> {
        self.stages
            .iter()
            .filter(|(_, s)| {
                s.status == Status::Pending
                    && s.depends_on.iter().all(|d| {
                        self.stages
                            .get(d)
                            .map(|x| x.status == Status::Success)
                            .unwrap_or(false)
                    })
            })
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Stages downstream of any Failed dep.
    pub fn failed_chain(&self) -> Vec<&str> {
        self.stages
            .iter()
            .filter(|(_, s)| {
                s.status == Status::Pending
                    && s.depends_on.iter().any(|d| {
                        self.stages
                            .get(d)
                            .map(|x| x.status == Status::Failed)
                            .unwrap_or(false)
                    })
            })
            .map(|(k, _)| k.as_str())
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PipeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PipeError::SchemaMismatch);
        }
        for (id, s) in &self.stages {
            if id.is_empty() {
                return Err(PipeError::EmptyId);
            }
            if s.label.is_empty() {
                return Err(PipeError::EmptyLabel);
            }
            for d in &s.depends_on {
                if !self.stages.contains_key(d) {
                    return Err(PipeError::UnknownDep {
                        stage: id.clone(),
                        dep: d.clone(),
                    });
                }
            }
        }
        Ok(())
    }
}

impl Default for Pipeline {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pipeline() -> Pipeline {
        let mut p = Pipeline::new();
        p.add_stage("build", "Build", vec![]).unwrap();
        p.add_stage("test", "Test", vec!["build".into()]).unwrap();
        p.add_stage("deploy", "Deploy", vec!["test".into()])
            .unwrap();
        p
    }

    #[test]
    fn ready_initially_is_root() {
        let p = pipeline();
        assert_eq!(p.ready_to_run(), vec!["build"]);
    }

    #[test]
    fn ready_after_success() {
        let mut p = pipeline();
        p.mark("build", Status::Success).unwrap();
        assert_eq!(p.ready_to_run(), vec!["test"]);
    }

    #[test]
    fn failed_chain_marks_downstream() {
        let mut p = pipeline();
        p.mark("build", Status::Failed).unwrap();
        // test depends on build (Failed) → in failed_chain.
        assert_eq!(p.failed_chain(), vec!["test"]);
    }

    #[test]
    fn duplicate_rejected() {
        let mut p = pipeline();
        assert!(matches!(
            p.add_stage("build", "X", vec![]).unwrap_err(),
            PipeError::DuplicateStage(_)
        ));
    }

    #[test]
    fn unknown_dep_rejected() {
        let mut p = Pipeline::new();
        let r = p.add_stage("a", "A", vec!["nope".into()]);
        assert!(matches!(r.unwrap_err(), PipeError::UnknownDep { .. }));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut p = Pipeline::new();
        assert!(matches!(
            p.add_stage("", "L", vec![]).unwrap_err(),
            PipeError::EmptyId
        ));
        assert!(matches!(
            p.add_stage("a", "", vec![]).unwrap_err(),
            PipeError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut p = pipeline();
        p.schema_version = "9.9.9".into();
        assert!(matches!(
            p.validate().unwrap_err(),
            PipeError::SchemaMismatch
        ));
    }

    #[test]
    fn pipe_serde_roundtrip() {
        let p = pipeline();
        let j = serde_json::to_string(&p).unwrap();
        let back: Pipeline = serde_json::from_str(&j).unwrap();
        assert_eq!(p, back);
    }
}
