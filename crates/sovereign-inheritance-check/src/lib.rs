//! `sovereign-inheritance-check` — the runnable consumer of
//! `sovereign-inheritance-artifacts`.
//!
//! M042 names 8 durable "inheritance" artifacts — the box's *executable memory*
//! (VISION / ARCHITECTURE / METHODOLOGY / PROFILES / POLICY / MODEL_REGISTRY /
//! HARDWARE_PROFILES / EVALS). The model crate fixes their canonical set, order, and
//! filenames — but nothing ran it, so "does the box actually carry its inheritance?"
//! was unanswerable. This crate is that runnable end: it renders the canonical
//! manifest and verifies the files exist under a target root.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]

use std::path::Path;

use sovereign_inheritance_artifacts::ArtifactManifest;

/// A human-readable rendering of the canonical 8-artifact manifest: position,
/// repo-relative path, and what each artifact carries.
#[must_use]
pub fn manifest_text() -> String {
    let m = ArtifactManifest::empty_canonical();
    let mut s =
        String::from("Durable inheritance artifacts (M042 — the box's executable memory):\n\n");
    for p in &m.artifacts {
        s.push_str(&format!(
            "  {}. {:<26} {}\n",
            p.kind.position(),
            p.repo_path,
            p.kind.description()
        ));
    }
    s
}

/// The (present, missing) split of the 8 canonical artifacts under `root`, by their
/// repo-relative paths.
#[must_use]
pub fn check_under(root: &Path) -> (Vec<String>, Vec<String>) {
    let m = ArtifactManifest::empty_canonical();
    let mut present = Vec::new();
    let mut missing = Vec::new();
    for p in &m.artifacts {
        if root.join(&p.repo_path).is_file() {
            present.push(p.repo_path.clone());
        } else {
            missing.push(p.repo_path.clone());
        }
    }
    (present, missing)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn manifest_lists_all_eight_artifacts() {
        let t = manifest_text();
        for f in [
            "VISION.md",
            "ARCHITECTURE.md",
            "METHODOLOGY.md",
            "PROFILES.yaml",
            "POLICY.yaml",
            "MODEL_REGISTRY.yaml",
            "HARDWARE_PROFILES.yaml",
            "EVALS.yaml",
        ] {
            assert!(t.contains(f), "manifest missing {f}:\n{t}");
        }
    }

    #[test]
    fn check_splits_present_from_missing() {
        let dir = std::env::temp_dir().join(format!("inh-check-{}", std::process::id()));
        let docs = dir.join("docs");
        std::fs::create_dir_all(&docs).unwrap();
        std::fs::write(docs.join("VISION.md"), "x").unwrap();
        std::fs::write(docs.join("POLICY.yaml"), "x").unwrap();
        let (present, missing) = check_under(&dir);
        assert!(present.contains(&"docs/VISION.md".to_string()));
        assert!(present.contains(&"docs/POLICY.yaml".to_string()));
        assert!(missing.contains(&"docs/EVALS.yaml".to_string()));
        assert_eq!(present.len() + missing.len(), 8, "all 8 accounted for");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
