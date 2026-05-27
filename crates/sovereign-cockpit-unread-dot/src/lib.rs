//! `sovereign-cockpit-unread-dot` — per-channel unread indicator.
//!
//! Channel{count, last_seen_ts_ms, mention}. observe(ts, mention)
//! increments count and remembers whether any unread carries a
//! @mention. mark_seen(ts) sets last_seen and zeroes count. Dot
//! shape: hide if count==0, otherwise show as Mention (red) when
//! any unread mention, else Numeric (subtle).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Channel.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct Channel {
    /// Unread count.
    pub count: u64,
    /// Last-seen ts ms.
    pub last_seen_ts_ms: u64,
    /// Any of the unread is a @mention.
    pub mention: bool,
}

/// Dot variant.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Dot {
    /// Hidden.
    Hidden,
    /// Numeric count (subtle).
    Numeric,
    /// Mention badge (red).
    Mention,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct UnreadDot {
    /// Schema version.
    pub schema_version: String,
    /// channel_id → channel.
    pub channels: BTreeMap<String, Channel>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum UnreadError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("channel id empty")]
    EmptyId,
}

impl UnreadDot {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            channels: BTreeMap::new(),
        }
    }

    /// Observe a new unread message.
    pub fn observe(&mut self, channel_id: &str, mention: bool) -> Result<(), UnreadError> {
        if channel_id.is_empty() {
            return Err(UnreadError::EmptyId);
        }
        let c = self.channels.entry(channel_id.into()).or_default();
        c.count = c.count.saturating_add(1);
        if mention {
            c.mention = true;
        }
        Ok(())
    }

    /// Mark as seen up to ts.
    pub fn mark_seen(&mut self, channel_id: &str, ts_ms: u64) -> Result<(), UnreadError> {
        if channel_id.is_empty() {
            return Err(UnreadError::EmptyId);
        }
        let c = self.channels.entry(channel_id.into()).or_default();
        c.count = 0;
        c.mention = false;
        c.last_seen_ts_ms = ts_ms;
        Ok(())
    }

    /// Dot for a channel.
    pub fn dot(&self, channel_id: &str) -> Dot {
        let c = match self.channels.get(channel_id) {
            Some(c) => c,
            None => return Dot::Hidden,
        };
        if c.count == 0 {
            return Dot::Hidden;
        }
        if c.mention {
            return Dot::Mention;
        }
        Dot::Numeric
    }

    /// Total unread across all channels.
    pub fn total_unread(&self) -> u64 {
        self.channels.values().map(|c| c.count).sum()
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), UnreadError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(UnreadError::SchemaMismatch);
        }
        for k in self.channels.keys() {
            if k.is_empty() {
                return Err(UnreadError::EmptyId);
            }
        }
        Ok(())
    }
}

impl Default for UnreadDot {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_channel_hidden() {
        let u = UnreadDot::new();
        assert_eq!(u.dot("any"), Dot::Hidden);
    }

    #[test]
    fn observe_shows_numeric() {
        let mut u = UnreadDot::new();
        u.observe("c1", false).unwrap();
        u.observe("c1", false).unwrap();
        assert_eq!(u.dot("c1"), Dot::Numeric);
        assert_eq!(u.channels.get("c1").unwrap().count, 2);
    }

    #[test]
    fn mention_promotes_to_mention_dot() {
        let mut u = UnreadDot::new();
        u.observe("c1", false).unwrap();
        u.observe("c1", true).unwrap();
        assert_eq!(u.dot("c1"), Dot::Mention);
    }

    #[test]
    fn mark_seen_clears() {
        let mut u = UnreadDot::new();
        u.observe("c1", true).unwrap();
        u.mark_seen("c1", 100).unwrap();
        assert_eq!(u.dot("c1"), Dot::Hidden);
        assert_eq!(u.channels.get("c1").unwrap().last_seen_ts_ms, 100);
    }

    #[test]
    fn total_unread_sums() {
        let mut u = UnreadDot::new();
        u.observe("a", false).unwrap();
        u.observe("a", false).unwrap();
        u.observe("b", false).unwrap();
        assert_eq!(u.total_unread(), 3);
    }

    #[test]
    fn empty_id_rejected() {
        let mut u = UnreadDot::new();
        assert!(matches!(
            u.observe("", false).unwrap_err(),
            UnreadError::EmptyId
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut u = UnreadDot::new();
        u.schema_version = "9.9.9".into();
        assert!(matches!(
            u.validate().unwrap_err(),
            UnreadError::SchemaMismatch
        ));
    }

    #[test]
    fn unread_serde_roundtrip() {
        let mut u = UnreadDot::new();
        u.observe("c1", true).unwrap();
        let j = serde_json::to_string(&u).unwrap();
        let back: UnreadDot = serde_json::from_str(&j).unwrap();
        assert_eq!(u, back);
    }
}
