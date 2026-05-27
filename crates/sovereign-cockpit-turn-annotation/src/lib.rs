//! `sovereign-cockpit-turn-annotation` — operator notes / highlights / stars on turns.
//!
//! Each `Annotation` carries (thread_id, turn_index, kind, body). Pure
//! display surface — no policy, no authority. The cockpit renders these
//! inline; the replay engine preserves them across sessions.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_conversation_thread::ConversationThread;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// 4 annotation kinds.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AnnotationKind {
    /// Free-form operator note.
    Note,
    /// Highlight (mark turn as significant).
    Highlight,
    /// Star (favourite).
    Star,
    /// Comment thread (operator-to-future-self).
    Comment,
}

/// One annotation.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Annotation {
    /// Thread id.
    pub thread_id: String,
    /// Turn index inside thread.
    pub turn_index: u32,
    /// Kind.
    pub kind: AnnotationKind,
    /// Body text (≤500 chars).
    pub body: String,
    /// Operator MS003 fingerprint (signature-style id, not selfdef authority).
    pub by: String,
    /// ISO-8601 UTC.
    pub at: String,
}

/// Annotation set envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AnnotationSet {
    /// Schema version.
    pub schema_version: String,
    /// Annotations.
    pub annotations: Vec<Annotation>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum AnnotationError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty thread_id.
    #[error("thread_id missing")]
    MissingThreadId,
    /// turn_index out of range.
    #[error("turn_index {idx} >= thread turns {total}")]
    OutOfRange {
        /// idx.
        idx: u32,
        /// total.
        total: u32,
    },
    /// Body too long.
    #[error("annotation body length {0} > 500")]
    BodyTooLong(usize),
    /// Empty by.
    #[error("annotation `by` empty")]
    EmptyBy,
}

impl AnnotationSet {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            annotations: Vec::new(),
        }
    }

    /// Add an annotation. Validates against a thread.
    pub fn add(
        &mut self,
        a: Annotation,
        thread: &ConversationThread,
    ) -> Result<(), AnnotationError> {
        check_shape(&a)?;
        if a.thread_id == thread.thread_id && a.turn_index >= thread.turns.len() as u32 {
            return Err(AnnotationError::OutOfRange {
                idx: a.turn_index,
                total: thread.turns.len() as u32,
            });
        }
        self.annotations.push(a);
        Ok(())
    }

    /// Annotations for one (thread_id, turn_index).
    pub fn for_turn(&self, thread_id: &str, turn_index: u32) -> Vec<&Annotation> {
        self.annotations
            .iter()
            .filter(|a| a.thread_id == thread_id && a.turn_index == turn_index)
            .collect()
    }

    /// Annotations by kind.
    pub fn by_kind(&self, kind: AnnotationKind) -> Vec<&Annotation> {
        self.annotations.iter().filter(|a| a.kind == kind).collect()
    }

    /// Validate the set.
    pub fn validate(&self) -> Result<(), AnnotationError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(AnnotationError::SchemaMismatch);
        }
        for a in &self.annotations {
            check_shape(a)?;
        }
        Ok(())
    }
}

fn check_shape(a: &Annotation) -> Result<(), AnnotationError> {
    if a.thread_id.is_empty() {
        return Err(AnnotationError::MissingThreadId);
    }
    if a.by.is_empty() {
        return Err(AnnotationError::EmptyBy);
    }
    let n = a.body.chars().count();
    if n > 500 {
        return Err(AnnotationError::BodyTooLong(n));
    }
    Ok(())
}

impl Default for AnnotationSet {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_conversation_thread::{Turn, TurnRole};

    fn t3() -> ConversationThread {
        let mut t = ConversationThread::new("th-1", "ts");
        for _ in 0..3 {
            t.append(Turn {
                index: 0,
                role: TurnRole::Operator,
                tokens_in: 0,
                tokens_out: 0,
                provider: "p".into(),
                started_at: "t".into(),
                completed_at: "t".into(),
                branch_id: "main".into(),
                text: String::new(),
            });
        }
        t
    }

