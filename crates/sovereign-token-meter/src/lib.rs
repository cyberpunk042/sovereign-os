//! `sovereign-token-meter` — token accounting and cost metering.
//!
//! The sovereign runtime's premise is cost-aware, `$0`-target inference: route
//! cheap work to local quantized models and only spill to paid cloud when it
//! pays off. That decision needs *accounting* — how many tokens a session has
//! consumed, whether the next request fits a budget, and what it would cost.
//! This crate is that ledger.
//!
//! A [`TokenMeter`] tracks input and output tokens, optionally caps total and
//! output tokens via a [`Budget`], answers "can I afford `n` more output
//! tokens?" *before* a spend (so a request can be rejected or down-routed
//! rather than overrunning), and estimates cost from per-1k-token prices.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the token-meter surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Cumulative token usage.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Usage {
    /// Tokens consumed as input (prompt).
    pub input_tokens: usize,
    /// Tokens produced as output (completion).
    pub output_tokens: usize,
}

impl Usage {
    /// Total tokens (input + output).
    pub fn total(&self) -> usize {
        self.input_tokens + self.output_tokens
    }
}

/// Optional caps on usage.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Budget {
    /// Maximum total tokens, if any.
    pub max_total: Option<usize>,
    /// Maximum output tokens, if any.
    pub max_output: Option<usize>,
}

impl Budget {
    /// An unlimited budget.
    pub fn unlimited() -> Self {
        Self::default()
    }

    /// A budget capping total tokens.
    pub fn total(max_total: usize) -> Self {
        Self {
            max_total: Some(max_total),
            max_output: None,
        }
    }
}

/// Why a spend was rejected.
#[derive(Debug, Error, PartialEq)]
pub enum MeterError {
    /// The spend would exceed the total-token budget.
    #[error("total budget exceeded: {used} + {requested} > {max}")]
    TotalExceeded {
        /// Tokens already used.
        used: usize,
        /// Tokens requested.
        requested: usize,
        /// The cap.
        max: usize,
    },
    /// The spend would exceed the output-token budget.
    #[error("output budget exceeded: {used} + {requested} > {max}")]
    OutputExceeded {
        /// Output tokens already used.
        used: usize,
        /// Output tokens requested.
        requested: usize,
        /// The cap.
        max: usize,
    },
}

/// A running token ledger with optional budgets.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct TokenMeter {
    usage: Usage,
    budget: Budget,
}

impl TokenMeter {
    /// A meter with no limits.
    pub fn new() -> Self {
        Self::default()
    }

    /// A meter with the given budget.
    pub fn with_budget(budget: Budget) -> Self {
        Self {
            usage: Usage::default(),
            budget,
        }
    }

    /// Current usage.
    pub fn usage(&self) -> Usage {
        self.usage
    }

    /// Record `n` input tokens (prompt). Input is not output-capped but does
    /// count toward the total budget; over-total input still records (the
    /// prompt was already consumed) but [`over_budget`](Self::over_budget)
    /// will report it.
    pub fn record_input(&mut self, n: usize) {
        self.usage.input_tokens += n;
    }

    /// Record `n` output tokens (completion).
    pub fn record_output(&mut self, n: usize) {
        self.usage.output_tokens += n;
    }

    /// Whether `n` more output tokens fit within both budgets.
    pub fn can_spend_output(&self, n: usize) -> bool {
        self.check_output(n).is_ok()
    }

    /// Pre-flight check for `n` output tokens; records them only if they fit.
    pub fn try_spend_output(&mut self, n: usize) -> Result<(), MeterError> {
        self.check_output(n)?;
        self.record_output(n);
        Ok(())
    }

    fn check_output(&self, n: usize) -> Result<(), MeterError> {
        if let Some(max) = self.budget.max_output {
            if self.usage.output_tokens + n > max {
                return Err(MeterError::OutputExceeded {
                    used: self.usage.output_tokens,
                    requested: n,
                    max,
                });
            }
        }
        if let Some(max) = self.budget.max_total {
            if self.usage.total() + n > max {
                return Err(MeterError::TotalExceeded {
                    used: self.usage.total(),
                    requested: n,
                    max,
                });
            }
        }
        Ok(())
    }

