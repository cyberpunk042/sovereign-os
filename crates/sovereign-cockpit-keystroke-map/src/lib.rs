//! `sovereign-cockpit-keystroke-map` — keyboard shortcut registry.
//!
//! Each `KeyBinding` declares (modifiers, key, action_id, scope,
//! description). The registry rejects any duplicate (scope + chord)
//! pair so two actions can never collide in the same scope.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Modifier set (bitset).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default, Serialize, Deserialize)]
pub struct Modifiers {
    /// Ctrl held.
    pub ctrl: bool,
    /// Shift held.
    pub shift: bool,
    /// Alt held.
    pub alt: bool,
    /// Meta (Cmd/Super) held.
    pub meta: bool,
}

impl Modifiers {
    /// No modifiers.
    pub const NONE: Self = Self {
        ctrl: false,
        shift: false,
        alt: false,
        meta: false,
    };

    /// Builder: Ctrl.
    pub fn ctrl() -> Self {
        Self {
            ctrl: true,
            ..Self::NONE
        }
    }
    /// Add Shift.
    pub fn shift(mut self) -> Self {
        self.shift = true;
        self
    }
    /// Add Alt.
    pub fn alt(mut self) -> Self {
        self.alt = true;
        self
    }
}

/// Scope a binding applies in.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Scope {
    /// Always available.
    Global,
    /// Conversation pane.
    Conversation,
    /// Dashboard view.
    Dashboard,
    /// Replay session.
    Replay,
    /// Command palette open.
    Palette,
}

/// One binding.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyBinding {
    /// Modifiers.
    pub modifiers: Modifiers,
    /// Key (lowercased; "a"-"z", "0"-"9", or named: "enter", "esc", "f1", …).
    pub key: String,
    /// Action id.
    pub action_id: String,
    /// Scope.
    pub scope: Scope,
    /// Human-readable description.
    pub description: String,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeystrokeMap {
    /// Schema version.
    pub schema_version: String,
    /// Bindings.
    pub bindings: Vec<KeyBinding>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum KeystrokeError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty key.
    #[error("binding has empty key")]
    EmptyKey,
    /// Empty action_id.
    #[error("binding has empty action_id")]
    EmptyActionId,
    /// Conflict.
    #[error("conflict in scope {scope:?}: chord {chord} bound to both {a} and {b}")]
    Conflict {
        /// Scope.
        scope: Scope,
        /// Chord render.
        chord: String,
        /// First action.
        a: String,
        /// Second action.
        b: String,
    },
}

fn chord_string(m: Modifiers, key: &str) -> String {
    let mut s = String::new();
    if m.ctrl {
        s.push_str("Ctrl+");
    }
    if m.alt {
        s.push_str("Alt+");
    }
    if m.shift {
        s.push_str("Shift+");
    }
    if m.meta {
        s.push_str("Meta+");
    }
    s.push_str(key);
    s
}

impl KeystrokeMap {
    /// New empty registry.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            bindings: Vec::new(),
        }
    }

    /// Add a binding; rejects conflicts.
    pub fn add(&mut self, b: KeyBinding) -> Result<(), KeystrokeError> {
        if b.key.is_empty() {
            return Err(KeystrokeError::EmptyKey);
        }
        if b.action_id.is_empty() {
            return Err(KeystrokeError::EmptyActionId);
        }
        for existing in &self.bindings {
            if existing.scope == b.scope
                && existing.modifiers == b.modifiers
                && existing.key == b.key
            {
                return Err(KeystrokeError::Conflict {
                    scope: b.scope,
                    chord: chord_string(b.modifiers, &b.key),
                    a: existing.action_id.clone(),
                    b: b.action_id,
                });
            }
        }
        self.bindings.push(b);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), KeystrokeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(KeystrokeError::SchemaMismatch);
        }
        use std::collections::HashMap;
        let mut map: HashMap<(Scope, Modifiers, String), String> = HashMap::new();
        for b in &self.bindings {
            if b.key.is_empty() {
                return Err(KeystrokeError::EmptyKey);
            }
            if b.action_id.is_empty() {
                return Err(KeystrokeError::EmptyActionId);
            }
            let kk = (b.scope, b.modifiers, b.key.clone());
            if let Some(existing) = map.get(&kk) {
                return Err(KeystrokeError::Conflict {
                    scope: b.scope,
                    chord: chord_string(b.modifiers, &b.key),
                    a: existing.clone(),
                    b: b.action_id.clone(),
                });
            }
            map.insert(kk, b.action_id.clone());
        }
        Ok(())
    }

    /// Resolve a keypress to an action id in a given scope.
    pub fn resolve(&self, scope: Scope, modifiers: Modifiers, key: &str) -> Option<&str> {
        // Look in scope; fall back to Global.
        for b in &self.bindings {
            if b.scope == scope && b.modifiers == modifiers && b.key == key {
                return Some(&b.action_id);
            }
        }
        for b in &self.bindings {
            if b.scope == Scope::Global && b.modifiers == modifiers && b.key == key {
                return Some(&b.action_id);
            }
        }
        None
    }
}

