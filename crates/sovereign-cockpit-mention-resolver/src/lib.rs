//! `sovereign-cockpit-mention-resolver` — @mention text segmenter.
//!
//! User{handle, display_name}. resolve(text) walks the text and
//! emits Token::Plain runs interleaved with Token::Mention when
//! "@handle" matches a known user (handle = ASCII alnum + "_",
//! length 1..=64). Unknown "@unknown" segments stay as Plain.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// User.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct User {
    /// Handle (no leading @).
    pub handle: String,
    /// Display name.
    pub display_name: String,
}

/// Token.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind")]
pub enum Token {
    /// Plain text.
    Plain {
        /// text.
        text: String,
    },
    /// Resolved mention.
    Mention {
        /// User handle.
        handle: String,
        /// Display name.
        display_name: String,
    },
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MentionResolver {
    /// Schema version.
    pub schema_version: String,
    /// Known users keyed by handle.
    pub users: BTreeMap<String, User>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum ResolverError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("handle empty")]
    EmptyHandle,
    /// Bad handle.
    #[error("handle must be 1..=64 chars of ASCII alnum + '_'")]
    BadHandle,
}

fn is_handle_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

fn is_valid_handle(h: &str) -> bool {
    !h.is_empty() && h.len() <= 64 && h.chars().all(is_handle_char)
}

impl MentionResolver {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            users: BTreeMap::new(),
        }
    }

    /// Register a user.
    pub fn add_user(&mut self, handle: &str, display_name: &str) -> Result<(), ResolverError> {
        if handle.is_empty() {
            return Err(ResolverError::EmptyHandle);
        }
        if !is_valid_handle(handle) {
            return Err(ResolverError::BadHandle);
        }
        self.users.insert(
            handle.into(),
            User {
                handle: handle.into(),
                display_name: display_name.into(),
            },
        );
        Ok(())
    }

    /// Resolve.
    pub fn resolve(&self, text: &str) -> Vec<Token> {
        let mut out: Vec<Token> = Vec::new();
        let mut buf = String::new();
        let chars: Vec<char> = text.chars().collect();
        let mut i = 0;
        while i < chars.len() {
            if chars[i] == '@' {
                // Walk handle chars.
                let start = i + 1;
                let mut j = start;
                while j < chars.len() && is_handle_char(chars[j]) {
                    j += 1;
                }
                let handle: String = chars[start..j].iter().collect();
                if !handle.is_empty() && self.users.contains_key(&handle) {
                    if !buf.is_empty() {
                        out.push(Token::Plain {
                            text: std::mem::take(&mut buf),
                        });
                    }
                    let u = self.users.get(&handle).unwrap();
                    out.push(Token::Mention {
                        handle: u.handle.clone(),
                        display_name: u.display_name.clone(),
                    });
                    i = j;
                    continue;
                }
                // Not a known handle — copy "@" + chars into buf.
                buf.push('@');
                buf.extend(&chars[start..j]);
                i = j;
            } else {
                buf.push(chars[i]);
                i += 1;
            }
        }
        if !buf.is_empty() {
            out.push(Token::Plain { text: buf });
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ResolverError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ResolverError::SchemaMismatch);
        }
        for h in self.users.keys() {
            if !is_valid_handle(h) {
                return Err(ResolverError::BadHandle);
            }
        }
        Ok(())
    }
}

impl Default for MentionResolver {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn r() -> MentionResolver {
        let mut r = MentionResolver::new();
        r.add_user("alice", "Alice A.").unwrap();
        r.add_user("bob", "Bob B.").unwrap();
        r
    }

    #[test]
    fn resolves_known_handle() {
        let toks = r().resolve("hi @alice!");
        assert_eq!(
            toks,
            vec![
                Token::Plain { text: "hi ".into() },
                Token::Mention {
                    handle: "alice".into(),
                    display_name: "Alice A.".into()
                },
                Token::Plain { text: "!".into() },
            ]
        );
    }

    #[test]
    fn unknown_stays_plain() {
        let toks = r().resolve("hi @unknown!");
        assert_eq!(
            toks,
            vec![Token::Plain {
                text: "hi @unknown!".into()
            }]
        );
    }

    #[test]
    fn multiple_mentions() {
        let toks = r().resolve("@alice and @bob");
        assert_eq!(toks.len(), 3);
        assert!(matches!(toks[0], Token::Mention { .. }));
        assert!(matches!(toks[2], Token::Mention { .. }));
    }

    #[test]
    fn only_plain_no_at() {
        let toks = r().resolve("hello world");
        assert_eq!(
            toks,
            vec![Token::Plain {
                text: "hello world".into()
            }]
        );
    }

    #[test]
    fn at_with_no_handle() {
        let toks = r().resolve("price @ $5");
        assert_eq!(
            toks,
            vec![Token::Plain {
                text: "price @ $5".into()
            }]
        );
    }

    #[test]
    fn bad_handle_rejected() {
        let mut r = MentionResolver::new();
        assert!(matches!(
            r.add_user("", "x").unwrap_err(),
            ResolverError::EmptyHandle
        ));
        assert!(matches!(
            r.add_user("bad handle", "x").unwrap_err(),
            ResolverError::BadHandle
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = MentionResolver::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            ResolverError::SchemaMismatch
        ));
    }

    #[test]
    fn resolver_serde_roundtrip() {
        let r = r();
        let j = serde_json::to_string(&r).unwrap();
        let back: MentionResolver = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
