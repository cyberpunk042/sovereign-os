//! `sovereign-cockpit-pin-board` — operator pinboard.
//!
//! Each `PinCard` carries (id, title, kind, body, color, position).
//! Max 50 cards. Pure UX surface.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Max pin cards.
pub const MAX_CARDS: usize = 50;

/// Card kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CardKind {
    /// Free-form note.
    Note,
    /// Web link.
    Link,
    /// Code snippet.
    Snippet,
    /// Image (path or URL).
    Image,
    /// Conversation reference.
    ConvRef,
}

/// Card color.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CardColor {
    /// Yellow.
    Yellow,
    /// Blue.
    Blue,
    /// Green.
    Green,
    /// Red.
    Red,
    /// Pink.
    Pink,
    /// Grey.
    Grey,
}

/// 2D board position (px, can be negative for off-screen).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Position {
    /// x.
    pub x: i32,
    /// y.
    pub y: i32,
}

/// One pin card.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PinCard {
    /// Unique id.
    pub id: String,
    /// Title.
    pub title: String,
    /// Kind.
    pub kind: CardKind,
    /// Body (≤ 2000 chars).
    pub body: String,
    /// Color.
    pub color: CardColor,
    /// Position on board.
    pub position: Position,
}

/// Pin board envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PinBoard {
    /// Schema version.
    pub schema_version: String,
    /// Cards in z-order (last drawn on top).
    pub cards: Vec<PinCard>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum PinBoardError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("card id empty")]
    EmptyId,
    /// Empty title.
    #[error("card {0} title empty")]
    EmptyTitle(String),
    /// Body too long.
    #[error("card {id} body length {len} > 2000")]
    BodyTooLong {
        /// id.
        id: String,
        /// len.
        len: usize,
    },
    /// Duplicate.
    #[error("duplicate card id: {0}")]
    DuplicateId(String),
    /// Board full.
    #[error("board full ({MAX_CARDS} max)")]
    Full,
    /// Unknown id.
    #[error("unknown card id: {0}")]
    Unknown(String),
}

