//! `sovereign-workspace-folder-registry` — operator-declared workspace roots.
//!
//! Each `Folder` declares (label, root_path, scope, read_only, max_size_gb).
//! The dispatcher refuses any fs-read/write outside the union of declared
//! root paths.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Folder scope.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum FolderScope {
    /// Source code repository.
    Repo,
    /// Document store.
    Docs,
    /// Data / dataset folder.
    Data,
    /// Build artifacts / outputs.
    Build,
    /// Replay traces.
    Replay,
    /// Operator scratch.
    Scratch,
}

/// One folder.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Folder {
    /// Display label (non-empty, unique).
    pub label: String,
    /// Absolute root path (non-empty, starts with '/').
    pub root_path: String,
    /// Scope.
    pub scope: FolderScope,
    /// Read-only.
    pub read_only: bool,
    /// Soft size cap in GB; 0 means unlimited.
    pub max_size_gb: u32,
}

/// Registry envelope.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WorkspaceFolderRegistry {
    /// Schema version.
    pub schema_version: String,
    /// Folders.
    pub folders: Vec<Folder>,
}

/// Errors.
#[derive(Debug, Error)]
pub enum FolderError {
    /// Schema drift.
    #[error("schema version mismatch")]
    SchemaMismatch,
    /// Empty label.
    #[error("folder label empty")]
    EmptyLabel,
    /// Duplicate label.
    #[error("duplicate folder label: {0}")]
    DuplicateLabel(String),
    /// Empty root path.
    #[error("folder {0} root_path empty")]
    EmptyPath(String),
    /// Path not absolute.
    #[error("folder {label} root_path {path} not absolute")]
    NotAbsolute {
        /// label.
        label: String,
        /// path.
        path: String,
    },
    /// One folder's root_path is a prefix of another's (would create ambiguity).
    #[error("folder {a} root_path overlaps with folder {b}")]
    OverlappingRoots {
        /// a.
        a: String,
        /// b.
        b: String,
    },
    /// Path is not under any declared folder.
    #[error("path {0} not under any declared folder")]
    PathOutsideWorkspace(String),
    /// Write blocked by read-only folder.
    #[error("write blocked: folder {0} is read-only")]
    ReadOnlyBlock(String),
}

fn normalize(p: &str) -> String {
    // Drop trailing slash (except root "/").
    if p.len() > 1 && p.ends_with('/') {
        p[..p.len() - 1].to_string()
    } else {
        p.to_string()
    }
}

fn is_under(child: &str, parent: &str) -> bool {
    let c = normalize(child);
    let p = normalize(parent);
    if c == p {
        return true;
    }
    let p_with_sep = format!("{p}/");
    c.starts_with(&p_with_sep)
}

impl WorkspaceFolderRegistry {
    /// New empty.
    pub fn new() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            folders: Vec::new(),
        }
    }

    /// Add a folder.
    pub fn add(&mut self, f: Folder) -> Result<(), FolderError> {
        if f.label.is_empty() {
            return Err(FolderError::EmptyLabel);
        }
        if f.root_path.is_empty() {
            return Err(FolderError::EmptyPath(f.label));
        }
        if !f.root_path.starts_with('/') {
            return Err(FolderError::NotAbsolute {
                label: f.label,
                path: f.root_path,
            });
        }
        let new_root = normalize(&f.root_path);
        for existing in &self.folders {
            if existing.label == f.label {
                return Err(FolderError::DuplicateLabel(f.label));
            }
            let ex_root = normalize(&existing.root_path);
            if is_under(&new_root, &ex_root) || is_under(&ex_root, &new_root) {
                return Err(FolderError::OverlappingRoots {
                    a: existing.label.clone(),
                    b: f.label.clone(),
                });
            }
        }
        self.folders.push(f);
        Ok(())
    }

    /// Validate.
    pub fn validate(&self) -> Result<(), FolderError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(FolderError::SchemaMismatch);
        }
        use std::collections::HashSet;
        let mut seen: HashSet<&str> = HashSet::new();
        for f in &self.folders {
            if f.label.is_empty() {
                return Err(FolderError::EmptyLabel);
            }
            if !seen.insert(f.label.as_str()) {
                return Err(FolderError::DuplicateLabel(f.label.clone()));
            }
            if f.root_path.is_empty() {
                return Err(FolderError::EmptyPath(f.label.clone()));
            }
            if !f.root_path.starts_with('/') {
                return Err(FolderError::NotAbsolute {
                    label: f.label.clone(),
                    path: f.root_path.clone(),
                });
            }
        }
        // Pairwise overlap.
        for i in 0..self.folders.len() {
            for j in (i + 1)..self.folders.len() {
                let a = normalize(&self.folders[i].root_path);
                let b = normalize(&self.folders[j].root_path);
                if is_under(&a, &b) || is_under(&b, &a) {
                    return Err(FolderError::OverlappingRoots {
                        a: self.folders[i].label.clone(),
                        b: self.folders[j].label.clone(),
                    });
                }
            }
        }
        Ok(())
    }

    /// Find the folder that contains a given path, if any.
    pub fn resolve(&self, path: &str) -> Option<&Folder> {
        self.folders.iter().find(|f| is_under(path, &f.root_path))
    }

    /// Refuse write if path is outside any folder or its folder is read-only.
    pub fn require_writable(&self, path: &str) -> Result<&Folder, FolderError> {
        let f = self
            .resolve(path)
            .ok_or_else(|| FolderError::PathOutsideWorkspace(path.into()))?;
        if f.read_only {
            return Err(FolderError::ReadOnlyBlock(f.label.clone()));
        }
        Ok(f)
    }
}

