//! `sovereign-text-edit` — precise find-and-replace editing.
//!
//! A code-editing agent must change *exactly* the right span of a file. The
//! safe model — the one Claude Code's own edit tool uses — is find-and-replace
//! where the `find` text must occur **exactly once**: zero matches means the
//! edit is stale and is rejected; multiple matches means it's ambiguous and is
//! rejected (replacing the wrong one silently corrupts the file). This crate is
//! that model.
//!
//! [`apply`] applies one edit; [`apply_all`] applies a sequence in order
//! (each edit sees the result of the previous). It is the apply side of the
//! `sovereign-line-diff`: line-diff shows what changed, this *makes* the change
//! safely.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the text-edit surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A single find-and-replace edit.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Edit {
    /// The text to find (must occur exactly once).
    pub find: String,
    /// The text to replace it with.
    pub replace: String,
}

impl Edit {
    /// Build an edit.
    pub fn new(find: impl Into<String>, replace: impl Into<String>) -> Self {
        Self {
            find: find.into(),
            replace: replace.into(),
        }
    }
}

/// Why an edit could not be applied.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum EditError {
    /// The `find` text was empty (would match everywhere).
    #[error("empty find string")]
    EmptyFind,
    /// The `find` text did not occur in the input.
    #[error("find not found: {0:?}")]
    NotFound(String),
    /// The `find` text occurred more than once (ambiguous).
    #[error("find is ambiguous: {found} occurrences of {text:?}")]
    Ambiguous {
        /// How many times it occurred.
        found: usize,
        /// The find text.
        text: String,
    },
}

/// Count non-overlapping occurrences of `needle` in `haystack`.
fn count(haystack: &str, needle: &str) -> usize {
    haystack.matches(needle).count()
}

/// Apply one edit to `text`, requiring `edit.find` to occur exactly once.
pub fn apply(text: &str, edit: &Edit) -> Result<String, EditError> {
    if edit.find.is_empty() {
        return Err(EditError::EmptyFind);
    }
    match count(text, &edit.find) {
        0 => Err(EditError::NotFound(edit.find.clone())),
        1 => Ok(text.replacen(&edit.find, &edit.replace, 1)),
        n => Err(EditError::Ambiguous {
            found: n,
            text: edit.find.clone(),
        }),
    }
}

/// Apply a sequence of edits in order; each sees the previous result. Stops and
/// returns the error of the first edit that fails.
pub fn apply_all(text: &str, edits: &[Edit]) -> Result<String, EditError> {
    let mut current = text.to_string();
    for edit in edits {
        current = apply(&current, edit)?;
    }
    Ok(current)
}

/// Whether `edit` could be applied to `text` (exactly one match).
pub fn can_apply(text: &str, edit: &Edit) -> bool {
    !edit.find.is_empty() && count(text, &edit.find) == 1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn applies_a_unique_edit() {
        let out = apply("let x = 1;", &Edit::new("1", "2")).unwrap();
        assert_eq!(out, "let x = 2;");
    }

    #[test]
    fn not_found_is_rejected() {
        assert_eq!(
            apply("hello", &Edit::new("world", "x")).unwrap_err(),
            EditError::NotFound("world".to_string())
        );
    }

    #[test]
    fn ambiguous_match_is_rejected() {
        // "a" occurs twice → ambiguous, do not silently pick one
        assert_eq!(
            apply("banana", &Edit::new("na", "NA")).unwrap_err(),
            EditError::Ambiguous {
                found: 2,
                text: "na".to_string()
            }
        );
    }

    #[test]
    fn empty_find_is_rejected() {
        assert_eq!(
            apply("anything", &Edit::new("", "x")).unwrap_err(),
            EditError::EmptyFind
        );
    }

    #[test]
    fn unique_via_more_context_succeeds() {
        // disambiguate by including surrounding context
        let text = "foo = 1\nbar = 1";
        let out = apply(text, &Edit::new("foo = 1", "foo = 2")).unwrap();
        assert_eq!(out, "foo = 2\nbar = 1");
    }

    #[test]
    fn apply_all_runs_in_order() {
        let edits = [Edit::new("a", "b"), Edit::new("b", "c")];
        // "a" → "b" → then the new "b" → "c"
        assert_eq!(apply_all("xax", &edits).unwrap(), "xcx");
    }

    #[test]
    fn apply_all_stops_on_first_failure() {
        let edits = [Edit::new("x", "y"), Edit::new("zzz", "w")];
        assert_eq!(
            apply_all("x", &edits).unwrap_err(),
            EditError::NotFound("zzz".to_string())
        );
    }

    #[test]
    fn multiline_edits_work() {
        let text = "fn main() {\n    old();\n}\n";
        let out = apply(text, &Edit::new("    old();", "    new();")).unwrap();
        assert!(out.contains("new();") && !out.contains("old();"));
    }

    #[test]
    fn can_apply_predicts_success() {
        assert!(can_apply("abc", &Edit::new("b", "x")));
        assert!(!can_apply("abab", &Edit::new("ab", "x"))); // ambiguous
        assert!(!can_apply("abc", &Edit::new("z", "x"))); // missing
    }

    #[test]
    fn edit_serde_round_trip() {
        let e = Edit::new("from", "to");
        let j = serde_json::to_string(&e).unwrap();
        let back: Edit = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
