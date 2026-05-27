//! `sovereign-cockpit-emoji-shortcode` — :shortcode: → emoji registry.
//!
//! `register(name, glyph)` adds an entry. `lookup(name)` returns the
//! glyph. `prefix(query)` returns all (name, glyph) entries whose
//! name starts with `query`, sorted by name. `resolve(text)` expands
//! every `:name:` occurrence to its glyph (unknown names left
//! untouched).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EmojiShortcode {
    /// Schema version.
    pub schema_version: String,
    /// name → glyph.
    pub map: BTreeMap<String, String>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum EmojiError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty name.
    #[error("name empty")]
    EmptyName,
    /// Bad name (whitespace, colon).
    #[error("bad name: {0}")]
    BadName(String),
    /// Empty glyph.
    #[error("glyph empty")]
    EmptyGlyph,
}

impl EmojiShortcode {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            map: BTreeMap::new(),
        }
    }

    /// Seed with a small canonical set.
    pub fn canonical() -> Self {
        let mut e = Self::new();
        let pairs = [
            ("smile", "🙂"),
            ("grin", "😀"),
            ("laugh", "😂"),
            ("wink", "😉"),
            ("heart", "❤️"),
            ("thumbsup", "👍"),
            ("thumbsdown", "👎"),
            ("eyes", "👀"),
            ("fire", "🔥"),
            ("rocket", "🚀"),
            ("check", "✅"),
            ("cross", "❌"),
            ("warn", "⚠️"),
        ];
        for (n, g) in pairs {
            e.register(n, g).unwrap();
        }
        e
    }

    /// Register.
    pub fn register(&mut self, name: &str, glyph: &str) -> Result<(), EmojiError> {
        if name.is_empty() {
            return Err(EmojiError::EmptyName);
        }
        if name.chars().any(|c| c.is_whitespace() || c == ':') {
            return Err(EmojiError::BadName(name.into()));
        }
        if glyph.is_empty() {
            return Err(EmojiError::EmptyGlyph);
        }
        self.map.insert(name.into(), glyph.into());
        Ok(())
    }

    /// Lookup.
    pub fn lookup(&self, name: &str) -> Option<&str> {
        self.map.get(name).map(|s| s.as_str())
    }

    /// Prefix lookup.
    pub fn prefix(&self, q: &str) -> Vec<(String, String)> {
        self.map
            .iter()
            .filter(|(k, _)| k.starts_with(q))
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect()
    }

    /// Resolve `:name:` occurrences in `text`.
    pub fn resolve(&self, text: &str) -> String {
        let mut out = String::with_capacity(text.len());
        let bytes = text.as_bytes();
        let mut i = 0;
        while i < bytes.len() {
            if bytes[i] == b':' {
                if let Some(end) = bytes[i + 1..].iter().position(|&b| b == b':') {
                    let name = &text[i + 1..i + 1 + end];
                    if !name.is_empty()
                        && !name.chars().any(|c| c.is_whitespace())
                        && let Some(glyph) = self.lookup(name)
                    {
                        out.push_str(glyph);
                        i += end + 2;
                        continue;
                    }
                }
            }
            // Push UTF-8-safe one char at a time.
            let ch = text[i..].chars().next().unwrap();
            out.push(ch);
            i += ch.len_utf8();
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), EmojiError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(EmojiError::SchemaMismatch);
        }
        for (k, v) in &self.map {
            if k.is_empty() {
                return Err(EmojiError::EmptyName);
            }
            if k.chars().any(|c| c.is_whitespace() || c == ':') {
                return Err(EmojiError::BadName(k.clone()));
            }
            if v.is_empty() {
                return Err(EmojiError::EmptyGlyph);
            }
        }
        Ok(())
    }
}

impl Default for EmojiShortcode {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_validates() {
        EmojiShortcode::canonical().validate().unwrap();
    }

    #[test]
    fn register_and_lookup() {
        let mut e = EmojiShortcode::new();
        e.register("foo", "🦀").unwrap();
        assert_eq!(e.lookup("foo"), Some("🦀"));
        assert_eq!(e.lookup("bar"), None);
    }

    #[test]
    fn prefix_sorted() {
        let mut e = EmojiShortcode::new();
        e.register("smile", "🙂").unwrap();
        e.register("smirk", "😏").unwrap();
        e.register("hello", "👋").unwrap();
        let r = e.prefix("sm");
        assert_eq!(
            r.iter().map(|(k, _)| k.as_str()).collect::<Vec<_>>(),
            vec!["smile", "smirk"]
        );
    }

    #[test]
    fn resolve_expands_known() {
        let e = EmojiShortcode::canonical();
        let r = e.resolve("ship it :rocket: with :fire:!");
        assert_eq!(r, "ship it 🚀 with 🔥!");
    }

    #[test]
    fn resolve_leaves_unknown() {
        let e = EmojiShortcode::canonical();
        let r = e.resolve("hey :notfound: there");
        assert_eq!(r, "hey :notfound: there");
    }

    #[test]
    fn resolve_keeps_lonely_colons() {
        let e = EmojiShortcode::canonical();
        let r = e.resolve("ratio 5:1");
        assert_eq!(r, "ratio 5:1");
    }

    #[test]
    fn whitespace_in_name_rejected() {
        let mut e = EmojiShortcode::new();
        assert!(matches!(
            e.register("a b", "x").unwrap_err(),
            EmojiError::BadName(_)
        ));
    }

    #[test]
    fn colon_in_name_rejected() {
        let mut e = EmojiShortcode::new();
        assert!(matches!(
            e.register("a:b", "x").unwrap_err(),
            EmojiError::BadName(_)
        ));
    }

    #[test]
    fn empty_glyph_rejected() {
        let mut e = EmojiShortcode::new();
        assert!(matches!(
            e.register("a", "").unwrap_err(),
            EmojiError::EmptyGlyph
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut e = EmojiShortcode::new();
        e.schema_version = "9.9.9".into();
        assert!(matches!(
            e.validate().unwrap_err(),
            EmojiError::SchemaMismatch
        ));
    }

    #[test]
    fn emoji_serde_roundtrip() {
        let e = EmojiShortcode::canonical();
        let j = serde_json::to_string(&e).unwrap();
        let back: EmojiShortcode = serde_json::from_str(&j).unwrap();
        assert_eq!(e, back);
    }
}
