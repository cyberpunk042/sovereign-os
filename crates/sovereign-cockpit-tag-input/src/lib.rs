//! `sovereign-cockpit-tag-input` — tag-input widget state.
//!
//! Operator types into `buffer`. Enter / Tab / Comma commits a tag.
//! Backspace on empty buffer pops the last tag. Tag length, total
//! count, and casing rules enforced. Pure UX descriptor.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Default per-tag max chars.
pub const DEFAULT_MAX_TAG_LEN: usize = 32;

/// Default max number of tags.
pub const DEFAULT_MAX_TAGS: usize = 32;

/// Casing rule for committed tags.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CasingRule {
    /// As typed.
    Preserve,
    /// Lowercased.
    Lower,
    /// Uppercased.
    Upper,
}

/// Key event.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TagKey {
    /// Commit current buffer as a tag.
    Commit,
    /// Backspace.
    Backspace,
}

/// Outcome of an action.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum TagOutcome {
    /// Tag added.
    Added(String),
    /// Tag dropped.
    Removed(String),
    /// Tag rejected (duplicate, too long, full, empty).
    Rejected(String),
    /// No-op.
    Noop,
}

/// Tag-input state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TagInput {
    /// Schema version.
    pub schema_version: String,
    /// Already-committed tags in display order.
    pub tags: Vec<String>,
    /// Current edit buffer.
    pub buffer: String,
    /// Max per-tag length (chars).
    pub max_tag_len: u32,
    /// Max total tags.
    pub max_tags: u32,
    /// Casing rule.
    pub casing: CasingRule,
}

/// Errors.
#[derive(Debug, Error)]
pub enum TagInputError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// max_tag_len zero.
    #[error("max_tag_len is zero")]
    MaxLenZero,
    /// max_tags zero.
    #[error("max_tags is zero")]
    MaxTagsZero,
    /// Duplicate tag found in initial set.
    #[error("duplicate tag: {0}")]
    DuplicateTag(String),
    /// Tag too long in initial set.
    #[error("tag {0:?} length {1} > {2}")]
    TagTooLong(String, usize, u32),
}

