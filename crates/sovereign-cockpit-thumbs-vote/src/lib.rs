//! `sovereign-cockpit-thumbs-vote` — up/down votes.
//!
//! Per item, store per-user `Vote` (Up/Down). `cast(item, user, vote)`
//! upserts; toggling the same vote clears it. `tally(item)` returns
//! `Tally { up, down, net = up - down }`.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Vote.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Vote {
    /// Up.
    Up,
    /// Down.
    Down,
}

/// Per-item per-user store.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct ItemVotes {
    /// user → vote.
    pub by_user: BTreeMap<String, Vote>,
}

/// Tally.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Tally {
    /// Up.
    pub up: u64,
    /// Down.
    pub down: u64,
    /// Net (up - down, signed).
    pub net: i64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ThumbsVote {
    /// Schema version.
    pub schema_version: String,
    /// item → votes.
    pub items: BTreeMap<String, ItemVotes>,
}

/// Cast verdict.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum CastVerdict {
    /// First vote.
    Added,
    /// Switched (different vote).
    Switched,
    /// Cleared (same vote toggled off).
    Cleared,
}

/// Errors.
#[derive(Debug, Error)]
pub enum VoteError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("item empty")]
    EmptyItem,
    /// Empty.
    #[error("user empty")]
    EmptyUser,
}

impl ThumbsVote {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            items: BTreeMap::new(),
        }
    }

    /// Cast.
    pub fn cast(&mut self, item: &str, user: &str, vote: Vote) -> Result<CastVerdict, VoteError> {
        if item.is_empty() {
            return Err(VoteError::EmptyItem);
        }
        if user.is_empty() {
            return Err(VoteError::EmptyUser);
        }
        let it = self.items.entry(item.into()).or_default();
        let prev = it.by_user.get(user).copied();
        let verdict = match prev {
            None => {
                it.by_user.insert(user.into(), vote);
                CastVerdict::Added
            }
            Some(p) if p == vote => {
                it.by_user.remove(user);
                CastVerdict::Cleared
            }
            Some(_) => {
                it.by_user.insert(user.into(), vote);
                CastVerdict::Switched
            }
        };
        if it.by_user.is_empty() {
            self.items.remove(item);
        }
        Ok(verdict)
    }

    /// Get a user's vote.
    pub fn user_vote(&self, item: &str, user: &str) -> Option<Vote> {
        self.items
            .get(item)
            .and_then(|it| it.by_user.get(user))
            .copied()
    }

    /// Tally.
    pub fn tally(&self, item: &str) -> Tally {
        let Some(it) = self.items.get(item) else {
            return Tally::default();
        };
        let mut up = 0u64;
        let mut down = 0u64;
        for v in it.by_user.values() {
            match v {
                Vote::Up => up = up.saturating_add(1),
                Vote::Down => down = down.saturating_add(1),
            }
        }
        Tally {
            up,
            down,
            net: up as i64 - down as i64,
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), VoteError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(VoteError::SchemaMismatch);
        }
        for (i, it) in &self.items {
            if i.is_empty() {
                return Err(VoteError::EmptyItem);
            }
            for u in it.by_user.keys() {
                if u.is_empty() {
                    return Err(VoteError::EmptyUser);
                }
            }
        }
        Ok(())
    }
}

impl Default for ThumbsVote {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_vote_added() {
        let mut v = ThumbsVote::new();
        assert_eq!(v.cast("a", "alice", Vote::Up).unwrap(), CastVerdict::Added);
        assert_eq!(v.tally("a").up, 1);
    }

    #[test]
    fn same_vote_clears() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        assert_eq!(
            v.cast("a", "alice", Vote::Up).unwrap(),
            CastVerdict::Cleared
        );
        assert_eq!(v.tally("a").up, 0);
    }

    #[test]
    fn different_vote_switches() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        assert_eq!(
            v.cast("a", "alice", Vote::Down).unwrap(),
            CastVerdict::Switched
        );
        assert_eq!(v.tally("a").up, 0);
        assert_eq!(v.tally("a").down, 1);
    }

    #[test]
    fn multiple_users() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        v.cast("a", "bob", Vote::Up).unwrap();
        v.cast("a", "carol", Vote::Down).unwrap();
        let t = v.tally("a");
        assert_eq!(t.up, 2);
        assert_eq!(t.down, 1);
        assert_eq!(t.net, 1);
    }

    #[test]
    fn user_vote_lookup() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        assert_eq!(v.user_vote("a", "alice"), Some(Vote::Up));
        assert!(v.user_vote("a", "bob").is_none());
    }

    #[test]
    fn auto_tidy_empty_item() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        v.cast("a", "alice", Vote::Up).unwrap(); // clears
        assert!(!v.items.contains_key("a"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut v = ThumbsVote::new();
        assert!(matches!(
            v.cast("", "u", Vote::Up).unwrap_err(),
            VoteError::EmptyItem
        ));
        assert!(matches!(
            v.cast("i", "", Vote::Up).unwrap_err(),
            VoteError::EmptyUser
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut v = ThumbsVote::new();
        v.schema_version = "9.9.9".into();
        assert!(matches!(
            v.validate().unwrap_err(),
            VoteError::SchemaMismatch
        ));
    }

    #[test]
    fn vote_serde_roundtrip() {
        let mut v = ThumbsVote::new();
        v.cast("a", "alice", Vote::Up).unwrap();
        let j = serde_json::to_string(&v).unwrap();
        let back: ThumbsVote = serde_json::from_str(&j).unwrap();
        assert_eq!(v, back);
    }
}