impl PinBoard {
    /// New empty board.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            cards: Vec::new(),
        }
    }

    /// Add a card.
    pub fn add(&mut self, c: PinCard) -> Result<(), PinBoardError> {
        check_shape(&c)?;
        if self.cards.iter().any(|x| x.id == c.id) {
            return Err(PinBoardError::DuplicateId(c.id));
        }
        if self.cards.len() >= MAX_CARDS {
            return Err(PinBoardError::Full);
        }
        self.cards.push(c);
        Ok(())
    }

    /// Remove a card.
    pub fn remove(&mut self, id: &str) -> Result<(), PinBoardError> {
        let pos = self
            .cards
            .iter()
            .position(|c| c.id == id)
            .ok_or_else(|| PinBoardError::Unknown(id.into()))?;
        self.cards.remove(pos);
        Ok(())
    }

    /// Move a card to a new position.
    pub fn move_to(&mut self, id: &str, position: Position) -> Result<(), PinBoardError> {
        let c = self
            .cards
            .iter_mut()
            .find(|c| c.id == id)
            .ok_or_else(|| PinBoardError::Unknown(id.into()))?;
        c.position = position;
        Ok(())
    }

    /// Bring a card to front (z-order top).
    pub fn bring_to_front(&mut self, id: &str) -> Result<(), PinBoardError> {
        let pos = self
            .cards
            .iter()
            .position(|c| c.id == id)
            .ok_or_else(|| PinBoardError::Unknown(id.into()))?;
        let c = self.cards.remove(pos);
        self.cards.push(c);
        Ok(())
    }

    /// Cards filtered by kind.
    pub fn by_kind(&self, kind: CardKind) -> Vec<&PinCard> {
        self.cards.iter().filter(|c| c.kind == kind).collect()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), PinBoardError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(PinBoardError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for c in &self.cards {
            check_shape(c)?;
            if !seen.insert(c.id.as_str()) {
                return Err(PinBoardError::DuplicateId(c.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(c: &PinCard) -> Result<(), PinBoardError> {
    if c.id.is_empty() {
        return Err(PinBoardError::EmptyId);
    }
    if c.title.is_empty() {
        return Err(PinBoardError::EmptyTitle(c.id.clone()));
    }
    let n = c.body.chars().count();
    if n > 2000 {
        return Err(PinBoardError::BodyTooLong {
            id: c.id.clone(),
            len: n,
        });
    }
    Ok(())
}

impl Default for PinBoard {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn card(id: &str, kind: CardKind, color: CardColor) -> PinCard {
        PinCard {
            id: id.into(),
            title: format!("Title for {id}"),
            kind,
            body: String::new(),
            color,
            position: Position { x: 0, y: 0 },
        }
    }

    #[test]
    fn empty_board_validates() {
        PinBoard::new().validate().unwrap();
    }

    #[test]
    fn add_and_lookup() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        assert_eq!(b.cards.len(), 1);
    }

    #[test]
    fn duplicate_rejected() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        assert!(matches!(
            b.add(card("a", CardKind::Link, CardColor::Blue))
                .unwrap_err(),
            PinBoardError::DuplicateId(_)
        ));
    }

    #[test]
    fn max_cards_enforced() {
        let mut b = PinBoard::new();
        for i in 0..MAX_CARDS {
            b.add(card(&format!("c{i}"), CardKind::Note, CardColor::Yellow))
                .unwrap();
        }
        assert!(matches!(
            b.add(card("over", CardKind::Note, CardColor::Yellow))
                .unwrap_err(),
            PinBoardError::Full
        ));
    }

    #[test]
    fn move_updates_position() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        b.move_to("a", Position { x: 100, y: 200 }).unwrap();
        assert_eq!(b.cards[0].position, Position { x: 100, y: 200 });
    }

    #[test]
    fn bring_to_front_changes_z() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        b.add(card("b", CardKind::Note, CardColor::Yellow)).unwrap();
        b.add(card("c", CardKind::Note, CardColor::Yellow)).unwrap();
        b.bring_to_front("a").unwrap();
        assert_eq!(b.cards.last().unwrap().id, "a");
    }

    #[test]
    fn remove_unknown_rejected() {
        let mut b = PinBoard::new();
        assert!(matches!(
            b.remove("none").unwrap_err(),
            PinBoardError::Unknown(_)
        ));
    }

    #[test]
    fn empty_title_rejected() {
        let mut b = PinBoard::new();
        let mut c = card("a", CardKind::Note, CardColor::Yellow);
        c.title = String::new();
        assert!(matches!(
            b.add(c).unwrap_err(),
            PinBoardError::EmptyTitle(_)
        ));
    }

    #[test]
    fn body_too_long_rejected() {
        let mut b = PinBoard::new();
        let mut c = card("a", CardKind::Note, CardColor::Yellow);
        c.body = "x".repeat(2001);
        assert!(matches!(
            b.add(c).unwrap_err(),
            PinBoardError::BodyTooLong { .. }
        ));
    }

    #[test]
    fn by_kind_filters() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        b.add(card("b", CardKind::Link, CardColor::Blue)).unwrap();
        b.add(card("c", CardKind::Note, CardColor::Green)).unwrap();
        assert_eq!(b.by_kind(CardKind::Note).len(), 2);
        assert_eq!(b.by_kind(CardKind::Link).len(), 1);
        assert_eq!(b.by_kind(CardKind::Snippet).len(), 0);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut b = PinBoard::new();
        b.schema_version = "9.9.9".into();
        assert!(matches!(
            b.validate().unwrap_err(),
            PinBoardError::SchemaMismatch
        ));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(serde_json::to_string(&CardKind::Note).unwrap(), "\"note\"");
        assert_eq!(
            serde_json::to_string(&CardKind::ConvRef).unwrap(),
            "\"conv-ref\""
        );
        assert_eq!(
            serde_json::to_string(&CardKind::Snippet).unwrap(),
            "\"snippet\""
        );
    }

    #[test]
    fn board_serde_roundtrip() {
        let mut b = PinBoard::new();
        b.add(card("a", CardKind::Note, CardColor::Yellow)).unwrap();
        let j = serde_json::to_string(&b).unwrap();
        let back: PinBoard = serde_json::from_str(&j).unwrap();
        assert_eq!(b, back);
    }
}