impl TagInput {
    /// New empty input with supplied limits + casing.
    pub fn new(max_tag_len: u32, max_tags: u32, casing: CasingRule) -> Result<Self, TagInputError> {
        if max_tag_len == 0 {
            return Err(TagInputError::MaxLenZero);
        }
        if max_tags == 0 {
            return Err(TagInputError::MaxTagsZero);
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            tags: Vec::new(),
            buffer: String::new(),
            max_tag_len,
            max_tags,
            casing,
        })
    }

    /// New canonical (DEFAULT_MAX_*).
    pub fn canonical() -> Self {
        Self::new(
            DEFAULT_MAX_TAG_LEN as u32,
            DEFAULT_MAX_TAGS as u32,
            CasingRule::Lower,
        )
        .unwrap()
    }

    /// Append text to buffer.
    pub fn type_text(&mut self, s: &str) {
        self.buffer.push_str(s);
    }

    /// Apply key.
    pub fn key(&mut self, k: TagKey) -> TagOutcome {
        match k {
            TagKey::Commit => self.commit_buffer(),
            TagKey::Backspace => {
                if self.buffer.is_empty() {
                    if let Some(t) = self.tags.pop() {
                        TagOutcome::Removed(t)
                    } else {
                        TagOutcome::Noop
                    }
                } else {
                    self.buffer.pop();
                    TagOutcome::Noop
                }
            }
        }
    }

    fn commit_buffer(&mut self) -> TagOutcome {
        let raw = std::mem::take(&mut self.buffer);
        let trimmed = raw.trim();
        if trimmed.is_empty() {
            return TagOutcome::Rejected(raw);
        }
        let cased = match self.casing {
            CasingRule::Preserve => trimmed.to_string(),
            CasingRule::Lower => trimmed.to_lowercase(),
            CasingRule::Upper => trimmed.to_uppercase(),
        };
        let n = cased.chars().count();
        if n > self.max_tag_len as usize {
            return TagOutcome::Rejected(cased);
        }
        if self.tags.iter().any(|t| t == &cased) {
            return TagOutcome::Rejected(cased);
        }
        if self.tags.len() >= self.max_tags as usize {
            return TagOutcome::Rejected(cased);
        }
        self.tags.push(cased.clone());
        TagOutcome::Added(cased)
    }

    /// Remove a tag by exact match.
    pub fn remove(&mut self, tag: &str) -> bool {
        let pre = self.tags.len();
        self.tags.retain(|t| t != tag);
        self.tags.len() != pre
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), TagInputError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(TagInputError::SchemaMismatch);
        }
        if self.max_tag_len == 0 {
            return Err(TagInputError::MaxLenZero);
        }
        if self.max_tags == 0 {
            return Err(TagInputError::MaxTagsZero);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for t in &self.tags {
            let n = t.chars().count();
            if n > self.max_tag_len as usize {
                return Err(TagInputError::TagTooLong(t.clone(), n, self.max_tag_len));
            }
            if !seen.insert(t.as_str()) {
                return Err(TagInputError::DuplicateTag(t.clone()));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_zero_limits_rejected() {
        assert!(matches!(
            TagInput::new(0, 1, CasingRule::Lower).unwrap_err(),
            TagInputError::MaxLenZero
        ));
        assert!(matches!(
            TagInput::new(1, 0, CasingRule::Lower).unwrap_err(),
            TagInputError::MaxTagsZero
        ));
    }

    #[test]
    fn type_and_commit() {
        let mut t = TagInput::canonical();
        t.type_text("rust");
        assert!(matches!(t.key(TagKey::Commit), TagOutcome::Added(_)));
        assert_eq!(t.tags, vec!["rust"]);
        assert!(t.buffer.is_empty());
    }

    #[test]
    fn case_lower() {
        let mut t = TagInput::canonical();
        t.type_text("RUST");
        t.key(TagKey::Commit);
        assert_eq!(t.tags, vec!["rust"]);
    }

    #[test]
    fn case_upper() {
        let mut t = TagInput::new(10, 5, CasingRule::Upper).unwrap();
        t.type_text("rust");
        t.key(TagKey::Commit);
        assert_eq!(t.tags, vec!["RUST"]);
    }

    #[test]
    fn case_preserve() {
        let mut t = TagInput::new(10, 5, CasingRule::Preserve).unwrap();
        t.type_text("Rust");
        t.key(TagKey::Commit);
        assert_eq!(t.tags, vec!["Rust"]);
    }

    #[test]
    fn duplicate_rejected() {
        let mut t = TagInput::canonical();
        t.type_text("rust");
        t.key(TagKey::Commit);
        t.type_text("rust");
        assert!(matches!(t.key(TagKey::Commit), TagOutcome::Rejected(_)));
        assert_eq!(t.tags.len(), 1);
    }

    #[test]
    fn empty_buffer_commit_rejected() {
        let mut t = TagInput::canonical();
        t.type_text("   ");
        assert!(matches!(t.key(TagKey::Commit), TagOutcome::Rejected(_)));
    }

    #[test]
    fn too_long_rejected() {
        let mut t = TagInput::new(3, 5, CasingRule::Lower).unwrap();
        t.type_text("toolong");
        assert!(matches!(t.key(TagKey::Commit), TagOutcome::Rejected(_)));
    }

    #[test]
    fn max_tags_rejected() {
        let mut t = TagInput::new(10, 2, CasingRule::Lower).unwrap();
        t.type_text("a");
        t.key(TagKey::Commit);
        t.type_text("b");
        t.key(TagKey::Commit);
        t.type_text("c");
        assert!(matches!(t.key(TagKey::Commit), TagOutcome::Rejected(_)));
        assert_eq!(t.tags.len(), 2);
    }

    #[test]
    fn backspace_on_empty_pops_last_tag() {
        let mut t = TagInput::canonical();
        t.type_text("a");
        t.key(TagKey::Commit);
        t.type_text("b");
        t.key(TagKey::Commit);
        let out = t.key(TagKey::Backspace);
        assert!(matches!(out, TagOutcome::Removed(s) if s == "b"));
        assert_eq!(t.tags, vec!["a"]);
    }

    #[test]
    fn backspace_in_buffer_pops_char() {
        let mut t = TagInput::canonical();
        t.type_text("abc");
        t.key(TagKey::Backspace);
        assert_eq!(t.buffer, "ab");
    }

    #[test]
    fn remove_by_value() {
        let mut t = TagInput::canonical();
        t.type_text("a");
        t.key(TagKey::Commit);
        assert!(t.remove("a"));
        assert!(t.tags.is_empty());
        assert!(!t.remove("a"));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = TagInput::canonical();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            TagInputError::SchemaMismatch
        ));
    }

    #[test]
    fn casing_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&CasingRule::Lower).unwrap(),
            "\"lower\""
        );
        assert_eq!(
            serde_json::to_string(&CasingRule::Preserve).unwrap(),
            "\"preserve\""
        );
    }

    #[test]
    fn input_serde_roundtrip() {
        let mut t = TagInput::canonical();
        t.type_text("alpha");
        t.key(TagKey::Commit);
        t.type_text("beta");
        t.key(TagKey::Commit);
        let j = serde_json::to_string(&t).unwrap();
        let back: TagInput = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