    /// Remaining total tokens before the cap (`None` if uncapped).
    pub fn remaining_total(&self) -> Option<usize> {
        self.budget
            .max_total
            .map(|m| m.saturating_sub(self.usage.total()))
    }

    /// Remaining output tokens before the cap (`None` if uncapped).
    pub fn remaining_output(&self) -> Option<usize> {
        self.budget
            .max_output
            .map(|m| m.saturating_sub(self.usage.output_tokens))
    }

    /// Whether any budget has been exceeded.
    pub fn over_budget(&self) -> bool {
        self.budget
            .max_total
            .is_some_and(|m| self.usage.total() > m)
            || self
                .budget
                .max_output
                .is_some_and(|m| self.usage.output_tokens > m)
    }

    /// Estimated cost given per-1k-token prices for input and output.
    pub fn cost(&self, input_per_1k: f64, output_per_1k: f64) -> f64 {
        (self.usage.input_tokens as f64 / 1000.0) * input_per_1k
            + (self.usage.output_tokens as f64 / 1000.0) * output_per_1k
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accounts_input_and_output() {
        let mut m = TokenMeter::new();
        m.record_input(100);
        m.record_output(40);
        assert_eq!(m.usage().input_tokens, 100);
        assert_eq!(m.usage().output_tokens, 40);
        assert_eq!(m.usage().total(), 140);
    }

    #[test]
    fn unlimited_meter_never_over_budget() {
        let mut m = TokenMeter::new();
        m.record_input(1_000_000);
        m.record_output(1_000_000);
        assert!(!m.over_budget());
        assert!(m.can_spend_output(usize::MAX / 2));
        assert_eq!(m.remaining_total(), None);
    }

    #[test]
    fn output_budget_is_enforced() {
        let mut m = TokenMeter::with_budget(Budget {
            max_total: None,
            max_output: Some(50),
        });
        m.record_output(40);
        assert!(m.can_spend_output(10));
        assert!(!m.can_spend_output(11));
        assert_eq!(m.remaining_output(), Some(10));
        assert_eq!(
            m.try_spend_output(20).unwrap_err(),
            MeterError::OutputExceeded {
                used: 40,
                requested: 20,
                max: 50
            }
        );
        // a fitting spend records
        m.try_spend_output(10).unwrap();
        assert_eq!(m.usage().output_tokens, 50);
    }

    #[test]
    fn total_budget_counts_input_and_output() {
        let mut m = TokenMeter::with_budget(Budget::total(100));
        m.record_input(80);
        assert!(m.can_spend_output(20));
        assert!(!m.can_spend_output(21));
        assert_eq!(m.remaining_total(), Some(20));
        assert_eq!(
            m.try_spend_output(50).unwrap_err(),
            MeterError::TotalExceeded {
                used: 80,
                requested: 50,
                max: 100
            }
        );
    }

    #[test]
    fn over_budget_detects_overruns() {
        let mut m = TokenMeter::with_budget(Budget::total(10));
        m.record_input(8);
        m.record_output(5); // total 13 > 10 (input was already consumed)
        assert!(m.over_budget());
        assert_eq!(m.remaining_total(), Some(0)); // saturating
    }

    #[test]
    fn cost_estimation() {
        let mut m = TokenMeter::new();
        m.record_input(2000); // 2k input
        m.record_output(500); // 0.5k output
        // $0.50/1k in, $1.50/1k out → 2*0.5 + 0.5*1.5 = 1.0 + 0.75 = 1.75
        assert!((m.cost(0.50, 1.50) - 1.75).abs() < 1e-9);
        // local $0 model costs nothing
        assert_eq!(m.cost(0.0, 0.0), 0.0);
    }

    #[test]
    fn serde_round_trip() {
        let mut m = TokenMeter::with_budget(Budget::total(1000));
        m.record_input(10);
        m.record_output(5);
        let j = serde_json::to_string(&m).unwrap();
        let back: TokenMeter = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
