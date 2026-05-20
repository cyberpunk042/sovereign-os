//! `sovereign-cockpit-filter-builder` — boolean filter clauses.
//!
//! A `Clause` is `{ field, op, value }`. Clauses are combined under
//! an outer `Combinator { And, Or }`, optionally negated via
//! `negated`. The builder lets a UI add/remove/move clauses and
//! produces a stable `Filter` for evaluation downstream.
//!
//! `render_query()` produces a deterministic text form like
//! `(status:open AND priority:>=5)` for display.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Combinator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Combinator {
    /// All clauses must match.
    And,
    /// Any clause must match.
    Or,
}

/// Operator.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Op {
    /// Equals.
    Eq,
    /// Not equals.
    Ne,
    /// Greater than or equal.
    Gte,
    /// Less than or equal.
    Lte,
    /// Substring contains.
    Contains,
    /// Starts-with.
    StartsWith,
}

impl Op {
    /// Compact symbol.
    pub fn symbol(self) -> &'static str {
        match self {
            Op::Eq => ":",
            Op::Ne => ":!=",
            Op::Gte => ":>=",
            Op::Lte => ":<=",
            Op::Contains => ":~",
            Op::StartsWith => ":^",
        }
    }
}

/// Clause.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Clause {
    /// Field.
    pub field: String,
    /// Operator.
    pub op: Op,
    /// Value (caller-encoded).
    pub value: String,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FilterBuilder {
    /// Schema version.
    pub schema_version: String,
    /// Combinator.
    pub combinator: Combinator,
    /// Negated (apply NOT to whole filter).
    pub negated: bool,
    /// Clauses in display order.
    pub clauses: Vec<Clause>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FilterError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty field.
    #[error("field empty")]
    EmptyField,
    /// Empty value.
    #[error("value empty")]
    EmptyValue,
    /// Out of range index.
    #[error("index {0} out of range")]
    OutOfRange(usize),
}

impl FilterBuilder {
    /// New (And, not negated).
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            combinator: Combinator::And,
            negated: false,
            clauses: Vec::new(),
        }
    }

    /// Append a clause.
    pub fn push(&mut self, field: &str, op: Op, value: &str) -> Result<(), FilterError> {
        if field.is_empty() { return Err(FilterError::EmptyField); }
        if value.is_empty() { return Err(FilterError::EmptyValue); }
        self.clauses.push(Clause { field: field.into(), op, value: value.into() });
        Ok(())
    }

    /// Remove by index.
    pub fn remove(&mut self, idx: usize) -> Result<Clause, FilterError> {
        if idx >= self.clauses.len() { return Err(FilterError::OutOfRange(idx)); }
        Ok(self.clauses.remove(idx))
    }

    /// Move clause at `from` to `to`.
    pub fn move_clause(&mut self, from: usize, to: usize) -> Result<(), FilterError> {
        if from >= self.clauses.len() { return Err(FilterError::OutOfRange(from)); }
        if to > self.clauses.len() { return Err(FilterError::OutOfRange(to)); }
        let c = self.clauses.remove(from);
        let to_adj = if to > from { to - 1 } else { to };
        self.clauses.insert(to_adj, c);
        Ok(())
    }

    /// Set combinator.
    pub fn set_combinator(&mut self, c: Combinator) { self.combinator = c; }

    /// Set negated.
    pub fn set_negated(&mut self, n: bool) { self.negated = n; }

    /// Render text form.
    pub fn render_query(&self) -> String {
        if self.clauses.is_empty() {
            return if self.negated { "NOT ()".into() } else { "()".into() };
        }
        let joiner = match self.combinator { Combinator::And => " AND ", Combinator::Or => " OR " };
        let body: String = self.clauses.iter()
            .map(|c| format!("{}{}{}", c.field, c.op.symbol(), c.value))
            .collect::<Vec<_>>()
            .join(joiner);
        let wrapped = format!("({body})");
        if self.negated { format!("NOT {wrapped}") } else { wrapped }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FilterError> {
        if self.schema_version != SCHEMA_VERSION { return Err(FilterError::SchemaMismatch); }
        for c in &self.clauses {
            if c.field.is_empty() { return Err(FilterError::EmptyField); }
            if c.value.is_empty() { return Err(FilterError::EmptyValue); }
        }
        Ok(())
    }
}

impl Default for FilterBuilder {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_empty() {
        let f = FilterBuilder::new();
        assert_eq!(f.render_query(), "()");
    }

    #[test]
    fn render_single_eq() {
        let mut f = FilterBuilder::new();
        f.push("status", Op::Eq, "open").unwrap();
        assert_eq!(f.render_query(), "(status:open)");
    }

    #[test]
    fn render_multiple_and() {
        let mut f = FilterBuilder::new();
        f.push("status", Op::Eq, "open").unwrap();
        f.push("priority", Op::Gte, "5").unwrap();
        assert_eq!(f.render_query(), "(status:open AND priority:>=5)");
    }

    #[test]
    fn render_or_negated() {
        let mut f = FilterBuilder::new();
        f.push("status", Op::Eq, "open").unwrap();
        f.push("status", Op::Eq, "blocked").unwrap();
        f.set_combinator(Combinator::Or);
        f.set_negated(true);
        assert_eq!(f.render_query(), "NOT (status:open OR status:blocked)");
    }

    #[test]
    fn remove_clause() {
        let mut f = FilterBuilder::new();
        f.push("a", Op::Eq, "1").unwrap();
        f.push("b", Op::Eq, "2").unwrap();
        let c = f.remove(0).unwrap();
        assert_eq!(c.field, "a");
        assert_eq!(f.clauses.len(), 1);
    }

    #[test]
    fn move_clause_forward() {
        let mut f = FilterBuilder::new();
        f.push("a", Op::Eq, "1").unwrap();
        f.push("b", Op::Eq, "2").unwrap();
        f.push("c", Op::Eq, "3").unwrap();
        // Move 0 → end.
        f.move_clause(0, 3).unwrap();
        let fields: Vec<&String> = f.clauses.iter().map(|c| &c.field).collect();
        assert_eq!(fields, vec![&"b".to_string(), &"c".to_string(), &"a".to_string()]);
    }

    #[test]
    fn move_clause_backward() {
        let mut f = FilterBuilder::new();
        f.push("a", Op::Eq, "1").unwrap();
        f.push("b", Op::Eq, "2").unwrap();
        f.move_clause(1, 0).unwrap();
        assert_eq!(f.clauses[0].field, "b");
    }

    #[test]
    fn out_of_range_rejected() {
        let mut f = FilterBuilder::new();
        assert!(matches!(f.remove(0).unwrap_err(), FilterError::OutOfRange(_)));
    }

    #[test]
    fn op_symbols() {
        assert_eq!(Op::Eq.symbol(), ":");
        assert_eq!(Op::Gte.symbol(), ":>=");
        assert_eq!(Op::Contains.symbol(), ":~");
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = FilterBuilder::new();
        assert!(matches!(f.push("", Op::Eq, "x").unwrap_err(), FilterError::EmptyField));
        assert!(matches!(f.push("f", Op::Eq, "").unwrap_err(), FilterError::EmptyValue));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = FilterBuilder::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(f.validate().unwrap_err(), FilterError::SchemaMismatch));
    }

    #[test]
    fn filter_serde_roundtrip() {
        let mut f = FilterBuilder::new();
        f.push("status", Op::Eq, "open").unwrap();
        f.set_combinator(Combinator::Or);
        let j = serde_json::to_string(&f).unwrap();
        let back: FilterBuilder = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
