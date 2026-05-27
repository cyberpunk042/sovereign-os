//! `sovereign-cockpit-kanban-board` — column-based card flow.
//!
//! A board is a sequence of `Column { id, label, wip_limit }`.
//! Cards live in exactly one column at a time. `add_column(...)`
//! appends; `add_card(...)` places the card in the first column.
//! `move_card(card, target)` enforces the target column's WIP limit
//! and returns:
//!   * `Moved { from, to }`
//!   * `RejectedAtWipLimit { column, in_column, limit }`
//!   * `UnknownCard` / `UnknownColumn`
//!
//! `cards_in(column)` returns cards in the column in arrival order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One column.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Column {
    /// Id.
    pub id: String,
    /// Label.
    pub label: String,
    /// WIP limit (0 = unlimited).
    pub wip_limit: u32,
}

/// One card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Card {
    /// Id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Current column.
    pub column: String,
    /// Move count.
    pub moves: u64,
    /// Last moved ts.
    pub last_moved_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KanbanBoard {
    /// Schema version.
    pub schema_version: String,
    /// Columns in display order.
    pub columns: Vec<Column>,
    /// card_id → card.
    pub cards: BTreeMap<String, Card>,
}

/// Move verdict.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum MoveVerdict {
    /// Moved.
    Moved {
        /// from.
        from: String,
        /// to.
        to: String,
    },
    /// At WIP limit.
    RejectedAtWipLimit {
        /// column.
        column: String,
        /// in-column count.
        in_column: u32,
        /// limit.
        limit: u32,
    },
    /// Unknown card.
    UnknownCard,
    /// Unknown target column.
    UnknownColumn,
}

/// Errors.
#[derive(Debug, Error)]
pub enum KanbanError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("id empty")]
    EmptyId,
    /// Empty label.
    #[error("label empty")]
    EmptyLabel,
    /// Duplicate column.
    #[error("duplicate column id: {0}")]
    DuplicateColumn(String),
    /// Duplicate card.
    #[error("duplicate card id: {0}")]
    DuplicateCard(String),
    /// No columns defined.
    #[error("board has no columns")]
    NoColumns,
}

impl KanbanBoard {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            columns: Vec::new(),
            cards: BTreeMap::new(),
        }
    }

    /// Append a column.
    pub fn add_column(&mut self, id: &str, label: &str, wip_limit: u32) -> Result<(), KanbanError> {
        if id.is_empty() {
            return Err(KanbanError::EmptyId);
        }
        if label.is_empty() {
            return Err(KanbanError::EmptyLabel);
        }
        if self.columns.iter().any(|c| c.id == id) {
            return Err(KanbanError::DuplicateColumn(id.into()));
        }
        self.columns.push(Column {
            id: id.into(),
            label: label.into(),
            wip_limit,
        });
        Ok(())
    }

    /// Add a card to the first column.
    pub fn add_card(&mut self, id: &str, title: &str, ts_ms: u64) -> Result<(), KanbanError> {
        if id.is_empty() {
            return Err(KanbanError::EmptyId);
        }
        if title.is_empty() {
            return Err(KanbanError::EmptyLabel);
        }
        if self.cards.contains_key(id) {
            return Err(KanbanError::DuplicateCard(id.into()));
        }
        let first = self.columns.first().ok_or(KanbanError::NoColumns)?;
        self.cards.insert(
            id.into(),
            Card {
                id: id.into(),
                title: title.into(),
                column: first.id.clone(),
                moves: 0,
                last_moved_ms: ts_ms,
            },
        );
        Ok(())
    }

    /// Move a card.
    pub fn move_card(&mut self, card_id: &str, target: &str, ts_ms: u64) -> MoveVerdict {
        // Look up column first (immutable borrow on self.columns).
        let Some(col) = self.columns.iter().find(|c| c.id == target).cloned() else {
            return MoveVerdict::UnknownColumn;
        };
        // Look up card (immutable borrow).
        let Some(from) = self.cards.get(card_id).map(|c| c.column.clone()) else {
            return MoveVerdict::UnknownCard;
        };
        if from == target {
            // No-op: still record as a move? We say no — leave state untouched.
            return MoveVerdict::Moved {
                from: target.into(),
                to: target.into(),
            };
        }
        if col.wip_limit > 0 {
            let in_col = self.cards.values().filter(|c| c.column == target).count() as u32;
            if in_col >= col.wip_limit {
                return MoveVerdict::RejectedAtWipLimit {
                    column: target.into(),
                    in_column: in_col,
                    limit: col.wip_limit,
                };
            }
        }
        // All checks passed — mutate.
        let card = self.cards.get_mut(card_id).expect("card existed above");
        card.column = target.into();
        card.moves = card.moves.saturating_add(1);
        card.last_moved_ms = ts_ms;
        MoveVerdict::Moved {
            from,
            to: target.into(),
        }
    }

    /// Cards in a column.
    pub fn cards_in(&self, column: &str) -> Vec<Card> {
        self.cards
            .values()
            .filter(|c| c.column == column)
            .cloned()
            .collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), KanbanError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(KanbanError::SchemaMismatch);
        }
        for c in &self.columns {
            if c.id.is_empty() {
                return Err(KanbanError::EmptyId);
            }
            if c.label.is_empty() {
                return Err(KanbanError::EmptyLabel);
            }
        }
        for (id, card) in &self.cards {
            if id.is_empty() {
                return Err(KanbanError::EmptyId);
            }
            if card.title.is_empty() {
                return Err(KanbanError::EmptyLabel);
            }
        }
        Ok(())
    }
}

