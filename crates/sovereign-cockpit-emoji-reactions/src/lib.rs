//! `sovereign-cockpit-emoji-reactions` — per-message emoji reactions.
//!
//! For each message id, the cockpit tracks reactions keyed by emoji
//! shortcode. Each reaction is a set of user ids who reacted. The
//! count is the set size. `toggle(message, emoji, user)` flips the
//! user's reaction:
//!   * `Added` if user wasn't in the set.
//!   * `Removed` if user was.
//!
//! `counts(message)` returns reactions in descending count order,
//! ties broken by emoji name. `users(message, emoji)` lists reactors
//! in stable (sorted) order.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Per-message reactions.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct MessageReactions {
    /// emoji → set of user ids.
    pub by_emoji: BTreeMap<String, BTreeSet<String>>,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmojiReactions {
    /// Schema version.
    pub schema_version: String,
    /// message id → reactions.
    pub messages: BTreeMap<String, MessageReactions>,
}

/// Toggle verdict.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ToggleVerdict {
    /// Added.
    Added,
    /// Removed.
    Removed,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ReactionError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty message id.
    #[error("message id empty")]
    EmptyMessage,
    /// Empty emoji.
    #[error("emoji empty")]
    EmptyEmoji,
    /// Empty user id.
    #[error("user id empty")]
    EmptyUser,
}

impl EmojiReactions {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            messages: BTreeMap::new(),
        }
    }

    /// Toggle.
    pub fn toggle(&mut self, message_id: &str, emoji: &str, user_id: &str) -> Result<ToggleVerdict, ReactionError> {
        if message_id.is_empty() { return Err(ReactionError::EmptyMessage); }
        if emoji.is_empty() { return Err(ReactionError::EmptyEmoji); }
        if user_id.is_empty() { return Err(ReactionError::EmptyUser); }
        let m = self.messages.entry(message_id.into()).or_default();
        let set = m.by_emoji.entry(emoji.into()).or_default();
        let verdict = if set.contains(user_id) {
            set.remove(user_id);
            ToggleVerdict::Removed
        } else {
            set.insert(user_id.into());
            ToggleVerdict::Added
        };
        // Tidy: if the set is now empty, drop the entry.
        if set.is_empty() {
            m.by_emoji.remove(emoji);
        }
        // If the message has no reactions left, drop it.
        if m.by_emoji.is_empty() {
            self.messages.remove(message_id);
        }
        Ok(verdict)
    }

    /// Has this user reacted?
    pub fn has_reacted(&self, message_id: &str, emoji: &str, user_id: &str) -> bool {
        self.messages.get(message_id)
            .and_then(|m| m.by_emoji.get(emoji))
            .is_some_and(|s| s.contains(user_id))
    }

    /// Counts, sorted descending then alphabetical.
    pub fn counts(&self, message_id: &str) -> Vec<(String, u64)> {
        let Some(m) = self.messages.get(message_id) else { return Vec::new(); };
        let mut v: Vec<(String, u64)> = m.by_emoji.iter().map(|(k, s)| (k.clone(), s.len() as u64)).collect();
        v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        v
    }

    /// Users who reacted with this emoji.
    pub fn users(&self, message_id: &str, emoji: &str) -> Vec<String> {
        self.messages.get(message_id)
            .and_then(|m| m.by_emoji.get(emoji))
            .map(|s| s.iter().cloned().collect())
            .unwrap_or_default()
    }

    /// Drop all reactions on a message (e.g. message deleted).
    pub fn clear(&mut self, message_id: &str) -> bool {
        self.messages.remove(message_id).is_some()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ReactionError> {
        if self.schema_version != SCHEMA_VERSION { return Err(ReactionError::SchemaMismatch); }
        for (mid, m) in &self.messages {
            if mid.is_empty() { return Err(ReactionError::EmptyMessage); }
            for (e, set) in &m.by_emoji {
                if e.is_empty() { return Err(ReactionError::EmptyEmoji); }
                for u in set {
                    if u.is_empty() { return Err(ReactionError::EmptyUser); }
                }
            }
        }
        Ok(())
    }
}

impl Default for EmojiReactions {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_then_remove() {
        let mut r = EmojiReactions::new();
        assert_eq!(r.toggle("m1", "thumbsup", "alice").unwrap(), ToggleVerdict::Added);
        assert!(r.has_reacted("m1", "thumbsup", "alice"));
        assert_eq!(r.toggle("m1", "thumbsup", "alice").unwrap(), ToggleVerdict::Removed);
        assert!(!r.has_reacted("m1", "thumbsup", "alice"));
    }

    #[test]
    fn counts_descending_with_alpha_tiebreak() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "z", "u1").unwrap();
        r.toggle("m1", "a", "u1").unwrap();
        r.toggle("m1", "a", "u2").unwrap();
        let c = r.counts("m1");
        assert_eq!(c[0], ("a".into(), 2));
        assert_eq!(c[1], ("z".into(), 1));
    }

    #[test]
    fn counts_tied_are_alphabetical() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "b", "u1").unwrap();
        r.toggle("m1", "a", "u1").unwrap();
        let c = r.counts("m1");
        assert_eq!(c[0].0, "a");
        assert_eq!(c[1].0, "b");
    }

    #[test]
    fn users_sorted() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "thumbsup", "carol").unwrap();
        r.toggle("m1", "thumbsup", "alice").unwrap();
        r.toggle("m1", "thumbsup", "bob").unwrap();
        let u = r.users("m1", "thumbsup");
        assert_eq!(u, vec!["alice", "bob", "carol"]);
    }

    #[test]
    fn empty_emoji_removed() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "x", "alice").unwrap();
        r.toggle("m1", "x", "alice").unwrap();
        // Empty — message should have been dropped.
        assert!(r.counts("m1").is_empty());
    }

    #[test]
    fn clear_drops_message() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "x", "alice").unwrap();
        assert!(r.clear("m1"));
        assert!(r.counts("m1").is_empty());
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut r = EmojiReactions::new();
        assert!(matches!(r.toggle("", "e", "u").unwrap_err(), ReactionError::EmptyMessage));
        assert!(matches!(r.toggle("m", "", "u").unwrap_err(), ReactionError::EmptyEmoji));
        assert!(matches!(r.toggle("m", "e", "").unwrap_err(), ReactionError::EmptyUser));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = EmojiReactions::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(r.validate().unwrap_err(), ReactionError::SchemaMismatch));
    }

    #[test]
    fn reactions_serde_roundtrip() {
        let mut r = EmojiReactions::new();
        r.toggle("m1", "thumbsup", "alice").unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: EmojiReactions = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
