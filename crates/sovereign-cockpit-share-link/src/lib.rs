//! `sovereign-cockpit-share-link` — operator share URLs.
//!
//! Each `ShareLink` carries (id, target_id, kind, expires_at,
//! recipient_tag). Pure UX wrapper — the IPS authority actually
//! enforces access; this crate manages the cockpit-side state.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 share kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ShareKind {
    /// Conversation excerpt.
    Conversation,
    /// Dashboard snapshot.
    DashboardSnapshot,
    /// Replay session.
    Replay,
    /// Single turn.
    Turn,
}

/// One share link.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShareLink {
    /// Stable id.
    pub id: String,
    /// Target id (thread_id / dashboard slot / replay session id).
    pub target_id: String,
    /// Kind.
    pub kind: ShareKind,
    /// ISO-8601 UTC when link expires.
    pub expires_at: String,
    /// Optional recipient tag.
    pub recipient_tag: String,
    /// ISO-8601 UTC when link was created.
    pub created_at: String,
}

/// Share link registry.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShareLinkRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Active share links.
    pub links: Vec<ShareLink>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ShareError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("share id empty")]
    EmptyId,
    /// Empty target_id.
    #[error("link {0} target_id empty")]
    EmptyTargetId(String),
    /// Empty created_at / expires_at.
    #[error("link {0} timestamp missing")]
    MissingTimestamp(String),
    /// expires_at <= created_at.
    #[error("link {id} expires_at {expires_at} <= created_at {created_at}")]
    BadWindow {
        /// id.
        id: String,
        /// created_at.
        created_at: String,
        /// expires_at.
        expires_at: String,
    },
    /// Duplicate id.
    #[error("duplicate share id: {0}")]
    DuplicateId(String),
}

impl ShareLinkRegistry {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            links: Vec::new(),
        }
    }

    /// Add a link.
    pub fn add(&mut self, link: ShareLink) -> Result<(), ShareError> {
        check_shape(&link)?;
        if self.links.iter().any(|l| l.id == link.id) {
            return Err(ShareError::DuplicateId(link.id));
        }
        self.links.push(link);
        Ok(())
    }

    /// Remove (revoke) a link.
    pub fn revoke(&mut self, id: &str) -> bool {
        let n = self.links.len();
        self.links.retain(|l| l.id != id);
        self.links.len() < n
    }

    /// Lookup.
    pub fn get(&self, id: &str) -> Option<&ShareLink> {
        self.links.iter().find(|l| l.id == id)
    }

    /// Active links (not yet expired) at `now_iso`.
    pub fn active_at(&self, now_iso: &str) -> Vec<&ShareLink> {
        self.links
            .iter()
            .filter(|l| l.expires_at.as_str() > now_iso)
            .collect()
    }

    /// Prune expired entries at `now_iso`.
    pub fn prune_expired(&mut self, now_iso: &str) {
        self.links.retain(|l| l.expires_at.as_str() > now_iso);
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ShareError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ShareError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for l in &self.links {
            check_shape(l)?;
            if !seen.insert(l.id.as_str()) {
                return Err(ShareError::DuplicateId(l.id.clone()));
            }
        }
        Ok(())
    }
}

fn check_shape(l: &ShareLink) -> Result<(), ShareError> {
    if l.id.is_empty() {
        return Err(ShareError::EmptyId);
    }
    if l.target_id.is_empty() {
        return Err(ShareError::EmptyTargetId(l.id.clone()));
    }
    if l.created_at.is_empty() || l.expires_at.is_empty() {
        return Err(ShareError::MissingTimestamp(l.id.clone()));
    }
    if l.expires_at <= l.created_at {
        return Err(ShareError::BadWindow {
            id: l.id.clone(),
            created_at: l.created_at.clone(),
            expires_at: l.expires_at.clone(),
        });
    }
    Ok(())
}

impl Default for ShareLinkRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn link(id: &str, kind: ShareKind, expires: &str) -> ShareLink {
        ShareLink {
            id: id.into(),
            target_id: format!("target-{id}"),
            kind,
            expires_at: expires.into(),
            recipient_tag: "colleague".into(),
            created_at: "2026-05-19T00:00:00Z".into(),
        }
    }

    #[test]
    fn empty_registry_validates() {
        ShareLinkRegistry::new().validate().unwrap();
    }

    #[test]
    fn add_and_lookup() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        assert!(r.get("a").is_some());
    }

    #[test]
    fn duplicate_rejected() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        assert!(matches!(
            r.add(link("a", ShareKind::Replay, "2026-05-21T00:00:00Z"))
                .unwrap_err(),
            ShareError::DuplicateId(_)
        ));
    }

    #[test]
    fn revoke_removes() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        assert!(r.revoke("a"));
        assert!(r.links.is_empty());
        assert!(!r.revoke("a"));
    }

    #[test]
    fn active_at_filters_by_expiry() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        r.add(link("b", ShareKind::Replay, "2026-05-25T00:00:00Z"))
            .unwrap();
        let v = r.active_at("2026-05-22T00:00:00Z");
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].id, "b");
    }

    #[test]
    fn prune_expired_drops() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        r.prune_expired("2026-05-30T00:00:00Z");
        assert!(r.links.is_empty());
    }

    #[test]
    fn bad_window_rejected() {
        let mut r = ShareLinkRegistry::new();
        let l = link("a", ShareKind::Conversation, "2026-05-18T00:00:00Z"); // before created_at
        assert!(matches!(
            r.add(l).unwrap_err(),
            ShareError::BadWindow { .. }
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut r = ShareLinkRegistry::new();
        let l = link("", ShareKind::Conversation, "2026-05-20T00:00:00Z");
        assert!(matches!(r.add(l).unwrap_err(), ShareError::EmptyId));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = ShareLinkRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            ShareError::SchemaMismatch
        ));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&ShareKind::Conversation).unwrap(),
            "\"conversation\""
        );
        assert_eq!(
            serde_json::to_string(&ShareKind::DashboardSnapshot).unwrap(),
            "\"dashboard-snapshot\""
        );
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = ShareLinkRegistry::new();
        r.add(link("a", ShareKind::Conversation, "2026-05-20T00:00:00Z"))
            .unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: ShareLinkRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
