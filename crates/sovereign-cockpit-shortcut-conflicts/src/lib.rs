//! `sovereign-cockpit-shortcut-conflicts` — chord-conflict detector.
//!
//! Each Binding is (chord, scope, command). Conflicts arise when two
//! bindings share a chord within the same effective scope (Global
//! shadows PaneFocused which shadows InputFocused). detect_conflicts()
//! returns the typed conflict list for the settings UI.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Scope.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Scope {
    /// Global — active anywhere.
    Global,
    /// Pane-focused.
    PaneFocused,
    /// Input-focused.
    InputFocused,
}

/// One binding.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Binding {
    /// Stable id.
    pub id: String,
    /// Chord text (canonicalized — e.g., "ctrl+shift+k").
    pub chord: String,
    /// Scope.
    pub scope: Scope,
    /// Command id.
    pub command: String,
}

/// Conflict.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Conflict {
    /// Duplicate within same scope (two commands fighting).
    Duplicate {
        /// chord.
        chord: String,
        /// scope.
        scope: Scope,
        /// involved binding ids.
        binding_ids: Vec<String>,
    },
    /// Global shadow — Global chord hides a more-specific scope's chord.
    Shadow {
        /// chord.
        chord: String,
        /// global binding.
        global_id: String,
        /// shadowed binding.
        shadowed_id: String,
        /// shadowed scope.
        shadowed_scope: Scope,
    },
}

/// Errors.
#[derive(Debug, Error)]
pub enum ShortcutError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty id.
    #[error("binding id empty")]
    EmptyId,
    /// Empty chord.
    #[error("binding {0} chord empty")]
    EmptyChord(String),
    /// Empty command.
    #[error("binding {0} command empty")]
    EmptyCommand(String),
    /// Duplicate binding id.
    #[error("duplicate binding id: {0}")]
    DuplicateId(String),
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ShortcutMap {
    /// Schema version.
    pub schema_version: String,
    /// Bindings.
    pub bindings: Vec<Binding>,
}

impl ShortcutMap {
    /// New.
    pub fn new(bindings: Vec<Binding>) -> Result<Self, ShortcutError> {
        check_bindings(&bindings)?;
        Ok(Self {
            schema_version: SCHEMA_VERSION.into(),
            bindings,
        })
    }

    /// Detect conflicts (duplicate-in-scope + global-shadows-others).
    pub fn detect_conflicts(&self) -> Vec<Conflict> {
        let mut out: Vec<Conflict> = Vec::new();
        use std::collections::HashMap;
        // Group by (chord, scope).
        let mut buckets: HashMap<(String, Scope), Vec<&Binding>> = HashMap::new();
        for b in &self.bindings {
            buckets
                .entry((b.chord.clone(), b.scope))
                .or_default()
                .push(b);
        }
        let mut bucket_keys: Vec<(String, Scope)> = buckets.keys().cloned().collect();
        bucket_keys.sort();
        for k in &bucket_keys {
            let v = &buckets[k];
            if v.len() > 1 {
                let mut ids: Vec<String> = v.iter().map(|b| b.id.clone()).collect();
                ids.sort();
                out.push(Conflict::Duplicate {
                    chord: k.0.clone(),
                    scope: k.1,
                    binding_ids: ids,
                });
            }
        }
        // Global shadow: for each Global binding, find any other binding with same chord in a stricter scope.
        for b in &self.bindings {
            if b.scope != Scope::Global {
                continue;
            }
            for other in &self.bindings {
                if other.id == b.id {
                    continue;
                }
                if other.chord == b.chord && other.scope != Scope::Global {
                    out.push(Conflict::Shadow {
                        chord: b.chord.clone(),
                        global_id: b.id.clone(),
                        shadowed_id: other.id.clone(),
                        shadowed_scope: other.scope,
                    });
                }
            }
        }
        out
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), ShortcutError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(ShortcutError::SchemaMismatch);
        }
        check_bindings(&self.bindings)
    }
}

