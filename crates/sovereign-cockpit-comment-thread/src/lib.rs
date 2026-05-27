//! `sovereign-cockpit-comment-thread` — threaded comments.
//!
//! Comment{id, author, body, posted_at, in_reply_to, resolved}.
//! add validates parent exists when in_reply_to is set. resolve
//! marks resolved. outline returns tree-ordered list (depth-first
//! by post time).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One comment.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Comment {
    /// Stable id.
    pub id: String,
    /// Author handle.
    pub author: String,
    /// Body text.
    pub body: String,
    /// Posted at.
    pub posted_at_ms: u64,
    /// Parent comment id (None = top-level).
    pub in_reply_to: Option<String>,
    /// Resolved?
    pub resolved: bool,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CommentThread {
    /// Schema version.
    pub schema_version: String,
    /// id → comment.
    pub comments: BTreeMap<String, Comment>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum CommentError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("comment id empty")]
    EmptyId,
    /// Empty author.
    #[error("author empty")]
    EmptyAuthor,
    /// Empty body.
    #[error("body empty")]
    EmptyBody,
    /// Duplicate.
    #[error("duplicate comment id: {0}")]
    Duplicate(String),
    /// Parent missing.
    #[error("parent comment missing: {0}")]
    ParentMissing(String),
    /// Self-reply.
    #[error("self-reply not allowed")]
    SelfReply,
    /// Unknown.
    #[error("unknown comment: {0}")]
    Unknown(String),
}

impl CommentThread {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            comments: BTreeMap::new(),
        }
    }

    /// Add a comment.
    pub fn add(&mut self, c: Comment) -> Result<(), CommentError> {
        if c.id.is_empty() {
            return Err(CommentError::EmptyId);
        }
        if c.author.is_empty() {
            return Err(CommentError::EmptyAuthor);
        }
        if c.body.is_empty() {
            return Err(CommentError::EmptyBody);
        }
        if self.comments.contains_key(&c.id) {
            return Err(CommentError::Duplicate(c.id));
        }
        if let Some(parent) = &c.in_reply_to {
            if *parent == c.id {
                return Err(CommentError::SelfReply);
            }
            if !self.comments.contains_key(parent) {
                return Err(CommentError::ParentMissing(parent.clone()));
            }
        }
        self.comments.insert(c.id.clone(), c);
        Ok(())
    }

    /// Resolve.
    pub fn resolve(&mut self, id: &str) -> Result<(), CommentError> {
        let c = self
            .comments
            .get_mut(id)
            .ok_or_else(|| CommentError::Unknown(id.into()))?;
        c.resolved = true;
        Ok(())
    }

    /// Tree-ordered outline (depth-first by posted_at).
    pub fn outline(&self) -> Vec<Comment> {
        // Top-level (no parent), sorted by posted_at.
        let mut top: Vec<&Comment> = self
            .comments
            .values()
            .filter(|c| c.in_reply_to.is_none())
            .collect();
        top.sort_by_key(|c| c.posted_at_ms);
        let mut out = Vec::with_capacity(self.comments.len());
        for c in top {
            self.walk_subtree(c, &mut out);
        }
        out
    }

    fn walk_subtree(&self, c: &Comment, out: &mut Vec<Comment>) {
        out.push(c.clone());
        let mut children: Vec<&Comment> = self
            .comments
            .values()
            .filter(|x| x.in_reply_to.as_deref() == Some(c.id.as_str()))
            .collect();
        children.sort_by_key(|x| x.posted_at_ms);
        for child in children {
            self.walk_subtree(child, out);
        }
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), CommentError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(CommentError::SchemaMismatch);
        }
        for c in self.comments.values() {
            if c.id.is_empty() {
                return Err(CommentError::EmptyId);
            }
            if c.author.is_empty() {
                return Err(CommentError::EmptyAuthor);
            }
            if c.body.is_empty() {
                return Err(CommentError::EmptyBody);
            }
            if let Some(p) = &c.in_reply_to {
                if !self.comments.contains_key(p) {
                    return Err(CommentError::ParentMissing(p.clone()));
                }
            }
        }
        Ok(())
    }
}

impl Default for CommentThread {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn comment(id: &str, parent: Option<&str>, ts: u64) -> Comment {
        Comment {
            id: id.into(),
            author: "alice".into(),
            body: format!("Body {id}"),
            posted_at_ms: ts,
            in_reply_to: parent.map(|s| s.into()),
            resolved: false,
        }
    }

    #[test]
    fn add_top_level() {
        let mut t = CommentThread::new();
        t.add(comment("c1", None, 0)).unwrap();
        assert_eq!(t.outline().len(), 1);
    }

    #[test]
    fn parent_must_exist() {
        let mut t = CommentThread::new();
        assert!(matches!(
            t.add(comment("c2", Some("missing"), 0)).unwrap_err(),
            CommentError::ParentMissing(_)
        ));
    }

    #[test]
    fn outline_depth_first() {
        let mut t = CommentThread::new();
        t.add(comment("a", None, 0)).unwrap();
        t.add(comment("b", None, 10)).unwrap();
        t.add(comment("a-reply", Some("a"), 5)).unwrap();
        let ids: Vec<_> = t.outline().into_iter().map(|c| c.id).collect();
        // a then a's child a-reply, then b.
        assert_eq!(ids, vec!["a", "a-reply", "b"]);
    }

    #[test]
    fn self_reply_rejected() {
        let mut t = CommentThread::new();
        assert!(matches!(
            t.add(comment("c1", Some("c1"), 0)).unwrap_err(),
            CommentError::SelfReply
        ));
    }

    #[test]
    fn resolve_marks() {
        let mut t = CommentThread::new();
        t.add(comment("c1", None, 0)).unwrap();
        t.resolve("c1").unwrap();
        assert!(t.comments["c1"].resolved);
    }

    #[test]
    fn duplicate_rejected() {
        let mut t = CommentThread::new();
        t.add(comment("c1", None, 0)).unwrap();
        assert!(matches!(
            t.add(comment("c1", None, 1)).unwrap_err(),
            CommentError::Duplicate(_)
        ));
    }

    #[test]
    fn empty_fields_rejected() {
        let mut t = CommentThread::new();
        let mut bad = comment("c1", None, 0);
        bad.author = "".into();
        assert!(matches!(t.add(bad).unwrap_err(), CommentError::EmptyAuthor));
        let mut bad2 = comment("c1", None, 0);
        bad2.body = "".into();
        assert!(matches!(t.add(bad2).unwrap_err(), CommentError::EmptyBody));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut t = CommentThread::new();
        t.schema_version = "9.9.9".into();
        assert!(matches!(
            t.validate().unwrap_err(),
            CommentError::SchemaMismatch
        ));
    }

    #[test]
    fn thread_serde_roundtrip() {
        let mut t = CommentThread::new();
        t.add(comment("c1", None, 0)).unwrap();
        let j = serde_json::to_string(&t).unwrap();
        let back: CommentThread = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
    }
}