impl Default for KanbanBoard {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn board() -> KanbanBoard {
        let mut b = KanbanBoard::new();
        b.add_column("todo", "To Do", 0).unwrap();
        b.add_column("doing", "In Progress", 2).unwrap();
        b.add_column("done", "Done", 0).unwrap();
        b
    }

    #[test]
    fn add_card_goes_to_first_column() {
        let mut b = board();
        b.add_card("c1", "first card", 0).unwrap();
        assert_eq!(b.cards["c1"].column, "todo");
    }

    #[test]
    fn move_card_success() {
        let mut b = board();
        b.add_card("c1", "x", 0).unwrap();
        match b.move_card("c1", "doing", 100) {
            MoveVerdict::Moved { from, to } => {
                assert_eq!(from, "todo");
                assert_eq!(to, "doing");
            }
            _ => panic!(),
        }
        assert_eq!(b.cards["c1"].moves, 1);
    }

    #[test]
    fn wip_limit_rejects() {
        let mut b = board();
        b.add_card("a", "x", 0).unwrap();
        b.add_card("b", "x", 0).unwrap();
        b.add_card("c", "x", 0).unwrap();
        b.move_card("a", "doing", 1).unwrap_move();
        b.move_card("b", "doing", 2).unwrap_move();
        match b.move_card("c", "doing", 3) {
            MoveVerdict::RejectedAtWipLimit {
                column,
                in_column,
                limit,
            } => {
                assert_eq!(column, "doing");
                assert_eq!(in_column, 2);
                assert_eq!(limit, 2);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn unlimited_wip_ok() {
        let mut b = board();
        // todo and done both have wip=0 (unlimited).
        for i in 0..5 {
            b.add_card(&format!("c{i}"), "x", 0).unwrap();
        }
        // All sit in todo; move all to done.
        for i in 0..5 {
            assert!(matches!(
                b.move_card(&format!("c{i}"), "done", 0),
                MoveVerdict::Moved { .. }
            ));
        }
        assert_eq!(b.cards_in("done").len(), 5);
    }

    #[test]
    fn unknown_card_or_column() {
        let mut b = board();
        b.add_card("c1", "x", 0).unwrap();
        assert_eq!(b.move_card("nope", "doing", 0), MoveVerdict::UnknownCard);
        assert_eq!(b.move_card("c1", "nope", 0), MoveVerdict::UnknownColumn);
    }

    #[test]
    fn add_card_without_columns_rejected() {
        let mut b = KanbanBoard::new();
        assert!(matches!(
            b.add_card("c1", "x", 0).unwrap_err(),
            KanbanError::NoColumns
        ));
    }

    #[test]
    fn duplicate_column_rejected() {
        let mut b = board();
        assert!(matches!(
            b.add_column("todo", "X", 0).unwrap_err(),
            KanbanError::DuplicateColumn(_)
        ));
    }

    #[test]
    fn duplicate_card_rejected() {
        let mut b = board();
        b.add_card("c1", "x", 0).unwrap();
        assert!(matches!(
            b.add_card("c1", "x", 0).unwrap_err(),
            KanbanError::DuplicateCard(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = board();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            KanbanError::SchemaMismatch
        ));
    }

    #[test]
    fn kanban_serde_roundtrip() {
        let mut b = board();
        b.add_card("c1", "x", 0).unwrap();
        b.move_card("c1", "doing", 100);
        let j = serde_json::to_string(&b).unwrap();
        let back: KanbanBoard = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }

    // Helper trait used in tests.
    trait UnwrapMove {
        fn unwrap_move(self);
    }
    impl UnwrapMove for MoveVerdict {
        fn unwrap_move(self) {
            match self {
                MoveVerdict::Moved { .. } => {}
                other => panic!("expected Moved, got {other:?}"),
            }
        }
    }
}