fn check_bindings(bs: &[Binding]) -> Result<(), ShortcutError> {
    use std::collections::HashSet;
    let mut seen: HashSet<&str> = HashSet::new();
    for b in bs {
        if b.id.is_empty() {
            return Err(ShortcutError::EmptyId);
        }
        if b.chord.is_empty() {
            return Err(ShortcutError::EmptyChord(b.id.clone()));
        }
        if b.command.is_empty() {
            return Err(ShortcutError::EmptyCommand(b.id.clone()));
        }
        if !seen.insert(b.id.as_str()) {
            return Err(ShortcutError::DuplicateId(b.id.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(id: &str, chord: &str, scope: Scope, cmd: &str) -> Binding {
        Binding {
            id: id.into(),
            chord: chord.into(),
            scope,
            command: cmd.into(),
        }
    }

    #[test]
    fn no_conflict_when_distinct() {
        let m = ShortcutMap::new(vec![
            b("a", "ctrl+a", Scope::Global, "cmd-a"),
            b("b", "ctrl+b", Scope::Global, "cmd-b"),
        ])
        .unwrap();
        assert!(m.detect_conflicts().is_empty());
    }

    #[test]
    fn duplicate_in_scope_detected() {
        let m = ShortcutMap::new(vec![
            b("a", "ctrl+k", Scope::Global, "cmd-a"),
            b("b", "ctrl+k", Scope::Global, "cmd-b"),
        ])
        .unwrap();
        let c = m.detect_conflicts();
        assert_eq!(c.len(), 1);
        assert!(matches!(&c[0], Conflict::Duplicate { binding_ids, .. } if binding_ids.len() == 2));
    }

    #[test]
    fn same_chord_different_scope_not_duplicate_but_shadow_if_global() {
        let m = ShortcutMap::new(vec![
            b("g", "ctrl+k", Scope::Global, "global-cmd"),
            b("p", "ctrl+k", Scope::PaneFocused, "pane-cmd"),
        ])
        .unwrap();
        let c = m.detect_conflicts();
        assert!(c.iter().any(|x| matches!(x, Conflict::Shadow { .. })));
    }

    #[test]
    fn no_shadow_when_no_global() {
        let m = ShortcutMap::new(vec![
            b("a", "ctrl+k", Scope::PaneFocused, "a"),
            b("b", "ctrl+k", Scope::InputFocused, "b"),
        ])
        .unwrap();
        assert!(m.detect_conflicts().is_empty());
    }

    #[test]
    fn multi_duplicate_grouped() {
        let m = ShortcutMap::new(vec![
            b("a", "ctrl+k", Scope::Global, "a"),
            b("b", "ctrl+k", Scope::Global, "b"),
            b("c", "ctrl+k", Scope::Global, "c"),
        ])
        .unwrap();
        let c = m.detect_conflicts();
        let dups: Vec<_> = c
            .iter()
            .filter(|x| matches!(x, Conflict::Duplicate { .. }))
            .collect();
        assert_eq!(dups.len(), 1);
        match dups[0] {
            Conflict::Duplicate { binding_ids, .. } => assert_eq!(binding_ids.len(), 3),
            _ => panic!(),
        }
    }

    #[test]
    fn duplicate_id_rejected() {
        assert!(matches!(
            ShortcutMap::new(vec![
                b("a", "x", Scope::Global, "c"),
                b("a", "y", Scope::Global, "c"),
            ])
            .unwrap_err(),
            ShortcutError::DuplicateId(_)
        ));
    }

    #[test]
    fn empty_id_rejected() {
        let mut bad = b("a", "x", Scope::Global, "c");
        bad.id = String::new();
        assert!(matches!(
            ShortcutMap::new(vec![bad]).unwrap_err(),
            ShortcutError::EmptyId
        ));
    }

    #[test]
    fn empty_chord_rejected() {
        let mut bad = b("a", "x", Scope::Global, "c");
        bad.chord = String::new();
        assert!(matches!(
            ShortcutMap::new(vec![bad]).unwrap_err(),
            ShortcutError::EmptyChord(_)
        ));
    }

    #[test]
    fn empty_command_rejected() {
        let mut bad = b("a", "x", Scope::Global, "c");
        bad.command = String::new();
        assert!(matches!(
            ShortcutMap::new(vec![bad]).unwrap_err(),
            ShortcutError::EmptyCommand(_)
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut m = ShortcutMap::new(vec![b("a", "x", Scope::Global, "c")]).unwrap();
        m.schema_version = "9.9.9".into();
        assert!(matches!(
            m.validate().unwrap_err(),
            ShortcutError::SchemaMismatch
        ));
    }

    #[test]
    fn scope_serde_kebab() {
        assert_eq!(serde_json::to_string(&Scope::Global).unwrap(), "\"global\"");
        assert_eq!(
            serde_json::to_string(&Scope::PaneFocused).unwrap(),
            "\"pane-focused\""
        );
        assert_eq!(
            serde_json::to_string(&Scope::InputFocused).unwrap(),
            "\"input-focused\""
        );
    }

    #[test]
    fn conflict_serde_kebab() {
        let c = Conflict::Duplicate {
            chord: "k".into(),
            scope: Scope::Global,
            binding_ids: vec!["a".into()],
        };
        let j = serde_json::to_string(&c).unwrap();
        assert!(j.contains("\"kind\":\"duplicate\""));
    }

    #[test]
    fn map_serde_roundtrip() {
        let m = ShortcutMap::new(vec![b("a", "x", Scope::Global, "c")]).unwrap();
        let j = serde_json::to_string(&m).unwrap();
        let back: ShortcutMap = serde_json::from_str(&j).unwrap();
        assert_eq!(m, back);
    }
}