    fn a(kind: AnnotationKind, body: &str, turn_index: u32) -> Annotation {
        Annotation {
            thread_id: "th-1".into(),
            turn_index,
            kind,
            body: body.into(),
            by: "op-fp".into(),
            at: "2026-05-19T03:00:00Z".into(),
        }
    }

    #[test]
    fn empty_set_validates() {
        AnnotationSet::new().validate().unwrap();
    }

    #[test]
    fn add_and_retrieve() {
        let mut s = AnnotationSet::new();
        let t = t3();
        s.add(a(AnnotationKind::Note, "first", 0), &t).unwrap();
        s.add(a(AnnotationKind::Star, "fav", 1), &t).unwrap();
        s.add(a(AnnotationKind::Note, "another", 1), &t).unwrap();
        assert_eq!(s.for_turn("th-1", 0).len(), 1);
        assert_eq!(s.for_turn("th-1", 1).len(), 2);
        assert_eq!(s.by_kind(AnnotationKind::Note).len(), 2);
    }

    #[test]
    fn out_of_range_rejected() {
        let mut s = AnnotationSet::new();
        let t = t3();
        let err = s.add(a(AnnotationKind::Note, "x", 99), &t).unwrap_err();
        assert!(matches!(err, AnnotationError::OutOfRange { .. }));
    }

    #[test]
    fn empty_thread_id_rejected() {
        let mut s = AnnotationSet::new();
        let t = t3();
        let mut bad = a(AnnotationKind::Note, "x", 0);
        bad.thread_id = String::new();
        let err = s.add(bad, &t).unwrap_err();
        assert!(matches!(err, AnnotationError::MissingThreadId));
    }

    #[test]
    fn empty_by_rejected() {
        let mut s = AnnotationSet::new();
        let t = t3();
        let mut bad = a(AnnotationKind::Note, "x", 0);
        bad.by = String::new();
        let err = s.add(bad, &t).unwrap_err();
        assert!(matches!(err, AnnotationError::EmptyBy));
    }

    #[test]
    fn body_too_long_rejected() {
        let mut s = AnnotationSet::new();
        let t = t3();
        let long = "x".repeat(501);
        let bad = a(AnnotationKind::Note, &long, 0);
        let err = s.add(bad, &t).unwrap_err();
        assert!(matches!(err, AnnotationError::BodyTooLong(501)));
    }

    #[test]
    fn for_turn_filters_by_thread() {
        let mut s = AnnotationSet::new();
        let t = t3();
        s.add(a(AnnotationKind::Note, "x", 0), &t).unwrap();
        // Push a foreign annotation (manually bypassing thread validation).
        s.annotations.push(Annotation {
            thread_id: "th-other".into(),
            turn_index: 0,
            kind: AnnotationKind::Note,
            body: "x".into(),
            by: "op".into(),
            at: "t".into(),
        });
        assert_eq!(s.for_turn("th-1", 0).len(), 1);
        assert_eq!(s.for_turn("th-other", 0).len(), 1);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = AnnotationSet::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(
            s.validate().unwrap_err(),
            AnnotationError::SchemaMismatch
        ));
    }

    #[test]
    fn kind_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&AnnotationKind::Note).unwrap(),
            "\"note\""
        );
        assert_eq!(
            serde_json::to_string(&AnnotationKind::Highlight).unwrap(),
            "\"highlight\""
        );
        assert_eq!(
            serde_json::to_string(&AnnotationKind::Star).unwrap(),
            "\"star\""
        );
        assert_eq!(
            serde_json::to_string(&AnnotationKind::Comment).unwrap(),
            "\"comment\""
        );
    }

    #[test]
    fn set_serde_roundtrip() {
        let mut s = AnnotationSet::new();
        let t = t3();
        s.add(a(AnnotationKind::Star, "x", 0), &t).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: AnnotationSet = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