impl Default for WorkspaceFolderRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn f(label: &str, root: &str, scope: FolderScope, ro: bool) -> Folder {
        Folder {
            label: label.into(),
            root_path: root.into(),
            scope,
            read_only: ro,
            max_size_gb: 0,
        }
    }

    #[test]
    fn empty_validates() {
        WorkspaceFolderRegistry::new().validate().unwrap();
    }

    #[test]
    fn add_disjoint_folders() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/workspace/selfdef", FolderScope::Repo, false))
            .unwrap();
        r.add(f("data", "/var/data", FolderScope::Data, false))
            .unwrap();
        r.add(f("scratch", "/tmp/scratch", FolderScope::Scratch, false))
            .unwrap();
        r.validate().unwrap();
    }

    #[test]
    fn duplicate_label_rejected() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/a", FolderScope::Repo, false)).unwrap();
        let err = r
            .add(f("repo", "/b", FolderScope::Repo, false))
            .unwrap_err();
        assert!(matches!(err, FolderError::DuplicateLabel(_)));
    }

    #[test]
    fn non_absolute_rejected() {
        let mut r = WorkspaceFolderRegistry::new();
        let err = r
            .add(f("repo", "relative/path", FolderScope::Repo, false))
            .unwrap_err();
        assert!(matches!(err, FolderError::NotAbsolute { .. }));
    }

    #[test]
    fn overlapping_roots_rejected() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("a", "/workspace", FolderScope::Repo, false))
            .unwrap();
        let err = r
            .add(f("b", "/workspace/sub", FolderScope::Repo, false))
            .unwrap_err();
        assert!(matches!(err, FolderError::OverlappingRoots { .. }));
    }

    #[test]
    fn resolve_finds_containing_folder() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/workspace/selfdef", FolderScope::Repo, false))
            .unwrap();
        let found = r.resolve("/workspace/selfdef/crates/foo.rs").unwrap();
        assert_eq!(found.label, "repo");
    }

    #[test]
    fn resolve_returns_none_for_outside_path() {
        let r = WorkspaceFolderRegistry::new();
        assert!(r.resolve("/etc/passwd").is_none());
    }

    #[test]
    fn require_writable_succeeds_when_writable() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/workspace", FolderScope::Repo, false))
            .unwrap();
        r.require_writable("/workspace/foo.rs").unwrap();
    }

    #[test]
    fn require_writable_blocked_by_read_only() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("docs", "/docs", FolderScope::Docs, true)).unwrap();
        match r.require_writable("/docs/readme.md").unwrap_err() {
            FolderError::ReadOnlyBlock(label) => assert_eq!(label, "docs"),
            other => panic!("unexpected: {other:?}"),
        }
    }

    #[test]
    fn require_writable_outside_workspace() {
        let r = WorkspaceFolderRegistry::new();
        assert!(matches!(
            r.require_writable("/etc/passwd").unwrap_err(),
            FolderError::PathOutsideWorkspace(_)
        ));
    }

    #[test]
    fn root_exactly_at_folder_is_under() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/workspace", FolderScope::Repo, false))
            .unwrap();
        assert!(r.resolve("/workspace").is_some());
    }

    #[test]
    fn schema_drift_rejected() {
        let mut r = WorkspaceFolderRegistry::new();
        r.schema_version = "9.9.9".into();
        assert!(matches!(
            r.validate().unwrap_err(),
            FolderError::SchemaMismatch
        ));
    }

    #[test]
    fn scope_serde_kebab() {
        assert_eq!(
            serde_json::to_string(&FolderScope::Repo).unwrap(),
            "\"repo\""
        );
        assert_eq!(
            serde_json::to_string(&FolderScope::Scratch).unwrap(),
            "\"scratch\""
        );
    }

    #[test]
    fn registry_serde_roundtrip() {
        let mut r = WorkspaceFolderRegistry::new();
        r.add(f("repo", "/workspace", FolderScope::Repo, false))
            .unwrap();
        r.add(f("data", "/var/data", FolderScope::Data, true))
            .unwrap();
        let j = serde_json::to_string(&r).unwrap();
        let back: WorkspaceFolderRegistry = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }
}
