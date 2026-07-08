//! `sovereign-skill-library` — M016 learning without retraining.
//!
//! The dump's "learning without retraining" names Voyager-style **skill
//! libraries**: the agent accumulates reusable procedural skills and gets
//! better by *reusing the ones that work*, never touching model weights.
//! This crate is that library — distinct from [`sovereign_memory_os`] (which
//! holds episodes/facts); here a [`Skill`] is an executable recipe with
//! per-skill use/success tracking, and retrieval prefers high-success
//! skills for a tag.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

/// Schema version of the skill-library surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A reusable procedural skill.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Skill {
    /// Unique skill name.
    pub name: String,
    /// What the skill does.
    pub description: String,
    /// Ordered steps (commands / sub-skills).
    pub steps: Vec<String>,
    /// Tags this skill applies to (used for retrieval).
    pub tags: Vec<String>,
    /// Times the skill has been used.
    pub uses: u64,
    /// Times a use succeeded.
    pub successes: u64,
}

impl Skill {
    /// Build a fresh (unused) skill.
    pub fn new(name: &str, description: &str, steps: &[&str], tags: &[&str]) -> Self {
        Self {
            name: name.to_string(),
            description: description.to_string(),
            steps: steps.iter().map(|s| s.to_string()).collect(),
            tags: tags.iter().map(|s| s.to_string()).collect(),
            uses: 0,
            successes: 0,
        }
    }

    /// Success rate in `[0, 1]`; an unused skill is `0.0`.
    pub fn success_rate(&self) -> f64 {
        if self.uses == 0 {
            0.0
        } else {
            self.successes as f64 / self.uses as f64
        }
    }

    /// Whether the skill carries `tag`.
    pub fn has_tag(&self, tag: &str) -> bool {
        self.tags.iter().any(|t| t == tag)
    }
}

/// Skill-library errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum SkillError {
    /// Adding a skill whose name already exists.
    #[error("skill '{0}' already exists")]
    Duplicate(String),
    /// Recording use of an unknown skill.
    #[error("unknown skill '{0}'")]
    Unknown(String),
}

/// A growable library of reusable skills.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SkillLibrary {
    skills: HashMap<String, Skill>,
}

impl SkillLibrary {
    /// An empty library.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a new skill; errors if the name is already present.
    pub fn add(&mut self, skill: Skill) -> Result<(), SkillError> {
        if self.skills.contains_key(&skill.name) {
            return Err(SkillError::Duplicate(skill.name));
        }
        self.skills.insert(skill.name.clone(), skill);
        Ok(())
    }

    /// Number of skills.
    pub fn len(&self) -> usize {
        self.skills.len()
    }

    /// Whether the library is empty.
    pub fn is_empty(&self) -> bool {
        self.skills.is_empty()
    }

    /// Look up a skill by name.
    pub fn get(&self, name: &str) -> Option<&Skill> {
        self.skills.get(name)
    }

    /// Record a use of a skill (success or failure), updating its stats.
    pub fn record_use(&mut self, name: &str, success: bool) -> Result<(), SkillError> {
        let skill = self
            .skills
            .get_mut(name)
            .ok_or_else(|| SkillError::Unknown(name.to_string()))?;
        skill.uses += 1;
        if success {
            skill.successes += 1;
        }
        Ok(())
    }

    /// The best skill for a `tag`: highest success rate among skills carrying
    /// it (ties broken by more uses, then name). `None` if none match.
    pub fn best_for(&self, tag: &str) -> Option<&Skill> {
        self.skills
            .values()
            .filter(|s| s.has_tag(tag))
            .max_by(|a, b| {
                a.success_rate()
                    .total_cmp(&b.success_rate())
                    .then(a.uses.cmp(&b.uses))
                    .then(b.name.cmp(&a.name))
            })
    }

    /// All skills carrying a tag, highest success first.
    pub fn all_for(&self, tag: &str) -> Vec<&Skill> {
        let mut out: Vec<&Skill> = self.skills.values().filter(|s| s.has_tag(tag)).collect();
        out.sort_by(|a, b| {
            b.success_rate()
                .total_cmp(&a.success_rate())
                .then(b.uses.cmp(&a.uses))
                .then(a.name.cmp(&b.name))
        });
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lib() -> SkillLibrary {
        let mut l = SkillLibrary::new();
        l.add(Skill::new(
            "build",
            "compile project",
            &["cargo build"],
            &["dev"],
        ))
        .unwrap();
        l.add(Skill::new(
            "test",
            "run tests",
            &["cargo test"],
            &["dev", "verify"],
        ))
        .unwrap();
        l
    }

    #[test]
    fn add_and_get() {
        let l = lib();
        assert_eq!(l.len(), 2);
        assert_eq!(l.get("build").unwrap().steps, vec!["cargo build"]);
        assert!(l.get("missing").is_none());
    }

    #[test]
    fn duplicate_add_rejected() {
        let mut l = lib();
        let err = l.add(Skill::new("build", "x", &[], &[])).unwrap_err();
        assert_eq!(err, SkillError::Duplicate("build".to_string()));
    }

    #[test]
    fn record_use_updates_success_rate() {
        let mut l = lib();
        l.record_use("build", true).unwrap();
        l.record_use("build", true).unwrap();
        l.record_use("build", false).unwrap();
        assert!((l.get("build").unwrap().success_rate() - 2.0 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn record_use_unknown_rejected() {
        let mut l = lib();
        assert_eq!(
            l.record_use("nope", true).unwrap_err(),
            SkillError::Unknown("nope".to_string())
        );
    }

    #[test]
    fn unused_skill_has_zero_rate() {
        assert_eq!(lib().get("build").unwrap().success_rate(), 0.0);
    }

    #[test]
    fn best_for_prefers_higher_success() {
        let mut l = lib();
        // both tagged "dev"; make `test` more successful
        l.record_use("build", false).unwrap();
        l.record_use("test", true).unwrap();
        assert_eq!(l.best_for("dev").unwrap().name, "test");
    }

    #[test]
    fn best_for_unknown_tag_is_none() {
        assert!(lib().best_for("ops").is_none());
    }

    #[test]
    fn all_for_returns_tagged_sorted() {
        let mut l = lib();
        l.record_use("test", true).unwrap();
        let dev = l.all_for("dev");
        assert_eq!(dev.len(), 2);
        assert_eq!(dev[0].name, "test"); // higher success first
        // "verify" tag only on `test`
        assert_eq!(l.all_for("verify").len(), 1);
    }

    #[test]
    fn serde_round_trip() {
        let mut l = lib();
        l.record_use("build", true).unwrap();
        let j = serde_json::to_string(&l).unwrap();
        let back: SkillLibrary = serde_json::from_str(&j).unwrap();
        assert_eq!(back.get("build").unwrap().uses, 1);
    }
}
