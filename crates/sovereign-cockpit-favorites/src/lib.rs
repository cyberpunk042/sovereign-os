//! `sovereign-cockpit-favorites` — operator-favorites registry.
//!
//! Per `kind`, an ordered list of `Favorite{id, label, pinned_at}`.
//! `star(kind, fav)` appends; `unstar(kind, id)` removes.
//! `reorder(kind, from, to)` moves within the list.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// One favorite.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Favorite {
    /// Stable id within the kind.
    pub id: String,
    /// Display label.
    pub label: String,
    /// When pinned.
    pub pinned_at_ms: u64,
}

/// State.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Favorites {
    /// Schema version.
    pub schema_version: String,
    /// kind → ordered favorites.
    pub by_kind: BTreeMap<String, Vec<Favorite>>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FavError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty kind.
    #[error("kind empty")]
    EmptyKind,
    /// Empty id.
    #[error("favorite id empty")]
    EmptyId,
    /// Empty label.
    #[error("favorite label empty")]
    EmptyLabel,
    /// Duplicate.
    #[error("duplicate favorite id {0} in kind {1}")]
    Duplicate(String, String),
    /// Out of bounds.
    #[error("index {0} out of bounds (len {1})")]
    OutOfBounds(usize, usize),
}

impl Favorites {
    /// New.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            by_kind: BTreeMap::new(),
        }
    }

    /// Star.
    pub fn star(&mut self, kind: &str, fav: Favorite) -> Result<(), FavError> {
        if kind.is_empty() {
            return Err(FavError::EmptyKind);
        }
        if fav.id.is_empty() {
            return Err(FavError::EmptyId);
        }
        if fav.label.is_empty() {
            return Err(FavError::EmptyLabel);
        }
        let v = self.by_kind.entry(kind.into()).or_default();
        if v.iter().any(|f| f.id == fav.id) {
            return Err(FavError::Duplicate(fav.id, kind.into()));
        }
        v.push(fav);
        Ok(())
    }

    /// Unstar.
    pub fn unstar(&mut self, kind: &str, id: &str) -> bool {
        if let Some(v) = self.by_kind.get_mut(kind)
            && let Some(pos) = v.iter().position(|f| f.id == id)
        {
            v.remove(pos);
            if v.is_empty() {
                self.by_kind.remove(kind);
            }
            return true;
        }
        false
    }

    /// Reorder.
    pub fn reorder(&mut self, kind: &str, from: usize, to: usize) -> Result<(), FavError> {
        let v = self.by_kind.get_mut(kind).ok_or(FavError::EmptyKind)?;
        if from >= v.len() {
            return Err(FavError::OutOfBounds(from, v.len()));
        }
        let item = v.remove(from);
        let pos = to.min(v.len());
        v.insert(pos, item);
        Ok(())
    }

    /// List a kind.
    pub fn list_kind(&self, kind: &str) -> Vec<Favorite> {
        self.by_kind.get(kind).cloned().unwrap_or_default()
    }

    /// Is starred?
    pub fn is_starred(&self, kind: &str, id: &str) -> bool {
        self.by_kind
            .get(kind)
            .is_some_and(|v| v.iter().any(|f| f.id == id))
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FavError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FavError::SchemaMismatch);
        }
        for (k, v) in &self.by_kind {
            if k.is_empty() {
                return Err(FavError::EmptyKind);
            }
            use std::collections::HashSet;
            let mut seen: HashSet<&str> = HashSet::new();
            for f in v {
                if f.id.is_empty() {
                    return Err(FavError::EmptyId);
                }
                if f.label.is_empty() {
                    return Err(FavError::EmptyLabel);
                }
                if !seen.insert(f.id.as_str()) {
                    return Err(FavError::Duplicate(f.id.clone(), k.clone()));
                }
            }
        }
        Ok(())
    }
}

impl Default for Favorites {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fav(id: &str) -> Favorite {
        Favorite {
            id: id.into(),
            label: id.into(),
            pinned_at_ms: 0,
        }
    }

    #[test]
    fn star_and_list() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        f.star("dashboard", fav("b")).unwrap();
        assert_eq!(f.list_kind("dashboard").len(), 2);
    }

    #[test]
    fn unstar_returns_true() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        assert!(f.unstar("dashboard", "a"));
        assert!(!f.unstar("dashboard", "a"));
    }

    #[test]
    fn duplicate_rejected() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        assert!(matches!(
            f.star("dashboard", fav("a")).unwrap_err(),
            FavError::Duplicate(_, _)
        ));
    }

    #[test]
    fn reorder_moves() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        f.star("dashboard", fav("b")).unwrap();
        f.star("dashboard", fav("c")).unwrap();
        f.reorder("dashboard", 0, 2).unwrap();
        let ids: Vec<_> = f.list_kind("dashboard").into_iter().map(|x| x.id).collect();
        assert_eq!(ids, vec!["b", "c", "a"]);
    }

    #[test]
    fn reorder_clamps() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        f.star("dashboard", fav("b")).unwrap();
        f.reorder("dashboard", 0, 99).unwrap();
        let ids: Vec<_> = f.list_kind("dashboard").into_iter().map(|x| x.id).collect();
        assert_eq!(ids, vec!["b", "a"]);
    }

    #[test]
    fn reorder_oob_rejected() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        assert!(matches!(
            f.reorder("dashboard", 9, 0).unwrap_err(),
            FavError::OutOfBounds(_, _)
        ));
    }

    #[test]
    fn is_starred() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        assert!(f.is_starred("dashboard", "a"));
        assert!(!f.is_starred("dashboard", "b"));
    }

    #[test]
    fn empty_inputs_rejected() {
        let mut f = Favorites::new();
        assert!(matches!(
            f.star("", fav("a")).unwrap_err(),
            FavError::EmptyKind
        ));
        let mut bad = fav("a");
        bad.id = "".into();
        assert!(matches!(
            f.star("dashboard", bad).unwrap_err(),
            FavError::EmptyId
        ));
        let mut bad2 = fav("a");
        bad2.label = "".into();
        assert!(matches!(
            f.star("dashboard", bad2).unwrap_err(),
            FavError::EmptyLabel
        ));
    }

    #[test]
    fn schema_drift_rejected() {
        let mut f = Favorites::new();
        f.schema_version = "9.9.9".into();
        assert!(matches!(
            f.validate().unwrap_err(),
            FavError::SchemaMismatch
        ));
    }

    #[test]
    fn favorites_serde_roundtrip() {
        let mut f = Favorites::new();
        f.star("dashboard", fav("a")).unwrap();
        let j = serde_json::to_string(&f).unwrap();
        let back: Favorites = serde_json::from_str(&j).unwrap();
        assert_eq!(f, back);
    }
}
