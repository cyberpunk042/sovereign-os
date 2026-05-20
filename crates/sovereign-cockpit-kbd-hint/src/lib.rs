//! `sovereign-cockpit-kbd-hint` — inline keyboard-shortcut hint.
//!
//! Hint{action, chord: Vec<Key>}. parse("Ctrl+Shift+K") → chord
//! of three keys. render produces a Vec<Chunk> alternating between
//! KeyCap and Plus separators so the surface can wrap each piece
//! in a <kbd> element. Surface-only; no key-binding logic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A single key in a chord (already canonicalized).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Key(pub String);

/// Hint = action label + chord.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Hint {
    /// Action label (e.g. "Open command palette").
    pub action: String,
    /// Chord (e.g. ["Ctrl", "Shift", "K"]).
    pub chord: Vec<Key>,
}

/// Render chunk.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case", tag = "kind", content = "text")]
pub enum Chunk {
    /// Keycap, wrap in `<kbd>`.
    KeyCap(String),
    /// "+" separator (presentational).
    Plus,
}

/// Errors.
#[derive(Debug, Error)]
pub enum HintError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty.
    #[error("action empty")]
    EmptyAction,
    /// Empty.
    #[error("chord empty")]
    EmptyChord,
    /// Bad key.
    #[error("empty key in chord")]
    EmptyKey,
}

impl Hint {
    /// Build from action + raw chord string.
    pub fn parse(action: &str, chord: &str) -> Result<Self, HintError> {
        if action.is_empty() { return Err(HintError::EmptyAction); }
        let parts: Vec<&str> = chord.split('+').map(|s| s.trim()).collect();
        if parts.is_empty() || parts.iter().all(|s| s.is_empty()) {
            return Err(HintError::EmptyChord);
        }
        let mut keys = Vec::with_capacity(parts.len());
        for p in parts {
            if p.is_empty() { return Err(HintError::EmptyKey); }
            keys.push(Key(canonical(p)));
        }
        Ok(Hint { action: action.into(), chord: keys })
    }

    /// Render chord as Chunk sequence: keycap, plus, keycap, plus, …
    pub fn render(&self) -> Vec<Chunk> {
        let mut out = Vec::with_capacity(self.chord.len() * 2);
        for (i, k) in self.chord.iter().enumerate() {
            if i > 0 { out.push(Chunk::Plus); }
            out.push(Chunk::KeyCap(k.0.clone()));
        }
        out
    }

    /// Display as plain "Ctrl+Shift+K" text.
    pub fn display(&self) -> String {
        self.chord.iter().map(|k| k.0.clone()).collect::<Vec<_>>().join("+")
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HintError> {
        if self.action.is_empty() { return Err(HintError::EmptyAction); }
        if self.chord.is_empty() { return Err(HintError::EmptyChord); }
        for k in &self.chord {
            if k.0.is_empty() { return Err(HintError::EmptyKey); }
        }
        Ok(())
    }
}

fn canonical(k: &str) -> String {
    match k.to_ascii_lowercase().as_str() {
        "ctrl" | "control" => "Ctrl".into(),
        "shift" => "Shift".into(),
        "alt" | "option" | "opt" => "Alt".into(),
        "cmd" | "meta" | "super" | "win" => "Meta".into(),
        "esc" | "escape" => "Esc".into(),
        "enter" | "return" => "Enter".into(),
        "space" | "spacebar" => "Space".into(),
        "tab" => "Tab".into(),
        "backspace" | "bksp" => "Backspace".into(),
        "del" | "delete" => "Delete".into(),
        other => {
            if other.len() == 1 {
                other.to_ascii_uppercase()
            } else {
                // Capitalize ASCII first byte; rest preserved.
                let mut chars = k.chars();
                match chars.next() {
                    None => String::new(),
                    Some(c) => c.to_ascii_uppercase().to_string() + chars.as_str(),
                }
            }
        }
    }
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KbdHint {
    /// Schema version.
    pub schema_version: String,
    /// Hints (in display order).
    pub hints: Vec<Hint>,
}

impl KbdHint {
    /// New.
    pub fn new() -> Self {
        Self { schema_version: SCHEMA_VERSION.into(), hints: Vec::new() }
    }

    /// Add.
    pub fn push(&mut self, h: Hint) -> Result<(), HintError> {
        h.validate()?;
        self.hints.push(h);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), HintError> {
        if self.schema_version != SCHEMA_VERSION { return Err(HintError::SchemaMismatch); }
        for h in &self.hints { h.validate()?; }
        Ok(())
    }
}

impl Default for KbdHint {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_canonicalizes_modifiers() {
        let h = Hint::parse("Open palette", "ctrl+shift+k").unwrap();
        assert_eq!(h.chord, vec![
            Key("Ctrl".into()), Key("Shift".into()), Key("K".into())
        ]);
    }

    #[test]
    fn render_alternates_keycap_plus() {
        let h = Hint::parse("Save", "Ctrl+S").unwrap();
        assert_eq!(h.render(), vec![
            Chunk::KeyCap("Ctrl".into()),
            Chunk::Plus,
            Chunk::KeyCap("S".into()),
        ]);
    }

    #[test]
    fn display_joins_with_plus() {
        let h = Hint::parse("Save", "Ctrl+S").unwrap();
        assert_eq!(h.display(), "Ctrl+S");
    }

    #[test]
    fn single_key_chord() {
        let h = Hint::parse("Cancel", "Escape").unwrap();
        assert_eq!(h.chord, vec![Key("Esc".into())]);
        assert_eq!(h.render(), vec![Chunk::KeyCap("Esc".into())]);
    }

    #[test]
    fn empty_chord_rejected() {
        assert!(matches!(Hint::parse("x", "").unwrap_err(), HintError::EmptyChord));
        assert!(matches!(Hint::parse("x", "Ctrl++K").unwrap_err(), HintError::EmptyKey));
    }

    #[test]
    fn empty_action_rejected() {
        assert!(matches!(Hint::parse("", "Ctrl+K").unwrap_err(), HintError::EmptyAction));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut s = KbdHint::new();
        s.schema_version = "9.9.9".into();
        assert!(matches!(s.validate().unwrap_err(), HintError::SchemaMismatch));
    }

    #[test]
    fn hint_serde_roundtrip() {
        let mut s = KbdHint::new();
        s.push(Hint::parse("Open", "Ctrl+Shift+K").unwrap()).unwrap();
        let j = serde_json::to_string(&s).unwrap();
        let back: KbdHint = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
