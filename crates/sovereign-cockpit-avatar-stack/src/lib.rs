//! `sovereign-cockpit-avatar-stack` — overlapping avatars.
//!
//! Avatar{id, initials, color}. push appends; render(now)
//! returns the first `max_visible` and overflow count
//! (len - max_visible, 0 if fitting). Initials are uppercased
//! 1..=2 ASCII chars; longer inputs truncated. Pure data.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Avatar.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Avatar {
    /// Id.
    pub id: String,
    /// Initials (1..=2 chars).
    pub initials: String,
    /// Accent color (free-form, e.g. hex).
    pub color: String,
}

/// Render snapshot.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Render<'a> {
    /// Visible avatars.
    pub visible: Vec<&'a Avatar>,
    /// Overflow count (rest beyond max_visible).
    pub overflow: u32,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AvatarStack {
    /// Schema version.
    pub schema_version: String,
    /// Max avatars shown.
    pub max_visible: u32,
    /// Avatars in insertion order.
    pub avatars: Vec<Avatar>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum StackError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("id empty")]
    EmptyId,
    /// Empty.
    #[error("name empty")]
    EmptyName,
    /// Empty.
    #[error("color empty")]
    EmptyColor,
    /// Zero max.
    #[error("max_visible must be >= 1")]
    ZeroMax,
    /// Duplicate.
    #[error("duplicate id: {0}")]
    DuplicateId(String),
}

fn initials_from(name: &str) -> String {
    name.chars()
        .filter(|c| c.is_ascii_alphabetic())
        .take(2)
        .collect::<String>()
        .to_uppercase()
}

impl AvatarStack {
    /// New.
    pub fn new(max_visible: u32) -> Result<Self, StackError> {
        if max_visible == 0 {
            return Err(StackError::ZeroMax);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            max_visible,
            avatars: Vec::new(),
        })
    }

    /// Push avatar (name → initials).
    pub fn push(&mut self, id: &str, name: &str, color: &str) -> Result<(), StackError> {
        if id.is_empty() {
            return Err(StackError::EmptyId);
        }
        if name.is_empty() {
            return Err(StackError::EmptyName);
        }
        if color.is_empty() {
            return Err(StackError::EmptyColor);
        }
        if self.avatars.iter().any(|a| a.id == id) {
            return Err(StackError::DuplicateId(id.into()));
        }
        let initials = initials_from(name);
        let initials = if initials.is_empty() {
            "?".to_string()
        } else {
            initials
        };
        self.avatars.push(Avatar {
            id: id.into(),
            initials,
            color: color.into(),
        });
        Ok(())
    }

    /// Remove by id.
    pub fn remove(&mut self, id: &str) -> bool {
        if let Some(pos) = self.avatars.iter().position(|a| a.id == id) {
            self.avatars.remove(pos);
            true
        } else {
            false
        }
    }

    /// Render snapshot.
    pub fn render(&self) -> Render<'_> {
        let n = self.avatars.len();
        let max = self.max_visible as usize;
        if n <= max {
            Render {
                visible: self.avatars.iter().collect(),
                overflow: 0,
            }
        } else {
            Render {
                visible: self.avatars.iter().take(max).collect(),
                overflow: (n - max) as u32,
            }
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), StackError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(StackError::SchemaMismatch);
        }
        if self.max_visible == 0 {
            return Err(StackError::ZeroMax);
        }
        for a in &self.avatars {
            if a.id.is_empty() {
                return Err(StackError::EmptyId);
            }
            if a.initials.is_empty() {
                return Err(StackError::EmptyName);
            }
            if a.color.is_empty() {
                return Err(StackError::EmptyColor);
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn push_and_initials() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("u1", "Alice", "#fff").unwrap();
        s.push("u2", "Bob Smith", "#000").unwrap();
        assert_eq!(s.avatars[0].initials, "AL");
        assert_eq!(s.avatars[1].initials, "BO");
    }

    #[test]
    fn render_fits_under_max() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("a", "X", "#fff").unwrap();
        s.push("b", "Y", "#fff").unwrap();
        let r = s.render();
        assert_eq!(r.visible.len(), 2);
        assert_eq!(r.overflow, 0);
    }

    #[test]
    fn render_overflows_above_max() {
        let mut s = AvatarStack::new(2).unwrap();
        for c in &["a", "b", "c", "d", "e"] {
            s.push(c, "name", "#fff").unwrap();
        }
        let r = s.render();
        assert_eq!(r.visible.len(), 2);
        assert_eq!(r.overflow, 3);
    }

    #[test]
    fn remove_by_id() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("a", "X", "#fff").unwrap();
        assert!(s.remove("a"));
        assert!(!s.remove("a"));
    }

    #[test]
    fn non_alpha_name_falls_back_to_q() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("a", "123", "#fff").unwrap();
        assert_eq!(s.avatars[0].initials, "?");
    }

    #[test]
    fn duplicate_rejected() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("a", "X", "#fff").unwrap();
        assert!(matches!(
            s.push("a", "Y", "#000").unwrap_err(),
            StackError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut s = AvatarStack::new(3).unwrap();
        assert!(matches!(
            s.push("", "X", "#fff").unwrap_err(),
            StackError::EmptyId
        ));
        assert!(matches!(
            s.push("a", "", "#fff").unwrap_err(),
            StackError::EmptyName
        ));
        assert!(matches!(
            s.push("a", "X", "").unwrap_err(),
            StackError::EmptyColor
        ));
        assert!(matches!(
            AvatarStack::new(0).unwrap_err(),
            StackError::ZeroMax
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = AvatarStack::new(3).unwrap();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            StackError::SchemaMismatch
        ));
    }

    #[test]
    fn stack_serde_roundtrip() {
        let mut s = AvatarStack::new(3).unwrap();
        s.push("a", "X", "#fff").unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: AvatarStack = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