impl Default for KeystrokeMap {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(scope: Scope, modifiers: Modifiers, key: &str, action: &str) -> KeyBinding {
        KeyBinding {
            modifiers,
            key: key.into(),
            action_id: action.into(),
            scope,
            description: String::new(),
        }
    }

    #[test]
    fn empty_map_validates() {
        KeystrokeMap::new().validate().unwrap();
    }

    #[test]
    fn add_two_distinct_chords() {
        let mut m = KeystrokeMap::new();
        m.add(b(Scope::Global, Modifiers::ctrl(), "k", "open-palette"))
            .unwrap();
        m.add(b(Scope::Global, Modifiers::ctrl(), "s", "save"))
            .unwrap();
        m.validate().unwrap();
    }

    #[test]
    fn conflict_in_same_scope_rejected() {
        let mut m = KeystrokeMap::new();
        m.add(b(Scope::Global, Modifiers::ctrl(), "k", "a"))
            .unwrap();
        let err = m
            .add(b(Scope::Global, Modifiers::ctrl(), "k", "b"))
            .unwrap_err();
        assert!(matches!(err, KeystrokeError::Conflict { .. }));
    }

    #[test]
    fn same_chord_different_scope_ok() {
        let mut m = KeystrokeMap::new();
        m.add(b(Scope::Conversation, Modifiers::ctrl(), "k", "a"))
            .unwrap();
        m.add(b(Scope::Dashboard, Modifiers::ctrl(), "k", "b"))
            .unwrap();
    }

    #[test]
    fn empty_key_rejected() {
        let mut m = KeystrokeMap::new();
        let err = m
            .add(b(Scope::Global, Modifiers::ctrl(), "", "a"))
            .unwrap_err();
        assert!(matches!(err, KeystrokeError::EmptyKey));
    }

    #[test]
    fn empty_action_rejected() {
        let mut m = KeystrokeMap::new();
        let err = m
            .add(b(Scope::Global, Modifiers::ctrl(), "k", ""))
            .unwrap_err();
        assert!(matches!(err, KeystrokeError::EmptyActionId));
    }

    #[test]
    fn resolve_scope_first_then_global() {
        let mut m = KeystrokeMap::new();
        m.add(b(Scope::Global, Modifiers::ctrl(), "k", "global-action"))
            .unwrap();
        m.add(b(
            Scope::Conversation,
            Modifiers::ctrl(),
            "k",
            "conv-action",
        ))
        .unwrap();
        assert_eq!(
            m.resolve(Scope::Conversation, Modifiers::ctrl(), "k"),
            Some("conv-action")
        );
        assert_eq!(
            m.resolve(Scope::Dashboard, Modifiers::ctrl(), "k"),
            Some("global-action")
        );
    }

    #[test]
    fn resolve_returns_none_for_unbound() {
        let m = KeystrokeMap::new();
        assert_eq!(m.resolve(Scope::Global, Modifiers::ctrl(), "z"), None);
    }

    #[test]
    fn modifiers_builder() {
        let m = Modifiers::ctrl().shift().alt();
        assert!(m.ctrl);
        assert!(m.shift);
        assert!(m.alt);
        assert!(!m.meta);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = KeystrokeMap::new();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            KeystrokeError::SchemaMismatch
        ));
    }

    #[test]
    fn scope_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&Scope::Conversation).unwrap(),
            "\"conversation\""
        );
        assert_eq!(serde_json::to_string(&Scope::Replay).unwrap(), "\"replay\"");
        assert_eq!(
            serde_json::to_string(&Scope::Palette).unwrap(),
            "\"palette\""
        );
    }

    #[test]
    fn map_serde_roundtrip() {
        let mut m = KeystrokeMap::new();
        m.add(b(Scope::Global, Modifiers::ctrl(), "k", "open-palette"))
            .unwrap();
        m.add(b(
            Scope::Conversation,
            Modifiers::ctrl().shift(),
            "enter",
            "submit-and-stay",
        ))
        .unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: KeystrokeMap = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
