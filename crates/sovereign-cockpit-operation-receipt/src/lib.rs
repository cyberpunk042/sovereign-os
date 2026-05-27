//! `sovereign-cockpit-operation-receipt` — bounded receipts.
//!
//! Receipt{id, action, Outcome{Success/Failure(err)}, ts_ms}.
//! record_success / record_failure append; capacity drops
//! oldest. recent(n) returns up to n newest; failures()
//! filters by outcome.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Outcome.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "outcome", content = "error")]
pub enum Outcome {
    /// Success.
    Success,
    /// Failure(error).
    Failure(String),
}

/// Receipt.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Receipt {
    /// Id.
    pub id: String,
    /// Action description.
    pub action: String,
    /// Outcome.
    pub outcome: Outcome,
    /// ts ms.
    pub ts_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct OperationReceiptList {
    /// Schema version.
    pub schema_version: String,
    /// Capacity.
    pub capacity: u32,
    /// Receipts newest-last.
    pub receipts: Vec<Receipt>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ReceiptError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("action empty")]
    EmptyAction,
    /// Empty.
    #[error("error empty")]
    EmptyError,
    /// Zero capacity.
    #[error("capacity must be >= 1")]
    ZeroCapacity,
}

impl OperationReceiptList {
    /// New.
    pub fn new(capacity: u32) -> Result<Self, ReceiptError> {
        if capacity == 0 {
            return Err(ReceiptError::ZeroCapacity);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            capacity,
            receipts: Vec::new(),
        })
    }

    fn push(&mut self, r: Receipt) {
        if (self.receipts.len() as u32) >= self.capacity {
            self.receipts.remove(0);
        }
        self.receipts.push(r);
    }

    /// Record success.
    pub fn record_success(
        &mut self,
        id: &str,
        action: &str,
        ts_ms: u64,
    ) -> Result<(), ReceiptError> {
        if id.is_empty() {
            return Err(ReceiptError::EmptyId);
        }
        if action.is_empty() {
            return Err(ReceiptError::EmptyAction);
        }
        self.push(Receipt {
            id: id.into(),
            action: action.into(),
            outcome: Outcome::Success,
            ts_ms,
        });
        Ok(())
    }

    /// Record failure.
    pub fn record_failure(
        &mut self,
        id: &str,
        action: &str,
        error: &str,
        ts_ms: u64,
    ) -> Result<(), ReceiptError> {
        if id.is_empty() {
            return Err(ReceiptError::EmptyId);
        }
        if action.is_empty() {
            return Err(ReceiptError::EmptyAction);
        }
        if error.is_empty() {
            return Err(ReceiptError::EmptyError);
        }
        self.push(Receipt {
            id: id.into(),
            action: action.into(),
            outcome: Outcome::Failure(error.into()),
            ts_ms,
        });
        Ok(())
    }

    /// Recent n receipts (newest first).
    pub fn recent(&self, n: usize) -> Vec<&Receipt> {
        self.receipts.iter().rev().take(n).collect()
    }

    /// Failures only.
    pub fn failures(&self) -> Vec<&Receipt> {
        self.receipts
            .iter()
            .filter(|r| matches!(r.outcome, Outcome::Failure(_)))
            .collect()
    }

    /// Clear.
    pub fn clear(&mut self) {
        self.receipts.clear();
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ReceiptError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ReceiptError::SchemaMismatch);
        }
        if self.capacity == 0 {
            return Err(ReceiptError::ZeroCapacity);
        }
        for r in &self.receipts {
            if r.id.is_empty() {
                return Err(ReceiptError::EmptyId);
            }
            if r.action.is_empty() {
                return Err(ReceiptError::EmptyAction);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_and_recent() {
        let mut l = OperationReceiptList::new(5).unwrap();
        l.record_success("a", "save", 100).unwrap();
        l.record_failure("b", "send", "network", 200).unwrap();
        let r = l.recent(2);
        assert_eq!(r[0].id, "b");
        assert_eq!(r[1].id, "a");
    }

    #[test]
    fn failures_filter() {
        let mut l = OperationReceiptList::new(5).unwrap();
        l.record_success("a", "x", 0).unwrap();
        l.record_failure("b", "y", "e", 0).unwrap();
        assert_eq!(l.failures().len(), 1);
    }

    #[test]
    fn capacity_drops_oldest() {
        let mut l = OperationReceiptList::new(2).unwrap();
        l.record_success("a", "x", 0).unwrap();
        l.record_success("b", "y", 1).unwrap();
        l.record_success("c", "z", 2).unwrap();
        let ids: Vec<&str> = l.receipts.iter().map(|r| r.id.as_str()).collect();
        assert_eq!(ids, vec!["b", "c"]);
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut l = OperationReceiptList::new(5).unwrap();
        assert!(matches!(
            l.record_success("", "x", 0).unwrap_err(),
            ReceiptError::EmptyId
        ));
        assert!(matches!(
            l.record_success("a", "", 0).unwrap_err(),
            ReceiptError::EmptyAction
        ));
        assert!(matches!(
            l.record_failure("a", "x", "", 0).unwrap_err(),
            ReceiptError::EmptyError
        ));
        assert!(matches!(
            OperationReceiptList::new(0).unwrap_err(),
            ReceiptError::ZeroCapacity
        ));
    }

    #[test]
    fn clear_resets() {
        let mut l = OperationReceiptList::new(5).unwrap();
        l.record_success("a", "x", 0).unwrap();
        l.clear();
        assert!(l.receipts.is_empty());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut l = OperationReceiptList::new(5).unwrap();
        l.schema_version = "9.9.9".into();
        assert!(matches!(
            l.validate().unwrap_err(),
            ReceiptError::SchemaMismatch
        ));
    }

    #[test]
    fn list_serde_roundtrip() {
        let mut l = OperationReceiptList::new(5).unwrap();
        l.record_success("a", "x", 0).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: OperationReceiptList = serde_json::from_str(&j).unwrap();
        assert_eq!(l, back);
    }
}
